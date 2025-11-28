# _client_demo/25.11.18/tests/test_viewmodel.py

import pytest
from PyQt6.QtCore import QCoreApplication, QThread

# conftest.py가 경로를 설정해줘서 이제 임포트 가능
from viewmodel import FanucViewModel
from mock_model import MockFanucController
from fanuc_logic import FanucController

# =============================================================================
# Test Cases
# =============================================================================

def test_viewmodel_initialization(viewmodel: FanucViewModel):
    """Test 1: ViewModel이 '데모 모드'로 올바르게 초기화되는지 테스트"""
    assert viewmodel is not None
    assert viewmodel._is_demo_mode is True, "기본값은 데모 모드여야 합니다."
    assert isinstance(viewmodel._controller, MockFanucController), "기본 컨트롤러는 Mock이어야 합니다."



def test_set_demo_mode_to_live(viewmodel: FanucViewModel):
    """Test 2: 데모 모드를 Live 모드로 전환하는 기능 테스트"""
    viewmodel.set_demo_mode(False) #
    assert viewmodel._is_demo_mode is False
    assert isinstance(viewmodel._controller, FanucController), "컨트롤러가 Real Model로 변경되어야 합니다."



def test_connect_plc_demo_mode(viewmodel: FanucViewModel, qtbot):
    """
    Test 3: '데모 모드'에서 PLC 연결 테스트 (시그널 검증)
    qtbot.waitSignals를 사용하여 비동기 작업 종료 대기 및 시그널 값 검증
    """
    viewmodel.set_demo_mode(True)
    
    # [수정] 1. qtbot.waitSignals를 사용하여 두 시그널을 동시에 감시합니다.
    with qtbot.wait_signals(
        [viewmodel.log_updated, viewmodel.connection_changed],
        timeout=2000
    ) as blocker:
        # Action: 연결 시도
        viewmodel.connect_plc()
            
    # 2. 검증:
    # blocker.emitted는 [시그널1의 결과, 시그널2의 결과] 리스트를 담고 있습니다.
    # [0]는 log_updated의 결과, [1]는 connection_changed의 결과입니다.
    log_updates = blocker.emitted[0]
    conn_result = blocker.emitted[1]
    
    # log_updated의 첫 번째 인자(메시지)를 확인
    assert len(log_updates) >= 1, "로그 시그널이 최소 1회 발생해야 합니다."
    assert "PLC 연결 시도 중..." in log_updates[0][0]
    
    # connection_changed의 결과 검증: [True, "메시지"]
    assert len(conn_result) == 1, "connection_changed 시그널이 1회 발생해야 합니다."
    assert conn_result[0] == [True, "데모 모드: 가짜 PLC 연결 성공"]


def test_send_command_demo_mode(viewmodel: FanucViewModel, qtbot):
    """
    Test 4: '데모 모드'에서 좌표 전송 테스트 (시그널 검증)
    """
    viewmodel.set_demo_mode(True)
    
    # 연결이 완료될 때까지 먼저 대기
    with qtbot.wait_signals([viewmodel.connection_changed], timeout=2000):
        viewmodel.connect_plc()
    
    test_coords = {
        'X': 10, 'Y': 20, 'Z': 30,
        'W': 0, 'P': 0, 'R': 0, 'F': 100
    }
    
    # [수정] 1. Action 및 대기: 명령 전송 중 로그와 완료 시그널을 감시
    with qtbot.wait_signals(
        [viewmodel.log_updated, viewmodel.connection_changed], 
        timeout=1000
    ) as blocker:
        viewmodel.send_command(test_coords)
            
    # 2. 검증:
    log_updates = blocker.emitted[0]
    conn_result = blocker.emitted[1]
    
    assert len(log_updates) >= 1, "로그 시그널이 최소 1회 이상 발생해야 합니다."
    assert "좌표 전송 시작..." in log_updates[0][0] # 첫 번째 로그 메시지 확인
    
    # connection_changed 시그널은 마지막에 전송 완료를 보고합니다.
    assert len(conn_result) == 1
    assert conn_result[0] == [True, "명령 전송 완료"]


def test_connect_plc_live_mode_failure(viewmodel: FanucViewModel, qtbot):
    """
    Test 5: '라이브 모드'에서 PLC 연결 실패 테스트 (예상된 실패 검증)
    """
    viewmodel.set_demo_mode(False) # 라이브 모드
    
    # [수정] 1. Action 및 대기: 실패 시그널을 기다립니다.
    with qtbot.wait_signals(
        [viewmodel.connection_changed], 
        timeout=5000 # 네트워크 타임아웃을 충분히 기다림
    ) as blocker:
        viewmodel.connect_plc()
    
    # 2. 검증:
    conn_result = blocker.emitted[0]
    
    assert len(conn_result) == 1
    assert conn_result[0][0] is False # success == False여야 함
    assert "PLC 연결 실패" in conn_result[0][1] # 에러 메시지 확인


