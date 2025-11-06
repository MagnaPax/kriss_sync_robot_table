# utils/logger.py
"""
utils/logger.py
----------------
중앙 로깅 설정 모듈.
모든 모듈에서 import 해서 사용:
    from utils.logger import logger
"""
import sys, os
import logging
import logging.config
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from .env import AppEnv



# =============================================================================
# 콘솔 컬러 출력을 위한 ANSI 색상 코드
# =============================================================================
class ColorFormatter(logging.Formatter):
    """
    콘솔 출력용 컬러 포매터 (ANSI 색상 코드 사용)
    """
    
    # ANSI 색상 코드
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'        # Reset
    }
    
    def format(self, record: logging.LogRecord) -> str:
        """로그 레벨에 따라 색상 적용"""
        # 원본 포맷 적용
        log_message = super().format(record)
        
        # 색상 적용 (Windows에서도 작동하도록 조건부)
        if hasattr(sys.stdout, 'isatty') and sys.stdout.isatty():
            color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
            return f"{color}{log_message}{self.COLORS['RESET']}"
        
        return log_message




class Logger:
    """
    클래스가 앱 전체에서 단 하나의 인스턴스(객체)만 갖도록 보장하는 
    싱글톤(Singleton) 디자인 패턴
    
    특징:
    - 개발/배포 환경 자동 감지(utils/env.py)
    - 일반 로그 / 에러 로그 분리
    - 컬러 콘솔 출력 (개발 모드)
    - 환경 변수로 로그 레벨 조정
    """    

    # 싱글톤 디자인 패턴
    _instance = None        # Logger 클래스의 유일한 인스턴스(객체)를 저장하기 위한 공간
    _initialized = False    # 초기화 코드가 여러번 실행되는 것을 방지하는 flag 변수(스위치)

    # 앱 정보
    APP_NAME = "KRISS_ROBOT_SYNC"
    APP_AUTHOR = "KRISS"

    # 로그 디렉터리
    LOG_DIR: Path
    LOG_FILE: Path
    ERROR_LOG_FILE: Path

    # 포멧터 정의
    FORMAT_DATE = "%Y-%m-%d %H:%M:%S"
    FORMAT_MESSAGE = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    LOG_FORMAT_FILE = logging.Formatter(
        fmt=FORMAT_MESSAGE, 
        datefmt=FORMAT_DATE
    )
    LOG_FORMAT_ERROR = logging.Formatter(
        fmt='%(asctime)s | %(levelname)s | %(pathname)s:%(lineno)d\n%(message)s\n',
        datefmt=FORMAT_DATE
    )
    LOG_FORMAT_CONSOLE = ColorFormatter(
        fmt=FORMAT_MESSAGE,
        datefmt=FORMAT_DATE
    )
    
    # 로테이션 설정
    COUNT_BACKUP = 14       # 14일치 보관
    COUNT_BACKUP_ERROR = 30 # 30일치 보관


    def __new__(cls) -> "Logger":
        """
        싱글톤 패턴 구현
        """
        # 1. 클래스 변수 _instance가 비어있는지(None) 확인
        if cls._instance is None:
            # 2. 비어있다면 (최초 호출이라면), 부모 클래스의 __new__를 호출하여
            #    새로운 인스턴스를 생성하고, 그 결과를 _instance에 저장
            cls._instance = super().__new__(cls)
        
        # 3. _instance에 저장된 인스턴스를 반환
        return cls._instance


    def __init__(self) -> None:
        """로거 초기화 (최초 1회만 실행 - 여러번 실행 방지)"""
        if Logger._initialized:
            return
        Logger._initialized = True

        # 외부 라이브러리에서 나오는 불필요한 로그 정보 제외시키기(로그 레벨 억제)
        logging.getLogger("PyQt6").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("PIL").setLevel(logging.WARNING)
        logging.getLogger("matplotlib").setLevel(logging.WARNING)

        # AppEnv 인스턴스 가져오기
        self.app_env = AppEnv()

        # 로그 파일 저장 위치 설정
        self._configure_logging()

        # 로거 생성(Logger 클래스 객체에 핸들러 등록)
        self._attach_handlers()




    ###################################
    # --- 로그파일 저장 위치 설정 --- #
    ###################################
    def _get_log_directory(self) -> Path:
        """개발환경or배포환경에 따른 로그 디렉토리 설정"""
        if not self.app_env.is_packaged:
            # 개발환경
            return self.app_env.base_path / "logs"
        else:
            # 배포환경
            return self.app_env.base_path

    def _configure_logging(self) -> None:
        """로그 디렉토리 설정 및 로그 파일 경로 설정"""
        # 로그 디렉토리 결정
        self.LOG_DIR: Path = self._get_log_directory()

        # 로그 디렉토리 생성
        try:
            # parents=True: 필요한 모든 상위 디렉터리 생성
            # exist_ok=True: 디렉터리가 이미 있어도 에러 X
            self.LOG_DIR.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            print(f"❌ 로그 디렉터리 생성 실패: {self.LOG_DIR} - {e}")

        # 로그 파일 경로 설정
        self.LOG_FILE = self.LOG_DIR / f"app_{datetime.now():%Y%m%d}.log"   # 개발 편의성 위한 날짜 표시
        self.ERROR_LOG_FILE: Path = self.LOG_DIR / "error.log"



    ##################
    # --- Helper --- #
    ##################
    def _determine_log_level(self) -> int:
        """
        환경변수(LOG_LEVEL)를 읽어서 그 값에 따라 로그 레벨 결정
        환경변수에 값이 없으면 기본값 반환
        개발자가 임의로 로그 레벨을 결정할 수 있게 한다

        사용 예시:
          • Windows:
                C:\> set LOG_LEVEL=DEBUG
                C:\> python 파일이름.py

          • macOS / Linux (bash, zsh 등):
                $ export LOG_LEVEL=WARNING
                $ python 파일이름.py

        환경변수 취소 방법
                C:\> set LOG_LEVEL=
                C:\> python 파일이름.py

        반환:
            int: logging.DEBUG(10), logging.INFO(20) 등
        """
        # LOG_LEVEL 환경변수 읽기
        level_name = os.getenv("LOG_LEVEL", "").upper()
        
        if level_name and hasattr(logging, level_name):
            # 환경 변수로 지정된 경우 (예: LOG_LEVEL=DEBUG)
            # 10(=DEBUG 레벨)을 반환
            return getattr(logging, level_name)
        else:
            # 기본값: 개발모드는 DEBUG, 배포모드는 INFO
            return logging.DEBUG if not self.app_env.is_packaged else logging.INFO




    ##################
    # --- 핸들러 --- #
    ##################
    def _create_file_handler(self) -> TimedRotatingFileHandler:
        """일반 로그 파일 핸들러 생성 (INFO 이상)"""
        handler = TimedRotatingFileHandler(
            filename=self.LOG_FILE,
            when="midnight",                # 자정마다 로테이션
            interval=1,                     # 1일 간격
            backupCount=self.COUNT_BACKUP,  # 지정 날짜만큼 보관
            encoding="utf-8"
        )
        handler.setLevel(logging.INFO)
        handler.setFormatter(self.LOG_FORMAT_FILE)
        return handler

    def _create_error_handler(self) -> TimedRotatingFileHandler:
        """에러만 기록 (WARNING 이상)"""
        handler = TimedRotatingFileHandler(
            filename=self.ERROR_LOG_FILE,
            when="midnight",
            interval=1,
            backupCount=self.COUNT_BACKUP_ERROR,
            encoding="utf-8"
        )
        handler.setLevel(logging.WARNING)
        handler.setFormatter(self.LOG_FORMAT_ERROR)
        return handler

    def _create_console_handler(self) -> logging.StreamHandler:
        """콘솔 출력 핸들러 (개발용, DEBUG 레벨)"""
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(self._determine_log_level())
        handler.setFormatter(self.LOG_FORMAT_CONSOLE)
        return handler

    def _attach_handlers(self) -> None:
        """핸들러들을 로거에 등록"""
        self.logger = logging.getLogger(Logger.APP_NAME)
        self.logger.setLevel(self._determine_log_level())
        self.logger.propagate = False   # 중복 출력 방지

        # 핸들러 중복 등록 방지
        if not self.logger.hasHandlers():
            self.logger.addHandler(self._create_file_handler())
            self.logger.addHandler(self._create_error_handler())

            # 개발 모드일 때 콘솔 핸들러 추가
            if not self.app_env.is_packaged:
                self.logger.addHandler(self._create_console_handler())

