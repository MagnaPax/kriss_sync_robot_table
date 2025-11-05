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

from .env import app_env, LogLevel


class Logger:

    # app_env 인스턴스를 사용하여 기본 경로를 가져온 후 'logs' 폴더를 지정
    LOG_DIR = app_env.base_path / "logs"

    # 로그 파일 저장 디렉토리 생성
    try:
        # parents=True: 필요한 모든 상위 디렉터리 생성
        # exist_ok=True: 디렉터리가 이미 있어도 에러 X
        LOG_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"❌ 로그 디렉터리 생성 실패: {LOG_DIR} - {e}")


    def __init__(self) -> None:
        pass