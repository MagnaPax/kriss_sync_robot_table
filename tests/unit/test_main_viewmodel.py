import pytest
from unittest.mock import Mock
from view_models.main_window_viewmodel import MainViewModel
from core.event_bus import EVENT_BUS

"""
pytest tests/unit/test_main_viewmodel.py
"""

# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def mock_service():
    """
    PLCService를 가짜(Mock)로 생성
    """
    service = Mock()
    # connector 속성도 Mock으로 만들어줘야 property 접근 시 에러 안 남
    service.connector = Mock()
    return service

@pytest.fixture
def viewmodel(qapp, mock_service):
    """
    테스트 대상인 MainViewModel 생성
    (qapp 픽스처는 QObject 생성을 위해 필수)
    """
    vm = MainViewModel(mock_service)
    return vm

# ------------------------------------------------------------------
# Tests: View -> ViewModel -> Service (명령 전달)
# ------------------------------------------------------------------

def test_is_connected_property(viewmodel, mock_service):
    """View가 is_connected를 조회하면 Service의 상태를 리턴하는지 확인"""
    # Given
    mock_service.connector.is_connected = True
    # Then
    assert viewmodel.is_connected is True
    
    # Given
    mock_service.connector.is_connected = False
    # Then
    assert viewmodel.is_connected is False

def test_request_disconnect(viewmodel, mock_service):
    """연결 해제 요청 시 Service 메서드 호출 확인"""
    # When
    viewmodel.request_disconnect()
    
    # Then
    mock_service.disconnect_plc.assert_called_once()

def test_retry_connection(viewmodel, mock_service):
    """재접속 요청 시 Service 메서드 호출 및 콜백 전달 확인"""
    # Given
    mock_callback = Mock()
    
    # When
    viewmodel.retry_connection(mock_callback)
    
    # Then
    mock_service.connect_with_retry.assert_called_once_with(mock_callback)

# ------------------------------------------------------------------
# Tests: EventBus -> ViewModel -> View (이벤트 중계)
# ------------------------------------------------------------------

def test_connection_status_relay(viewmodel, qtbot):
    """
    [시나리오] EventBus에서 연결 상태 변경 신호가 오면,
             ViewModel이 View용 로컬 시그널을 재송출(Relay)하는지 확인
    """
    # qtbot: 시그널을 감지하는 로봇 (pytest-qt 플러그인 기능)
    with qtbot.waitSignal(viewmodel.connection_status, timeout=1000) as blocker:
        # When: 방송국(EventBus)에서 신호 송출
        EVENT_BUS.conn.status_changed.emit(True)
        
    # Then: ViewModel의 시그널이 발사되었고, 값(True)이 일치하는지 확인
    assert blocker.args == [True]

def test_system.error_handling_disconnected(viewmodel, qtbot):
    """
    [시나리오] EventBus에서 'TwinCAT_DISCONNECTED' 에러가 오면,
             ViewModel이 '복구 다이얼로그 표시' 시그널을 보내는지 확인
    """
    # show_recovery_dialog 시그널 대기
    with qtbot.waitSignal(viewmodel.show_recovery_dialog, timeout=1000):
        # When: 시스템 에러 발생 (연결 끊김)
        EVENT_BUS.system.error.emit("TwinCAT_DISCONNECTED")

def test_system.error_handling_other_errors(viewmodel, qtbot):
    """
    [시나리오] 'TwinCAT_DISCONNECTED' 이외의 에러는 
             복구 다이얼로그 시그널을 보내지 않아야 함
    """
    # 시그널이 발생하지 않음을 검증 (assertNotEmitted)
    with qtbot.assertNotEmitted(viewmodel.show_recovery_dialog):
        # When: 다른 종류의 에러 발생
        EVENT_BUS.system.error.emit("Some Other Random Error")