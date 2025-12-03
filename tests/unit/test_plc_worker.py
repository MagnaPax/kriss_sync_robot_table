# tests/unit/test_plc_worker.py
import pytest
from unittest.mock import MagicMock, call
from workers.plc_worker import PLCWorker

"""
pytest tests/unit/test_plc_worker.py
"""

# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def mock_connector(mocker):
    """TwinCATConnector Mock"""
    # ams_net_id 속성 접근을 위해 설정
    connector = mocker.Mock()
    connector.ams_net_id = "127.0.0.1.1.1"
    return connector

@pytest.fixture
def mock_commander(mocker):
    """TwinCATCommander Mock"""
    return mocker.Mock()

def create_worker(connector, commander, cmd, data=None):
    """Helper to create worker instance"""
    return PLCWorker(connector, commander, cmd, data)

# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------

def test_run_connect_success(mock_connector, mock_commander, qtbot):
    """[CONNECT] 연결 성공 시나리오"""
    # Given
    worker = create_worker(mock_connector, mock_commander, 'CONNECT')
    
    # 시그널 감지 (Spy)
    with qtbot.waitSignal(worker.result) as blocker:
        # When
        worker.run()
    
    # Then
    mock_connector.connect.assert_called_once()
    assert blocker.args[0] is True  # Success
    assert "연결 성공" in blocker.args[1]


def test_run_connect_failure(mock_connector, mock_commander, qtbot):
    """[CONNECT] 연결 실패(예외 발생) 시나리오"""
    # Given
    mock_connector.connect.side_effect = Exception("Connection Timeout")
    worker = create_worker(mock_connector, mock_commander, 'CONNECT')
    
    with qtbot.waitSignal(worker.result) as blocker:
        worker.run()
    
    # Then
    assert blocker.args[0] is False # Failure
    assert "작업중 오류" in blocker.args[1]


def test_run_move_success(mock_connector, mock_commander, qtbot):
    """[MOVE] 이동 명령 성공 시나리오"""
    # Given
    test_data = ["coords", "prev", False, 1, []]
    worker = create_worker(mock_connector, mock_commander, 'MOVE', data=test_data)
    
    # Commander가 (new_prev, new_init) 튜플을 반환하도록 설정
    mock_commander.write_move_command.return_value = ({}, True)

    with qtbot.waitSignal(worker.result) as blocker:
        worker.run()

    # Then
    # write_move_command가 호출되었는지, 인자가 맞는지 확인
    # (check_stop 콜백은 worker 내부 메서드이므로 any 검사)
    mock_commander.write_move_command.assert_called_once()
    call_args = mock_commander.write_move_command.call_args
    assert call_args[0] == tuple(test_data) # 위치 인자 확인
    assert 'check_stop' in call_args[1]     # 키워드 인자 확인
    
    assert blocker.args[0] is True


def test_run_move_no_data_error(mock_connector, mock_commander, qtbot):
    """[MOVE] 데이터 없이 호출 시 에러 발생 확인"""
    # Given: data=None
    worker = create_worker(mock_connector, mock_commander, 'MOVE', data=None)
    
    with qtbot.waitSignal(worker.result) as blocker:
        worker.run()
    
    # Then
    assert blocker.args[0] is False
    assert "MOVE 명령에 필요한 데이터가 없습니다" in blocker.args[1]


def test_run_control_commands(mock_connector, mock_commander, qtbot):
    """[START/STOP/PAUSE/RESUME] 제어 명령 라우팅 확인"""
    
    # 테이블 기반 테스트 (Table Driven Test)
    scenarios = [
        ('START', mock_commander.start_process),
        ('STOP', mock_commander.stop_process),
        ('PAUSE', mock_commander.pause_process),
        ('RESUME', mock_commander.resume_process),
    ]

    for cmd, mock_method in scenarios:
        # START/STOP은 반환값이 (bool, str) 튜플임
        if cmd in ['START', 'STOP']:
            mock_method.return_value = (True, "OK")
        
        worker = create_worker(mock_connector, mock_commander, cmd)
        
        with qtbot.waitSignal(worker.result) as blocker:
            worker.run()
        
        # 해당 메서드가 호출되었는지 확인
        mock_method.assert_called_once()
        assert blocker.args[0] is True
        
        # Mock 초기화 (다음 루프를 위해)
        mock_method.reset_mock()


def test_run_unknown_command(mock_connector, mock_commander, qtbot):
    """알 수 없는 명령 처리"""
    worker = create_worker(mock_connector, mock_commander, 'INVALID_CMD')
    
    with qtbot.waitSignal(worker.result) as blocker:
        worker.run()
        
    assert blocker.args[0] is False
    assert "알 수 없는 명령" in blocker.args[1]