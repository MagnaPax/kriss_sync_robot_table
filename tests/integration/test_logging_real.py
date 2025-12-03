# tests/integration/test_logging_real.py
"""
pytest tests/integration/test_logging_real.py
"""
import pytest
import time
from core.event_bus import EVENT_BUS
from core.log_listener import LogListener

def test_real_logging_to_file(qapp):
    """
    [통합 테스트] 실제 LogListener를 연결해서 파일에 로그가 남는지 확인
    """
    # 1. 실제 리스너 생성 (이제부터 파일을 씁니다)
    listener = LogListener()
    
    # 2. 실제 에러 로그 발생시키기
    test_msg = f"이것은 실제 파일 기록 테스트입니다. (Time: {time.time()})"
    EVENT_BUS.ui_log_message.emit(test_msg, "ERROR")
    
    # 3. 파일 확인
    from config.paths import LOG_DIR
    from utils.logger import LoggerConfig
    
    # LoggerConfig가 초기화되었는지 확인 (보통 LogListener 생성 시 됨)
    # 파일 경로: logs/error.log
    error_log_path = LoggerConfig.ERROR_LOG
    
    assert error_log_path.exists(), "error.log 파일이 생성되어야 합니다."
    
    # 파일 내용을 읽어서 방금 쓴 메시지가 있는지 확인
    with open(error_log_path, 'r', encoding='utf-8') as f:
        content = f.read()
        assert test_msg in content, "로그 파일에 테스트 메시지가 저장되어야 합니다."
        
    print(f"\n✅ 실제 로그 파일 기록 확인 완료: {error_log_path}")
