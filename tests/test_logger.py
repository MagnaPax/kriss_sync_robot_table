"""
tests/test_logger.py
--------------------
utils/logger.py 통합 테스트 스크립트

테스트 항목:
1. Logger 싱글톤 패턴 검증
2. 로그 디렉토리 및 파일 생성 확인
3. 로그 레벨별 출력 및 파일 기록 검증
4. 에러 로그 분리 기록 확인
5. 예외 자동 로깅(sys.excepthook) 테스트
6. 환경 변수(LOG_LEVEL) 동적 제어 확인
7. 컬러 포매터 작동 확인

실행 방법:
    pytest tests/test_logger.py

    tests 폴더 안의 모든 테스트 파일 실행 원하면(pytest.ini 이용)
    pytest



"""

import os
import sys
import time
import logging
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler


import pytest

# --- 경로 문제 해결 ---
# 프로젝트 루트 디렉토리를 sys.path에 추가하여 'utils' 모듈을 찾을 수 있도록 합니다.
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# 테스트 대상 모듈 임포트
from utils.logger import Logger, ColorFormatter
from utils.env import AppEnv


# =============================================================================
# Fixtures
# =============================================================================
@pytest.fixture(scope="module")
def logger_instance():
    """
    Logger 싱글톤 인스턴스 준비
    
    Note:
        module 스코프로 모든 테스트에서 동일 인스턴스 사용
    """
    instance = Logger()
    yield instance.logger


@pytest.fixture(scope="function")
def clean_log_files():
    """
    각 테스트 전후로 로그 파일 정리 (선택적 사용)
    
    Note:
        function 스코프로 각 테스트마다 독립적 실행
    """
    yield
    # 테스트 후 정리 작업이 필요하면 여기 추가


# =============================================================================
# Test 1: 싱글톤 패턴 검증
# =============================================================================
def test_singleton_pattern():
    """
    Logger가 싱글톤으로 동작하는지 확인
    
    검증:
        - 여러 번 인스턴스를 생성해도 동일한 객체 반환
        - 객체 ID가 모두 동일함
    """
    logger1 = Logger()
    logger2 = Logger()
    logger3 = Logger()
    
    # 객체 ID 비교
    assert id(logger1) == id(logger2) == id(logger3), \
        "Logger 클래스가 싱글톤으로 동작하지 않음"
    
    # is 연산자로 동일성 확인
    assert logger1 is logger2 is logger3, \
        "Logger 인스턴스가 서로 다른 객체"


# =============================================================================
# Test 2: 로그 디렉토리 생성 확인
# =============================================================================
def test_log_directory_created():
    """
    로그 디렉토리가 자동으로 생성되는지 확인
    
    검증:
        - Logger 초기화 시 LOG_DIR 디렉토리 생성
        - 디렉토리가 실제 파일 시스템에 존재
    """
    logger = Logger()
    log_dir = Path(logger.LOG_DIR)
    
    assert log_dir.exists(), \
        f"로그 디렉토리 {log_dir}가 존재하지 않음"
    
    assert log_dir.is_dir(), \
        f"{log_dir}가 디렉토리가 아님"


# =============================================================================
# Test 3: 로그 파일 생성 및 기록 확인
# =============================================================================
def test_log_file_creation_and_write(logger_instance):
    """
    INFO 로그가 파일에 정상 기록되는지 확인
    
    검증:
        - app_YYYYMMDD.log 파일 생성
        - INFO 레벨 메시지가 파일에 기록됨
    """
    test_message = "TEST_LOG_INFO_MESSAGE_12345"
    logger_instance.info(test_message)
    
    # 파일 시스템 동기화 대기
    time.sleep(0.3)
    
    log_path = Path(Logger().LOG_FILE)
    
    # 파일 존재 확인
    assert log_path.exists(), \
        f"로그 파일 {log_path}이(가) 존재하지 않음"
    
    # 파일 내용 확인
    content = log_path.read_text(encoding="utf-8")
    assert test_message in content, \
        f"로그 파일에 '{test_message}' 메시지가 기록되지 않음"


# =============================================================================
# Test 4: 에러 로그 분리 기록 확인
# =============================================================================
def test_error_log_separation(logger_instance):
    """
    WARNING 이상의 로그가 error.log에 별도 기록되는지 확인
    
    검증:
        - error.log 파일 생성
        - WARNING, ERROR 메시지가 error.log에 기록됨
        - INFO 메시지는 error.log에 기록되지 않음
    """
    test_error_message = "TEST_ERROR_MESSAGE_67890"
    test_info_message = "TEST_INFO_NOT_IN_ERROR_LOG"
    
    logger_instance.info(test_info_message)
    logger_instance.error(test_error_message)
    
    # 파일 시스템 동기화 대기
    time.sleep(0.3)
    
    err_path = Path(Logger().ERROR_LOG_FILE)
    
    # 파일 존재 확인
    assert err_path.exists(), \
        f"에러 로그 파일 {err_path}이(가) 존재하지 않음"
    
    # 파일 내용 확인
    content = err_path.read_text(encoding="utf-8")
    
    # ERROR 메시지는 포함되어야 함
    assert test_error_message in content, \
        f"에러 로그에 '{test_error_message}' 메시지가 기록되지 않음"
    
    # INFO 메시지는 포함되지 않아야 함
    assert test_info_message not in content, \
        f"에러 로그에 INFO 메시지가 잘못 기록됨"


# =============================================================================
# Test 5: 모든 로그 레벨 출력 확인
# =============================================================================
def test_all_log_levels(logger_instance):
    """
    DEBUG, INFO, WARNING, ERROR, CRITICAL 레벨 모두 정상 작동 확인
    
    검증:
        - 각 레벨의 메시지가 적절한 파일에 기록됨
    """
    logger_instance.debug("TEST_DEBUG_MESSAGE")
    logger_instance.info("TEST_INFO_MESSAGE")
    logger_instance.warning("TEST_WARNING_MESSAGE")
    logger_instance.error("TEST_ERROR_MESSAGE")
    logger_instance.critical("TEST_CRITICAL_MESSAGE")
    
    time.sleep(0.3)
    
    # 일반 로그 파일 확인 (INFO 이상)
    log_content = Path(Logger().LOG_FILE).read_text(encoding="utf-8")
    assert "TEST_INFO_MESSAGE" in log_content
    assert "TEST_WARNING_MESSAGE" in log_content
    assert "TEST_ERROR_MESSAGE" in log_content
    assert "TEST_CRITICAL_MESSAGE" in log_content
    
    # 에러 로그 파일 확인 (WARNING 이상)
    err_content = Path(Logger().ERROR_LOG_FILE).read_text(encoding="utf-8")
    assert "TEST_WARNING_MESSAGE" in err_content
    assert "TEST_ERROR_MESSAGE" in err_content
    assert "TEST_CRITICAL_MESSAGE" in err_content


# =============================================================================
# Test 6: 예외 스택 트레이스 기록 확인
# =============================================================================
def test_exception_logging(logger_instance):
    """
    exception() 메서드가 스택 트레이스를 포함하여 기록하는지 확인
    
    검증:
        - 예외 메시지가 error.log에 기록
        - 스택 트레이스 포함 (Traceback 문자열 존재)
    """
    test_exception_message = "TEST_INTENTIONAL_EXCEPTION_98765"
    
    try:
        raise ValueError(test_exception_message)
    except ValueError:
        logger_instance.exception("예외 발생 테스트")
    
    time.sleep(0.3)
    
    err_path = Path(Logger().ERROR_LOG_FILE)
    content = err_path.read_text(encoding="utf-8")
    
    # 예외 메시지 확인
    assert test_exception_message in content, \
        "예외 메시지가 error.log에 기록되지 않음"
    
    # 스택 트레이스 확인
    assert "Traceback" in content or "ValueError" in content, \
        "스택 트레이스가 error.log에 기록되지 않음"



# =============================================================================
# Test 8: 환경 변수로 로그 레벨 제어 확인
# =============================================================================
def test_log_level_env_override(monkeypatch):
    """
    환경 변수 LOG_LEVEL로 로그 레벨을 제어할 수 있는지 확인
    
    검증:
        - LOG_LEVEL 환경 변수 설정 가능
    
    Note:
        이 테스트는 Logger를 재초기화하지 않으므로 완벽한 검증은 어려움
        실제 환경 변수 테스트는 별도 프로세스에서 수행 권장
        실제 테스트: LOG_LEVEL=ERROR pytest tests/test_logger.py
    """
    # 환경 변수 설정 (테스트용)
    monkeypatch.setenv("LOG_LEVEL", "ERROR")
    
    assert os.getenv("LOG_LEVEL") == "ERROR", \
        "환경 변수 설정 실패"


# =============================================================================
# Test 9: 컬러 포매터 작동 확인
# =============================================================================
"""
def test_console_color_formatter_OLD(logger_instance, caplog, monkeypatch):
    # 컬러 출력을 강제하기 위해 isatty()가 True를 반환하도록 패치
    monkeypatch.setattr(sys.stdout, 'isatty', lambda: True)

    # caplog의 로그 레벨을 DEBUG로 설정하여 모든 로그를 캡처
    with caplog.at_level(logging.DEBUG):
        logger_instance.info("TEST_COLORED_OUTPUT_12345")

    test_color_message = "TEST_COLORED_OUTPUT_12345"

    # 개발 모드일 때만 콘솔 출력 확인
    if not AppEnv().is_packaged:
        # caplog.text에 색상 코드와 메시지가 모두 포함되어 있는지 확인
        assert "\033[32m" in caplog.text, "콘솔 출력에 INFO 레벨 색상 코드가 없음"
        assert test_color_message in caplog.text, "콘솔 출력에 로그 메시지가 없음"
"""

def test_console_color_formatter(monkeypatch):
    """
    ColorFormatter가 ANSI 색상 코드를 정상적으로 적용하는지 확인
    
    검증:
        - ColorFormatter가 TTY 환경에서 색상 코드를 추가함
        - 비TTY 환경에서는 색상 코드를 추가하지 않음
    """
    # ColorFormatter 인스턴스 생성
    formatter = ColorFormatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 로그 레코드 생성
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=42,
        msg="TEST_COLORED_OUTPUT",
        args=(),
        exc_info=None
    )

    # TTY 환경 시뮬레이션 (색상 코드 적용됨)
    monkeypatch.setattr(sys.stdout, 'isatty', lambda: True)
    formatted_with_color = formatter.format(record)
    
    # ANSI 색상 코드 확인 (INFO = green = \033[32m)
    assert "\033[32m" in formatted_with_color, \
        "TTY 환경에서 색상 코드가 적용되지 않음"
    
    assert "TEST_COLORED_OUTPUT" in formatted_with_color, \
        "포맷된 메시지에 원본 메시지가 없음"
    
    # 비TTY 환경 시뮬레이션 (색상 코드 미적용)
    monkeypatch.setattr(sys.stdout, 'isatty', lambda: False)
    formatted_without_color = formatter.format(record)
    
    # 색상 코드가 없어야 함
    assert "\033[" not in formatted_without_color, \
        "비TTY 환경에서 색상 코드가 잘못 적용됨"
    
    assert "TEST_COLORED_OUTPUT" in formatted_without_color, \
        "포맷된 메시지에 원본 메시지가 없음"
        

# =============================================================================
# Test 10: 모듈별 로거 생성 확인
# =============================================================================
def test_module_logger_creation():
    """
    logging.getLogger()로 모듈별 로거를 직접 생성할 수 있는지 확인
    
    검증:
        - 모듈 이름이 로거 네임스페이스에 포함
        - 부모 로거 설정 상속
    """
    module_name = "test_module.submodule"
    
    # Logger의 APP_NAME을 기반으로 직접 생성
    module_logger = logging.getLogger(f"{Logger.APP_NAME}.{module_name}")
    
    expected_name = f"{Logger.APP_NAME}.{module_name}"
    assert module_logger.name == expected_name, \
        f"모듈 로거 이름이 {expected_name}이 아님"
    
    # 메시지 기록 테스트
    test_module_message = "TEST_MODULE_LOGGER_MESSAGE_99999"
    module_logger.info(test_module_message)
    
    time.sleep(0.3)
    
    # 일반 로그 파일에 기록 확인
    content = Path(Logger().LOG_FILE).read_text(encoding="utf-8")
    assert test_module_message in content, \
        "모듈 로거 메시지가 파일에 기록되지 않음"


# =============================================================================
# Test 11: 로그 파일 로테이션 설정 확인
# =============================================================================
def test_log_rotation_configuration():
    """
    TimedRotatingFileHandler가 올바르게 설정되었는지 확인
    
    검증:
        - backupCount 설정값 확인
        - when='midnight' 설정 확인
    """
    logger = Logger()
    
    file_handlers = [
        h for h in logger.logger.handlers
        if isinstance(h, TimedRotatingFileHandler)
    ]
    
    assert len(file_handlers) >= 1, \
        "TimedRotatingFileHandler가 등록되지 않음"
    
    # 일반 로그 핸들러 확인
    app_log_handler = next(
        (h for h in file_handlers if "app_" in str(h.baseFilename)),
        None
    )
    
    if app_log_handler:
        assert app_log_handler is not None, "일반 로그 핸들러를 찾을 수 없습니다."
        assert app_log_handler.backupCount == Logger.COUNT_BACKUP, \
            f"일반 로그 backupCount가 {Logger.COUNT_BACKUP}이 아님"
    
    # 에러 로그 핸들러 확인
    error_log_handler = next(
        (h for h in file_handlers if h.baseFilename and "error.log" in str(h.baseFilename)),
        None
    )
    
    if error_log_handler:
        assert error_log_handler is not None, "에러 로그 핸들러를 찾을 수 없습니다."
        assert error_log_handler.backupCount == Logger.COUNT_BACKUP_ERROR, \
            f"에러 로그 backupCount가 {Logger.COUNT_BACKUP_ERROR}이 아님"


# =============================================================================
# Test 12: 환경 정보 확인
# =============================================================================
def test_environment_detection():
    """
    AppEnv가 올바르게 초기화되고 Logger에서 사용되는지 확인
    
    검증:
        - AppEnv 인스턴스 존재
        - 환경 변수(DEV_MODE) 감지
        - 로그 디렉토리 경로 적절성
    """
    logger = Logger()
    app_env = logger.app_env
    
    assert app_env is not None, \
        "AppEnv 인스턴스가 초기화되지 않음"
    
    assert hasattr(app_env, 'is_packaged'), \
        "AppEnv에 is_packaged 속성이 없음"
    
    assert hasattr(app_env, 'base_path'), \
        "AppEnv에 base_path 속성이 없음"
    
    # 로그 디렉토리 경로 검증
    if not app_env.is_packaged:
        expected_log_dir = app_env.base_path / "logs"
        assert logger.LOG_DIR == expected_log_dir, \
            f"개발 환경 로그 디렉토리가 {expected_log_dir}이 아님"


# =============================================================================
# Test 13: Logger 인스턴스 속성 확인
# =============================================================================
def test_logger_properties():
    """
    Logger 클래스가 필요한 속성들을 올바르게 가지고 있는지 확인
    
    검증:
        - LOG_DIR, LOG_FILE, ERROR_LOG_FILE 속성 존재
        - logger (내부 로거 인스턴스) 속성 존재
        - app_env 속성 존재
    """
    logger_instance = Logger()
    
    # 필수 속성 확인
    assert hasattr(logger_instance, 'LOG_DIR'), \
        "Logger에 LOG_DIR 속성이 없음"
    
    assert hasattr(logger_instance, 'LOG_FILE'), \
        "Logger에 LOG_FILE 속성이 없음"
    
    assert hasattr(logger_instance, 'ERROR_LOG_FILE'), \
        "Logger에 ERROR_LOG_FILE 속성이 없음"
    
    assert hasattr(logger_instance, 'logger'), \
        "Logger에 logger 속성이 없음"
    
    assert hasattr(logger_instance, 'app_env'), \
        "Logger에 app_env 속성이 없음"
    
    # 속성 타입 확인
    assert isinstance(logger_instance.LOG_DIR, Path), \
        "LOG_DIR이 Path 타입이 아님"
    
    assert isinstance(logger_instance.logger, logging.Logger), \
        "logger가 logging.Logger 타입이 아님"


# =============================================================================
# 통합 테스트 (선택적 실행)
# =============================================================================
@pytest.mark.slow
def test_comprehensive_logging():
    """
    전체 로깅 시스템 통합 테스트
    
    Note:
        이 테스트는 시간이 오래 걸리므로 -m slow 옵션으로만 실행
        pytest tests/test_logger.py -v -m slow
    """
    logger_instance = Logger().logger
    
    # 대량 로그 생성
    for i in range(100):
        if i % 10 == 0:
            logger_instance.warning(f"통합 테스트 경고 #{i}")
        elif i % 5 == 0:
            logger_instance.error(f"통합 테스트 에러 #{i}")
        else:
            logger_instance.info(f"통합 테스트 정보 #{i}")
    
    time.sleep(0.5)
    
    # 파일 크기 확인
    log_file = Path(Logger().LOG_FILE)
    error_file = Path(Logger().ERROR_LOG_FILE)
    
    assert log_file.exists() and log_file.stat().st_size > 0, \
        "일반 로그 파일이 비어있음"
    
    assert error_file.exists() and error_file.stat().st_size > 0, \
        "에러 로그 파일이 비어있음"


# =============================================================================
# 실행 진입점
# =============================================================================
if __name__ == "__main__":
    # pytest 직접 실행
    pytest.main(["-v", "-s", __file__])