# tests/unit/test_startup.py
"""
pytest tests/unit/test_startup.py
"""
import sys
import pytest
from unittest.mock import MagicMock, call, patch
from core.startup import StartupManager
from core.event_bus import EVENT_BUS

# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def manager():
    """StartupManager 인스턴스"""
    return StartupManager()

@pytest.fixture
def mock_splash():
    """가짜 스플래시 화면"""
    splash = MagicMock()
    return splash

@pytest.fixture
def mock_event_bus(mocker):
    """EventBus 시그널 Mocking"""
    return {
        'ui_log': mocker.patch.object(EVENT_BUS, 'ui_log_message'),
        'sys_info': mocker.patch.object(EVENT_BUS, 'system_info')
    }

# ------------------------------------------------------------------
# Tests: _load_driver (DLL 로드 로직)
# ------------------------------------------------------------------

def test_load_driver_success_first_try(manager, mock_splash, mock_event_bus, mocker):
    """[시나리오] 1차 시도에 DLL 로드 성공"""
    
    # Given: load_pyads_dll이 성공(None 반환)하도록 설정
    mocker.patch('core.startup.load_pyads_dll')
    mocker.patch('time.sleep') # 딜레이 제거

    # When
    result = manager._load_driver(mock_splash)

    # Then
    assert result is True
    # 성공 메시지가 업데이트되었는지 확인
    mock_splash.update_status.assert_called_with("드라이버 로드 완료.", 40)
    # 시스템 정보 로그가 발생했는지 확인
    mock_event_bus['sys_info'].emit.assert_called_with("TwinCAT 통신 모듈(DLL) 로드 성공")


def test_load_driver_retry_success(manager, mock_splash, mock_event_bus, mocker):
    """[시나리오] 1, 2차 실패 후 3차 시도에 성공"""
    
    # Given: 에러 -> 에러 -> 성공
    mock_loader = mocker.patch('core.startup.load_pyads_dll')
    mock_loader.side_effect = [Exception("Fail 1"), Exception("Fail 2"), None]
    
    mocker.patch('time.sleep')

    # When
    result = manager._load_driver(mock_splash)

    # Then
    assert result is True
    assert mock_loader.call_count == 3
    
    # 실패 로그가 2번 남았는지 확인
    assert mock_event_bus['ui_log'].emit.call_count == 2


def test_load_driver_failure(manager, mock_splash, mock_event_bus, mocker):
    """[시나리오] 3차 시도까지 모두 실패"""
    
    # Given: 계속 에러
    mock_loader = mocker.patch('core.startup.load_pyads_dll')
    mock_loader.side_effect = Exception("DLL Not Found")
    
    # _show_critical_error 메서드 Mocking (실제 팝업 방지)
    manager._show_critical_error = MagicMock()
    mocker.patch('time.sleep')

    # When
    result = manager._load_driver(mock_splash)

    # Then
    assert result is False
    assert mock_loader.call_count == 3
    
    # 에러 팝업 호출 확인
    manager._show_critical_error.assert_called_once()


# ------------------------------------------------------------------
# Tests: run (전체 흐름)
# ------------------------------------------------------------------

def test_run_full_success(manager, mocker, qapp):
    """[시나리오] 모든 단계 성공 시 메인 윈도우 반환"""
    
    # --- Mocking Setup ---
    # 1. SplashScreen
    MockSplash = mocker.patch('core.startup.SplashScreen')
    mock_splash_instance = MockSplash.return_value
    
    # 2. _load_driver (성공으로 가정)
    manager._load_driver = MagicMock(return_value=True)
    
    # 3. PLCService
    MockService = mocker.patch('core.startup.PLCService')
    mock_service_instance = MockService.return_value
    mock_service_instance.connect_with_retry.return_value = True # 연결 성공
    
    # 4. UI 및 ViewModel (import 방지 및 Mocking)
    mocker.patch('time.sleep')
    
    # Lazy Import 되는 모듈들을 sys.modules 조작으로 Mocking
    # (실제 UI가 없으므로 이 부분이 까다로움. 간단히 흐름만 체크)
    with patch.dict('sys.modules', {
        'ui.main_window': MagicMock(),
        'view_models.main_window_viewmodel': MagicMock()
    }):
        # Mock 클래스들 가져오기
        MockMainWindow = sys.modules['ui.main_window'].MainWindow
        
        # --- When ---
        window = manager.run()
        
        # --- Then ---
        # 1. 스플래시 표시 및 닫기 확인
        mock_splash_instance.show.assert_called_once()
        assert mock_splash_instance.close.call_count >= 1
        
        # 2. 드라이버 로드 호출 확인
        manager._load_driver.assert_called_once()
        
        # 3. 서비스 연결 시도 확인
        mock_service_instance.connect_with_retry.assert_called_once()
        
        # 4. 메인 윈도우 생성 및 표시 확인
        MockMainWindow.assert_called_once()
        window.show.assert_called_once()