# demo_logger.py
import logging
import os
from datetime import datetime

class FanucLogger:
    """
    FANUC Robot Control Demo 애플리케이션 전체에서 사용할 로깅 클래스.
    - 콘솔 출력과 파일 저장을 동시에 수행한다

    사용법:
        from demo_logger import logger

        logger.info("애플리케이션이 시작되었습니다.")
        logger.warning("이 값은 곧 만료될 예정입니다.")
        logger.error("예상치 못한 오류가 발생했습니다.")
    """
    def __init__(self, name='FanucDemoApp', log_file='fanuc_demo.log', level=logging.DEBUG):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        self.log_file = log_file

        # 핸들러가 중복 등록되는 것을 방지
        if not self.logger.handlers:

            # 파일 핸들러 (로그 파일에 저장)
            file_handler = logging.FileHandler(self.log_file, encoding='utf-8')

            # 메세지 포맷
            # [2025-11-19 11:20:03.123] [INFO] message
            file_format = logging.Formatter(
                '[%(asctime)s.%(msecs)03d] [%(levelname)s] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )

            file_handler.setFormatter(file_format)
            self.logger.addHandler(file_handler)

            # 콘솔 핸들러 (CLI 출력)
            console_handler = logging.StreamHandler()
            console_format = logging.Formatter('%(message)s') # 콘솔 출력은 간략하게
            console_handler.setFormatter(console_format)
            self.logger.addHandler(console_handler)

    def log_info(self, message):
        self.logger.info(message)

    def log_warning(self, message):
        self.logger.warning(message)

    def log_error(self, message):
        self.logger.error(message)

    def log_exception(self, message, exc: Exception):
        # exc_info=True를 사용하여 스택 트레이스를 포함
        self.logger.error(f"{message} - {type(exc).__name__}: {str(exc)}", exc_info=True)


# 전역 로거 인스턴스 (다른 파일에서 사용하기 편하게 / Singleton 패턴처럼 사용)
logger = FanucLogger().logger