# utils/logger.py
"""
중앙 로깅 시스템
---------------
KRISS Robot Sync 프로젝트의 통합 로깅 솔루션

설계 원칙:
1. 단일 책임: Logger는 오직 로그 기록만 담당
2. 환경 설정 분리: LoggerConfig가 모든 설정 관리
3. EventBus 독립: Logger는 EventBus에 의존하지 않음
4. 확장성: 다양한 핸들러 추가 가능


사용법:
    from utils.logger import get_logger
    
    logger = get_logger(__name__)
    logger.info("정보 메시지")
    logger.info("작업 시작")
    logger.error("에러 발생", exc_info=True)
    logger.debug("디버그 정보")
"""

import sys
import os
import logging
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Optional

from .env import AppEnv


# =============================================================================
# 콘솔에서 컬러 출력을 위한 포매터
# =============================================================================
class ColorFormatter(logging.Formatter):
    """
    콘솔 출력용 ANSI 색상 포매터
    
    개발 환경에서 로그 레벨을 시각적으로 구분하기 위해 사용
    """
    
    COLORS = {
        'DEBUG': '\x1b[36m',      # Cyan
        'INFO': '\x1b[32m',       # Green
        'WARNING': '\x1b[33m',    # Yellow
        'ERROR': '\x1b[31m',      # Red
        'CRITICAL': '\x1b[35m',   # Magenta
        'RESET': '\x1b[0m'
    }
    
    def format(self, record: logging.LogRecord) -> str:
        """로그 레벨에 따라 색상 적용"""
        log_message = super().format(record)
        
        # TTY 환경 확인 (Windows에서도 작동)
        if hasattr(sys.stdout, 'isatty') and sys.stdout.isatty():
            color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
            return f"{color}{log_message}{self.COLORS['RESET']}"
        
        return log_message


# =============================================================================
# 로거 설정 관리 (단일 책임: 환경 설정)
# =============================================================================
class LoggerConfig:
    """
    로거 환경 설정 전담 클래스
    
    책임:
    - 로그 디렉토리 관리
    - 핸들러 생성
    - 포맷터 정의
    - 환경별 설정 분기
    
    Note:
        Logger 클래스와 완전히 분리되어 독립적으로 테스트 가능
    """
    
    _initialized = False
    
    # 앱 정보
    APP_NAME = "KRISS_ROBOT_SYNC"
    
    # 로그 파일 경로
    LOG_DIR: Path
    INFO_LOG: Path
    ERROR_LOG: Path
    
    # 포맷 정의
    DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
    MESSAGE_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    ERROR_FORMAT = "%(asctime)s | %(levelname)s | %(pathname)s:%(lineno)d\n%(message)s\n"
    
    # 로테이션 설정
    BACKUP_COUNT = 14        # 일반 로그: 14일 보관
    BACKUP_COUNT_ERROR = 30  # 에러 로그: 30일 보관
    

    @classmethod
    def _setup_log_config(cls, app_env: AppEnv):
        """
        로그 저장 환경 설정

        환경에 따른 저장 경로 설정, 로그파일 이름, 로그 폴더 생성
        """
        # --- 환경(개발/배포)에 맞는 로그 디렉토리 경로 설정 --- #
        if not app_env.is_packaged:
            # 개발 환경: 프로젝트 루트/logs
            cls.LOG_DIR = app_env.base_path / "logs"
        else:
            # 배포 환경: 실행 파일과 같은 위치
            cls.LOG_DIR = app_env.base_path

        # --- 로그 파일 경로 설정 --- #
        time_now = datetime.now().strftime("%Y%m%d")
        cls.INFO_LOG = cls.LOG_DIR / f"app_{time_now}.log"
        cls.ERROR_LOG = cls.LOG_DIR / "error.log"
        
        # --- 디렉토리 생성 --- #
        try:
            # parents=True: 중간 디렉토리도 생성, exist_ok=True: 폴더가 이미 있어도 에러 발생 안함
            cls.LOG_DIR.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            # 디렉토리 생성 실패 시, 로깅 시스템이 작동하기 전에 출력
            print(f"❌ 로그 디렉토리 생성 실패: {cls.LOG_DIR} - {e}")    


    @classmethod
    def initialize(cls):
        """
        로거 설정 초기화 (최초 1회만 실행)
        """

        # 이미 초기화되었으면 초기화 실행 안 하고 건너뜀
        if cls._initialized:
            return
        
        cls._initialized = True
        
        # 환경 감지
        app_env = AppEnv()

        # 로그 저장 설정
        cls._setup_log_config(app_env)
        
        # 외부 라이브러리 로그 걸러내기
        cls._suppress_noisy_loggers()


    @staticmethod
    def _suppress_noisy_loggers():
        """
        불필요한 외부 라이브러리 로그 억제(제외시키기)
        
        PyQt6, urllib3 등의 외부 라이브러리는 기본적으로 많은 로그를 출력
        과다 정보로 인해 로그를 읽기 어렵게 방해하기 때문
        """
        noisy_loggers = ["PyQt6", "urllib3", "PIL", "matplotlib"]
        for logger_name in noisy_loggers:
            logging.getLogger(logger_name).setLevel(logging.WARNING)
    
    
    @classmethod
    def get_log_level(cls) -> int:
        """
        환경 변수로 로그 레벨 동적 결정

            환경변수(LOG_LEVEL)를 읽어서 그 값에 따라 로그 레벨 결정
            환경변수에 값이 없으면 기본값 반환
            개발자가 임의로 로그 레벨을 결정할 수 있게 한다
        
        환경 변수 우선순위:
        1. LOG_LEVEL 환경 변수 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        2. 개발 환경: DEBUG
        3. 배포 환경: INFO
        
        사용 예:
            Windows: set LOG_LEVEL=DEBUG && python main.py
            Linux/Mac: LOG_LEVEL=DEBUG python main.py
        
        리턴:
            int: logging.DEBUG(10), INFO(20), WARNING(30), ERROR(40), CRITICAL(50)

        사용 예시:
        • Windows:
                C:> set LOG_LEVEL=DEBUG
                C:> python 파일이름.py

        • macOS / Linux (bash, zsh 등):
                $ export LOG_LEVEL=WARNING
                $ python 파일이름.py

        환경변수 취소 방법
                C:> set LOG_LEVEL=
                C:> python 파일이름.py            
        """

        # LOG_LEVEL 환경변수 읽기
        level_name = os.getenv("LOG_LEVEL", "").upper()
        
        if level_name and hasattr(logging, level_name):
            # 환경 변수로 지정된 경우 (예: LOG_LEVEL=DEBUG)
            # 10(=DEBUG 레벨)을 반환
            return getattr(logging, level_name)
        
        # 기본값: 개발모드는 DEBUG, 배포모드는 INFO
        
        # 순환 참조 방지를 위해 함수 내부에서 import
        try:
            from core.settings import SETTINGS
            # settings.ini의 DEBUG 값이 True면 DEBUG 레벨, False면 INFO 레벨
            if SETTINGS.app.debug:
                return logging.DEBUG
            else:
                return logging.INFO
        except ImportError:
            # 아직 core 모듈이 로딩되지 않았거나 단독 실행 시
            app_env = AppEnv()
            return logging.DEBUG if not app_env.is_packaged else logging.INFO
    


    ##################
    # --- 핸들러 --- #
    ##################
    @classmethod
    def create_file_handler(
        cls, 
        filepath: Path, 
        level: int,
        is_error_log: bool = False
    ) -> TimedRotatingFileHandler:
        """
        파일 핸들러 생성
        
        Args:
            filepath: 로그 파일 경로
            level: 로그 레벨 (logging.INFO, logging.ERROR 등)
            is_error_log: 에러 로그 여부 (포맷 선택용)
            
        Returns:
            TimedRotatingFileHandler: 자정마다 로테이션되는 핸들러
        """
        handler = TimedRotatingFileHandler(
            filename=filepath,
            when="midnight",    # 자정마다 로테이션
            interval=1,         # 1일마다 로테이션
            backupCount=cls.BACKUP_COUNT_ERROR if is_error_log else cls.BACKUP_COUNT,   # 일반:14일, 에러: 30일
            encoding="utf-8"
        )
        handler.setLevel(level)
        
        # 포맷 설정
        if is_error_log:
            fmt = logging.Formatter(cls.ERROR_FORMAT, cls.DATE_FORMAT)
        else:
            fmt = logging.Formatter(cls.MESSAGE_FORMAT, cls.DATE_FORMAT)
        
        handler.setFormatter(fmt)
        return handler

    @classmethod
    def create_console_handler(cls) -> logging.StreamHandler: # type: ignore
        """
        콘솔 핸들러 생성 (컬러 출력)
        
        Returns:
            StreamHandler: 컬러 포맷터가 적용된 핸들러
        """
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(cls.get_log_level())
        handler.setFormatter(ColorFormatter(cls.MESSAGE_FORMAT, cls.DATE_FORMAT))
        return handler



# =============================================================================
# 로거 싱글톤 (단일 책임: 로그 기록)
# =============================================================================
class Logger:
    """
    싱글톤 사용: 
        로그 설정(파일 위치, 포맷 등)은 앱 전체에서 딱 한 번만 세팅하면 되고, 모든 파일에서 똑같은 설정을 써야 하기 때문에

    책임:
    - 로그 기록만 수행
    - EventBus와 독립적
    - 모듈별 자식 로거 생성
    
    Note:
        직접 사용하지 말고 get_logger() 함수 사용 권장
    """
    
    # 싱글톤 디자인 패턴
    _instance: Optional['Logger'] = None    # Logger 클래스의 유일한 인스턴스(객체)를 저장하기 위한 공간
    _root_logger: Optional[logging.Logger] = None
    
    
    def __new__(cls):
        """
        인스턴스 중복 생성 방지

        이 클래스의 인스턴스가 계속 만들어지는 것을 방지하기 위해 
        부모의 생성자 메서드(object.__new__)를 오버라이딩
        """
        # 최초 요청할때만 객체 생성, 그 뒤로는 같은 인스턴스 리턴
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._setup_root_logger()
        return cls._instance
    
    
    def _setup_root_logger(self):
        """
        루트 로거 설정
        
        흐름:
        1. LoggerConfig 초기화
        2. 루트 로거 생성
        3. 핸들러 추가 (파일, 에러, 콘솔)
        4. 초기화 완료 로그
        """
        
        # 로거 설정 초기화
        LoggerConfig.initialize()

        
        # 루트 로거 생성
        self._root_logger = logging.getLogger(LoggerConfig.APP_NAME)
        self._root_logger.setLevel(LoggerConfig.get_log_level())
        self._root_logger.propagate = False
        
        # 기존 핸들러 제거 (중복 방지)
        self._root_logger.handlers.clear()
        
        # 핸들러 추가
        self._root_logger.addHandler(
            LoggerConfig.create_file_handler(
                LoggerConfig.INFO_LOG, 
                LoggerConfig.get_log_level(),
                is_error_log=False
            )
        )
        self._root_logger.addHandler(
            LoggerConfig.create_file_handler(
                LoggerConfig.ERROR_LOG, 
                logging.ERROR,
                is_error_log=True
            )
        )
        
        # 개발 모드에서만 콘솔 출력
        app_env = AppEnv()
        if not app_env.is_packaged:
            self._root_logger.addHandler(LoggerConfig.create_console_handler())
        
        # 초기화 완료 로그
        env_name = app_env.environment.value
        self._root_logger.info(
            f"Logger initialized in [{env_name}] environment - "
            f"Log directory: {LoggerConfig.LOG_DIR}"
        )
    
    
    def _get_child_logger(self, name: str) -> logging.Logger:
        """
        자식 로거 반환

        로그 메시지에 해당 로거의 이름(name)이 포함되도록 하여, 어떤 모듈이나 클래스에서 로그가 발생했는지(%(name)s 포맷) 쉽게 식별할 수 있도록
        
        Args:
            name: 로거 이름 (일반적으로 __name__ 사용)
            
        Returns:
            logging.Logger: 부모 설정이 상속된 로거
            
        Example:
            logger = Logger()._get_child_logger('models.fanuc_logic')
            logger.info("메시지")
            # 출력: 2025-01-20 10:30:00 | INFO | KRISS_ROBOT_SYNC.models.fanuc_logic | 메시지
        """
        # 루트 로거가 초기화되었음을 보장 (Pylance 경고 해결 및 런타임 안정성)
        assert self._root_logger is not None, "Root logger has not been initialized."
        
        return self._root_logger.getChild(name)


# =============================================================================
# 편의 함수
# =============================================================================
def get_logger(name: str = __name__) -> logging.Logger:
    """
    로거 인스턴스 반환

    엔드 유저가 사용하는 진입점 만들기 위해서
    

    Args:
        name: 로거 이름 (일반적으로 __name__)
        
    Returns:
        logging.Logger: 설정이 적용된 로거
        
    Example:
        from utils.logger import get_logger
        
        logger = get_logger(__name__)
        logger.info("작업 시작")
        logger.error("에러 발생", exc_info=True)
        logger.debug("디버그 정보")
    """
    logger_instance = Logger()
    return logger_instance._get_child_logger(name) # type: ignore


# 다른 파일에서 쓰기 편하게 하위 호환성을 위한 전역 로거
logger = get_logger(__name__)





"""
=============================================================================
-- Smoke Test --

python -m utils.logger
=============================================================================
"""

if __name__ == "__main__":
    print("\n" + "="*70)
    print("Logger 테스트")
    print("="*70 + "\n")
    
    # 테스트용 로거 생성
    test_logger = get_logger("test_module")
    
    # 모든 로그 레벨 테스트
    test_logger.debug("디버그 메시지 (개발 모드에서만 표시)")
    test_logger.info("정보 메시지")
    test_logger.warning("경고 메시지")
    test_logger.error("에러 메시지")
    test_logger.critical("치명적 에러 메시지")
    
    # 예외 로깅 테스트
    print("\n[예외 로깅 테스트]")
    try:
        raise ValueError("의도적인 테스트 예외")
    except ValueError:
        test_logger.exception("예외 발생:")
    
    # 로그 파일 위치 출력
    print(f"\n[로그 파일 위치]")
    print(f"로그 디렉토리: {LoggerConfig.LOG_DIR}")
    print(f"INFO 로그: {LoggerConfig.INFO_LOG}")
    print(f"ERROR 로그: {LoggerConfig.ERROR_LOG}")
    
    # 싱글톤 확인
    print(f"\n[싱글톤 확인]")
    logger1 = Logger()
    logger2 = Logger()
    print(f"동일 인스턴스: {logger1 is logger2}")
    
    print("\n" + "="*70)
    print("테스트 완료")
    print("="*70 + "\n")
