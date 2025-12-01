# tests/unit/test_startup.py
"""
pytest tests/unit/test_startup.py
"""

import pytest
from unittest.mock import call, MagicMock
from core.startup import StartupManager
from core.event_bus import EVENT_BUS



# qapp: conftest.py에서 만든 픽스처 자동 주입
# mocker: pytest-mock 플러그인이 제공하는 강력한 모킹 도구


# def test_connection_retry_success(qapp, mocker):
#     """
#     [시나리오 1] 연결 실패 후 재시도하여 결국 성공하는 케이스
#     """
#     # --- Given ---
#     manager = StartupManager()
    
#     # load_pyads_dll 함수를 가짜(Mock)로 교체
#     # 효과: 에러 -> 에러 -> 성공 (True)
#     mock_loader = mocker.patch('core.startup.load_pyads_dll')
#     mock_loader.side_effect = [
#         Exception("1차 실패"),
#         Exception("2차 실패"),
#         True 
#     ]
    
#     # 스플래시 화면 Mocking (실제 창 안 뜨게)
#     mock_splash = mocker.Mock()

#     # --- When ---
#     result = manager._attempt_connection(mock_splash)

#     # --- Then ---
#     assert result is True  # 결과는 성공이어야 함
#     assert mock_loader.call_count == 3  # 총 3번 시도했어야 함
    
#     # 스플래시 화면에 상태 업데이트가 호출되었는지 확인
#     assert mock_splash.update_status.called


# def test_connection_failure(qapp, mocker):
#     """
#     [시나리오 2] 3번 모두 실패하여 결국 False를 반환하는 케이스
#     """
#     # --- Given ---
#     manager = StartupManager()
    
#     # 계속 에러 발생
#     mock_loader = mocker.patch('core.startup.load_pyads_dll')
#     mock_loader.side_effect = Exception("연결 불가")
    
#     mock_splash = mocker.Mock()

#     # --- When ---
#     result = manager._attempt_connection(mock_splash)

#     # --- Then ---
#     assert result is False # 결과는 실패여야 함
#     assert mock_loader.call_count == 3 # 3번까지 시도하고 포기했어야 함





def test_connection_retry_sequence_and_logs(qapp, mocker):
    """
    [통합 시나리오] 
    1. 연결 실패 -> 재시도 메시지 표시 -> 로그 기록
    2. 3번째 시도에 성공 -> 성공 메시지 표시 -> 시스템 정보 로그 기록
    """
    
    # --- Given (준비) ---
    manager = StartupManager()
    
    # 1. DLL 로더 모킹
    mock_loader = mocker.patch('core.startup.load_pyads_dll')
    mock_loader.side_effect = [
        Exception("1차 에러"),
        Exception("2차 에러"),
        True 
    ]
    
    # 2. 스플래시 화면 모킹
    mock_splash = mocker.Mock()
    
    # 3. [수정됨] EventBus 시그널 자체를 Mock으로 교체
    # 'emit' 메서드만 막는 게 아니라 시그널 객체를 통째로 Mocking 합니다.
    mock_log_signal = mocker.patch.object(EVENT_BUS, 'ui_log_message')
    mock_info_signal = mocker.patch.object(EVENT_BUS, 'system_info')
    
    # 4. 시간 지연 모킹
    mocker.patch('time.sleep') 


    # --- When (실행) ---
    result = manager._attempt_connection(mock_splash)


    # --- Then (검증) ---
    
    # 1. 결과 검증
    assert result is True
    assert mock_loader.call_count == 3

    # 2. 스플래시 메시지 검증
    expected_calls = [
        call("TwinCAT 접속 시도 중... (1/3)", 30),
        call("접속 실패. 재시도 대기 중...", 30),
        call("TwinCAT 접속 시도 중... (2/3)", 60),
        call("접속 실패. 재시도 대기 중...", 60),
        call("TwinCAT 접속 시도 중... (3/3)", 90),
        call("접속 완료! 시스템을 시작합니다.", 100)
    ]
    mock_splash.update_status.assert_has_calls(expected_calls, any_order=False)
    
    # 3. 로그 기록 검증 (이제 시그널 객체의 emit을 검사)
    assert mock_log_signal.emit.call_count == 2
    mock_log_signal.emit.assert_any_call("접속 시도(1) 실패: 1차 에러", "WARNING")
    mock_log_signal.emit.assert_any_call("접속 시도(2) 실패: 2차 에러", "WARNING")
    
    mock_info_signal.emit.assert_called_with("TwinCAT 통신 모듈 로드 성공")
