# core/exception_handler.py
import sys
from types import TracebackType
from typing import Type

from utils.logger import Logger


# 중복 설치 방지
_installed = False


def install_global_exception_hook():
    """
    처리되지 않은 모든 예외를 가로채 로깅하기 위한 전역 훅(hook)을 설치합니다.

    이 함수는 애플리케이션의 진입점(AppEngine)에서 한 번만 호출되어야 합니다.
    """
    global _installed
    if _installed:
        return

    original_hook = sys.excepthook

    @staticmethod
    def _global_exception_hook(
        exc_type: Type[BaseException],
        exc_value: BaseException,
        exc_traceback: TracebackType | None
    ):
        """
        실제로 예외를 처리하는 함수. sys.excepthook에 의해 호출됩니다.
        """
        # 사용자가 Ctrl+C로 종료한 경우는 일반적인 종료로 간주하고,
        # 원래의 예외 처리 방식에 따라 프로그램을 종료
        if issubclass(exc_type, KeyboardInterrupt):
            original_hook(exc_type, exc_value, exc_traceback)
            return

        # 그 외 모든 처리되지 않은 예외는 CRITICAL 레벨로 로그 남긴다
        Logger().logger.critical(
            "Unhandled application exception occurred",
            exc_info=(exc_type, exc_value, exc_traceback)
        )

    # 파이썬의 전역 예외 처리기를 이 함수로 교체
    sys.excepthook = _global_exception_hook
    Logger().logger.info("Global exception hook installed.")

    _installed = True
