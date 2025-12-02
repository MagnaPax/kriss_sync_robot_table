# tests/integration/test_twincat_full_cycle.py
import pytest
from unittest.mock import MagicMock
from PyQt6.QtCore import QTimer

# 실제 클래스들 임포트 (통합 테스트이므로 진짜를 씀)
from services.plc_service import PLCService
from view_models.main_window_viewmodel import MainViewModel
from ui.main_window import MainWindow
from core.event_bus import EVENT_BUS
from core.settings import TwinCATConfig

"""
pytest tests/integration/test_twincat_full_cycle.py
"""

# ------------------------------------------------------------------
# Fixtures (준비물)
# ------------------------------------------------------------------

@pytest.fixture
def integration_setup(qapp, mocker):
    """
    [통합 환경 구성]
    Settings를 데모 모드로 조작하고, Service-VM-View를 모두 연결하여 반환
    """
    # 1. SETTINGS 조작 (데모 모드 ON -> 가짜 PLC 사용)
    mock_config = TwinCATConfig('127.0.0.1.1.1', 851, demo_mode=True)
    mocker.patch('core.settings.Settings.twincat', new_callable=mocker.PropertyMock, return_value=mock_config)
    
    # 2. 시간 지연 제거 (테스트 속도 향상)
    mocker.patch('time.sleep')
    
    # 3. 진짜 객체 생성 및 조립
    service = PLCService()
    vm = MainViewModel(service)
    window = MainWindow(vm)
    
    # qtbot이 이벤트를 잡을 수 있게 show 호출
    window.show()
    
    return service, vm, window

# ------------------------------------------------------------------
# Integration Test
# ------------------------------------------------------------------

def test_full_connection_cycle(integration_setup, qtbot, mocker): # [수정] mocker 인자 추가
    """
    [시나리오] 연결 시도 -> 성공 확인 -> 연결 끊김 감지 -> 복구 모드 진입 확인
    """
    service, vm, window = integration_setup
    qtbot.addWidget(window)

    # -----------------------------------------------------
    # Step 1. 초기 상태 확인 (Disconnected)
    # -----------------------------------------------------
    status_box = window.twincat_indicator
    assert status_box._lbl_state.text() == "Disconnected"
    assert service.connector.is_connected is False
    print("\n✅ [Step 1] 초기 상태: 연결 끊김 확인됨")


    # -----------------------------------------------------
    # Step 2. 연결 시도 및 성공 확인
    # -----------------------------------------------------
    with qtbot.waitSignal(vm.twincat_status_data, timeout=2000):
        success = service.connect_with_retry()
    
    assert success is True
    assert service.connector.is_connected is True
    assert status_box._lbl_state.text() == "Connected"
    print("✅ [Step 2] 연결 성공: View 업데이트 확인됨")


    # -----------------------------------------------------
    # Step 3. Heartbeat 실패 시뮬레이션 (연결 끊김 감지)
    # -----------------------------------------------------
    
    # 1. 강제로 연결 에러 상황 연출
    service.connector._twincat.read_state = MagicMock(side_effect=Exception("Lost Connection"))
    
    # 2. [핵심 수정] 자동 복구 방지 & 호출 여부 검증용 Mock킹
    #    MainWindow가 호출하는 vm.retry_connection을 가로챕니다.
    #    실제 연결은 안 하고(return_value=True), 호출되었다는 기록만 남깁니다.
    mock_retry = mocker.patch.object(vm, 'retry_connection', return_value=True)
    
    # 3. Heartbeat 체크 트리거
    #    (연결 끊김 -> EventBus 알림 -> View 수신 -> retry_connection 호출 순서로 진행됨)
    with qtbot.waitSignal(vm.show_recovery_dialog, timeout=2000):
        service._check_heartbeat()
    
    # 4. 검증
    # (1) 연결 상태가 False로 유지되어야 함 (재접속을 막았으므로)
    assert service.connector.is_connected is False
    
    # (2) UI가 복구(재접속)를 시도했는지 확인
    mock_retry.assert_called_once()
    
    print("✅ [Step 3] 연결 끊김 감지 및 복구 요청 확인됨")

