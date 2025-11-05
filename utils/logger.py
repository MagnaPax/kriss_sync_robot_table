# utils/logger.py
"""
utils/logger.py
----------------
중앙 로깅 설정 모듈.
모든 모듈에서 import 해서 사용:
    from utils.logger import logger
"""
import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from .env import app_env, LogLevel


class Logger:

    # 싱글톤 디자인 패턴
    _instance = None        # Logger 클래스의 유일한 인스턴스(객체)를 저장하기 위한 공간
    _initialized = False    # 초기화 코드가 여러번 실행되는 것을 방지하는 flag 변수(스위치)


    # 로그 디렉터리
    LOG_DIR: Path
    LOG_FILE: Path
    ERROR_LOG_FILE: Path

    # 포멧터 정의
    DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

    LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

    FILE_FORMAT = logging.Formatter(
        fmt = LOG_FORMAT, 
        datefmt = DATE_FORMAT
    )

    CONSOLE_FORMAT = logging.Formatter(
        fmt = LOG_FORMAT
    )

    ERROR_FORMAT = logging.Formatter(
        fmt = '%(asctime)s | %(levelname)s | %(pathname)s:%(lineno)d\n%(message)s\n',
        datefmt = DATE_FORMAT
    )
    
    def __new__(cls):
        """
        클래스가 앱 전체에서 단 하나의 인스턴스(객체)만 갖도록 보장하는 
        싱글톤(Singleton) 디자인 패턴 구현
        """
        # 1. 클래스 변수 _instance가 비어있는지(None) 확인
        if cls._instance is None:
            # 2. 비어있다면 (최초 호출이라면), 부모 클래스의 __new__를 호출하여
            #    새로운 인스턴스를 생성하고, 그 결과를 _instance에 저장
            cls._instance = super().__new__(cls)
        
        # 3. _instance에 저장된 인스턴스를 반환
        return cls._instance


    def __init__(self) -> None:
        # 초기화(__init__ 메서드)가 여러번 실행되는 것 방지
        if self._initialized:
            return
        self._initialized = True

        # 로그 디렉토리 결정 및 인스턴스 속성으로 저장
        self.LOG_DIR: Path = self._get_log_directory()

        # 로그 디렉토리 생성
        try:
            # parents=True: 필요한 모든 상위 디렉터리 생성
            # exist_ok=True: 디렉터리가 이미 있어도 에러 X
            self.LOG_DIR.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            print(f"❌ 로그 디렉터리 생성 실패: {self.LOG_DIR} - {e}")

        # 로그 파일 경로 설정
        self.LOG_FILE: Path = self.LOG_DIR / "app.log"
        self.ERROR_LOG_FILE: Path = self.LOG_DIR / "error.log"

        # 핸들러 캐시
        self._handlers = {}     # 로그 메세지를 특정대상(파일,콘솔)으로 보냄
        self._formatters = {}   # 로그 메세지의 형태 지정


    def _get_log_directory(self) -> Path:
        if not app_env.is_packaged:
            # 개발환경
            return app_env.base_path / "logs"
        else:
            # 배포환경
            return app_env.base_path

