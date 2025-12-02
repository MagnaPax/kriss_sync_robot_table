# tests/unit/test_plc_service.py
import pytest
from unittest.mock import MagicMock, call
from services.plc_service import PLCService
from core.event_bus import EVENT_BUS

"""
pytest tests/unit/test_plc_service.py
"""

# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def mock_service(qapp, mocker):
    """
    PLCService를 생성하되, 내부의 Connector와 Commander를 가짜(Mock)로 교체
    """
    # 1. 서비스 생성
    service = PLCService()
    
    # 2. 내부 Model 객체들을 Mock으로 교체 (실제 통신 차단)
    service.connector = mocker.Mock()
    service.commander = mocker.Mock()
    
    # 3. 시간 지연(sleep) 제거 (테스트 속도 향상)
    mocker.patch('time.sleep')
    
    return service

@pytest.fixture
def mock_event_bus(mocker):
    """
    EventBus의 주요 시그널들을 Mocking하여 호출 여부 추적
    """
    # 주의: 시그널 객체 자체를 Mock으로 교체해야 함
    mocks = {
        'ui_log': mocker.patch.object(EVENT_BUS, 'ui_log_message'),
        'conn_status': mocker.patch.object(EVENT_BUS, 'connection_status_changed'),
        'sys_error': mocker.patch.object(EVENT_BUS, 'system_error'),
        'sys_info': mocker.patch.object(EVENT_BUS, 'system_info')
    }
    return mocks

# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------

def test_connect_with_retry_success(mock_service, mock_event_bus):
    """
    [시나리오] 재접속 시도: 1, 2차 실패 후 3차 성공
    """
    # Given: 커넥터가 에러 -> 에러 -> 성공 순으로 동작하도록 설정
    mock_service.connector.connect.side_effect = [
        Exception("Fail 1"),
        Exception("Fail 2"),
        None # 성공 (Return None)
    ]
    
    # UI 콜백용 가짜 함수
    mock_callback = MagicMock()

    # When: 재접속 시도
    result = mock_service.connect_with_retry(ui_callback=mock_callback)

    # Then:
    # 1. 결과는 True여야 함
    assert result is True
    
    # 2. 커넥터의 connect가 총 3번 호출되었는지 확인
    assert mock_service.connector.connect.call_count == 3
    
    # 3. 성공 시 시스템 정보와 연결 상태 변경 신호가 나갔는지 확인
    mock_event_bus['sys_info'].emit.assert_called_with("TwinCAT 연결 성공")
    mock_event_bus['conn_status'].emit.assert_called_with(True)
    
    # 4. Heartbeat 타이머가 시작되었는지 확인
    assert mock_service._heartbeat_timer.isActive()


def test_connect_with_retry_failure(mock_service, mock_event_bus):
    """
    [시나리오] 3번 모두 실패하여 최종 실패 처리
    """
    # Given: 계속 에러 발생
    mock_service.connector.connect.side_effect = Exception("Network Error")
    
    # When
    result = mock_service.connect_with_retry()

    # Then
    assert result is False
    assert mock_service.connector.connect.call_count == 3
    
    # CRITICAL 로그가 남았는지 확인
    mock_event_bus['ui_log'].emit.assert_called_with("TwinCAT 연결 실패", "CRITICAL")


def test_heartbeat_loss_detection(mock_service, mock_event_bus):
    """
    [시나리오] 하트비트 체크 중 연결 끊김 감지
    """
    # Given: 커넥터가 '죽었다(False)'고 응답
    mock_service.connector.check_connection.return_value = False
    
    # 타이머가 돌고 있다고 가정
    mock_service._heartbeat_timer.start()

    # When: 하트비트 체크 함수 직접 호출 (타이머에 의해 호출된 상황 가정)
    mock_service._check_heartbeat()

    # Then:
    # 1. 타이머가 멈췄어야 함
    assert mock_service._heartbeat_timer.isActive() is False
    
    # 2. 연결 끊김 신호(False) 전송 확인
    mock_event_bus['conn_status'].emit.assert_called_with(False)
    
    # 3. [핵심] 시스템 에러(TwinCAT_DISCONNECTED) 발생 확인 (이게 MainWindow를 깨움)
    mock_event_bus['sys_error'].emit.assert_called_with("TwinCAT_DISCONNECTED")


def test_disconnect_plc(mock_service, mock_event_bus):
    """
    [시나리오] 정상적인 연결 해제 요청
    """
    # Given: 현재 연결된 상태
    mock_service.connector.is_connected = True
    
    # When: 해제 요청
    mock_service.disconnect_plc()
    
    # Then:
    # 1. 커넥터의 disconnect가 호출되었는지
    mock_service.connector.disconnect.assert_called_once()
    
    # 2. 타이머 정지 확인
    assert mock_service._heartbeat_timer.isActive() is False
    
    # 3. 상태 변경 신호 확인
    mock_event_bus['conn_status'].emit.assert_called_with(False)