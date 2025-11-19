# _client_demo/25.11.18/tests/test_controllers_logging.py
"""
테스트 실행
_client_demo/25.11.18/pytest

"""



# _client_demo/25.11.18/tests/test_controllers_logging.py (최종 안정화 버전)

import pytest
import os
import time
from unittest import mock
import logging

# =========================================================================
# (pyads Mocking 코드는 변경 없음)
# =========================================================================
import sys

mock_pyads = mock.MagicMock(spec=sys.modules.get('pyads')) 
MockConnection = mock.MagicMock() 
mock_pyads.Connection = MockConnection 

mock_pyads.PORT_TC3PLC1 = 851 
mock_pyads.PLCTYPE_BOOL = bool

sys.modules['pyads'] = mock_pyads
# =========================================================================

from fanuc_logic import FanucController
from mock_model import MockFanucController
from fanuc_logger import logger, FanucLogger


LOG_FILE_NAME = FanucLogger().log_file

@pytest.fixture(autouse=True)
def cleanup_log_file():
    """
    로그 파일 정리 및 핸들러 복원을 관리합니다.
    - setup 단계에서 모든 정리와 재설정을 완료하고, teardown은 생략합니다.
    """
    
    # 1. 이전 테스트 종료 후: 핸들러 닫고 제거 (파일 잠금 해제)
    for handler in logger.handlers[:]: 
        if isinstance(handler, logging.FileHandler):
            handler.close()
            logger.removeHandler(handler)

    # 2. 로그 파일 삭제
    if os.path.exists(LOG_FILE_NAME):
        try:
            os.remove(LOG_FILE_NAME)
        except PermissionError:
            time.sleep(0.1) 
            if os.path.exists(LOG_FILE_NAME):
                os.remove(LOG_FILE_NAME)

    # 3. 테스트 진행 준비: 새로운 로거 인스턴스를 생성하여 핸들러를 다시 등록
    FanucLogger() 

    yield # 테스트 실행

    # 4. 테스트 종료 후 (Teardown): 다음 테스트의 setup 단계에 정리를 맡기고,
    # 여기서 핸들러를 닫지 않아 파일 쓰기 지연으로 인한 AssertionError를 방지합니다.
    # 이 섹션은 PASS 처리합니다.
    pass 


# --- 로그 파일 내용 확인 헬퍼 함수 ---
def read_log_file():
    """
    로그 파일의 모든 내용을 문자열로 반환합니다.
    """
    # 모든 핸들러의 버퍼 flush
    for handler in logger.handlers:
        if isinstance(handler, logging.FileHandler):
            handler.flush()
    
    # 파일 시스템 쓰기 완료 대기
    time.sleep(0.05)
    
    # 파일 읽기
    if not os.path.exists(LOG_FILE_NAME):
        return ""
    
    try:
        with open(LOG_FILE_NAME, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception:
        return ""



# =========================================================
# (테스트 함수 로직은 변경 없음)
# =========================================================
def test_fanuc_controller_connect_logging_success():
    """실제 FanucController의 연결 성공 시 로깅을 테스트합니다."""
    # Given
    controller = FanucController()

    # When
    controller.connect_plc()
    
    # Then: 로그 파일 내용 확인
    log_content = read_log_file()
    
    assert "[FanucController] 인스턴스 생성 완료" in log_content
    assert "connect_plc 시작" in log_content
    assert "PLC 연결 성공 (5.119.154.174.1.1)" in log_content
    assert "INFO" in log_content


def test_fanuc_controller_connect_logging_failure():
    """실제 FanucController의 연결 실패 시 에러 로깅을 테스트합니다."""
    # Given
    controller = FanucController()

    # When
    # Connection 객체의 open()이 실패하도록 임시 Mock 설정 (MockConnection의 return_value로 접근)
    with mock.patch.object(MockConnection.return_value, 'open', side_effect=Exception("Mocked Connection Error")):
        controller.connect_plc()
    
    # Then: 로그 파일 내용 확인
    log_content = read_log_file()
    
    assert "PLC 연결 실패: Mocked Connection Error" in log_content
    assert "ERROR" in log_content


def test_fanuc_controller_execute_command_logging():
    """FanucController의 execute_command 명령 실행 로깅을 테스트합니다."""
    # Given
    controller = FanucController()
    controller.is_connected = True # 연결된 상태 가정
    
    # pyads.Connection()의 인스턴스(MockConnection.return_value)를 controller.plc에 할당
    controller.plc = MockConnection.return_value

    # When
    controller.execute_command(10.5, -20.0, 50.12, 0.0, 90.0, -45.0, 10.0)
    
    # Then: 로그 파일 내용 확인
    log_content = read_log_file()
    
    assert "execute_command 시작. 좌표: X:10.5, Y:-20.0, Z:50.12, W:0.0, P:90.0, R:-45.0, F:10.0" in log_content
    assert "RSR 신호 OFF (초기화)" in log_content
    assert "좌표(X,Y,Z,W,P,R) 값 비트 전송 완료" in log_content
    assert "RSR 신호 ON (명령 트리거)" in log_content


# =========================================================
# 2. MockFanucController (데모 로직) 테스트
# =========================================================

def test_mock_controller_connect_logging():
    """MockFanucController의 연결 로깅을 테스트합니다."""
    # Given
    controller = MockFanucController()

    # When
    controller.connect_plc()
    
    # Then: 로그 파일 내용 확인
    log_content = read_log_file()
    
    assert "[MOCK] 가짜 FanucController 객체 생성" in log_content
    assert "[MOCK] PLC 연결 시도... (네트워크 딜레이 1초 시뮬레이션)" in log_content
    assert "데모 모드: 가짜 PLC 연결 성공" in log_content
    assert "INFO" in log_content

def test_mock_controller_execute_command_logging():
    """MockFanucController의 명령 실행 로깅을 테스트합니다."""
    # Given
    controller = MockFanucController()
    controller.is_connected = True

    # When
    controller.execute_command(1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0)
    
    # Then: 로그 파일 내용 확인
    log_content = read_log_file()
    
    assert "[MOCK] 가짜 FanucController 객체 생성" in log_content
    assert "[MOCK] RSR 신호 OFF" in log_content
    assert "좌표 전송 시작..." in log_content
    assert "[MOCK] 좌표 쓰기: [X:1.0, Y:2.0, Z:3.0, W:4.0, P:5.0, R:6.0, F:7.0]" in log_content
    assert "[MOCK] RSR 신호 ON" in log_content
