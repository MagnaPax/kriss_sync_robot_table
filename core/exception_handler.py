# core/exception_handler.py
"""
전역 예외 처리기
---------------
처리되지 않은 모든 예외를 자동으로 캐치하여 로깅

역할:
- sys.excepthook 교체
- try-except 없이도 예외 추적
- 앱 크래시 시 자동 로그 기록
- EventBus를 통한 UI 알림 (선택적)

설계 원칙:
- Logger와 독립적
- EventBus와 느슨한 결합
- 중복 설치 방지

사용법:
    # main.py에서 앱 시작 시 한 번만 호출

    from core.exception_handler import install_global_exception_hook
    
    install_global_exception_hook()
"""

import sys
from types import TracebackType
from typing import Type, Optional

from utils.logger import get_logger


# =============================================================================
# 전역 상태 관리
# =============================================================================
_installed = False
_logger = None


# =============================================================================
# 전역 예외 훅
# =============================================================================
def install_global_exception_hook():
    """
    처리되지 않은 모든 예외를 가로채 로깅하기 위한 전역 훅 설치
    
    특징:
    - 멱등성: 여러 번 호출해도 한 번만 설치됨
    - KeyboardInterrupt 처리: Ctrl+C는 정상 종료로 간주
    - EventBus 연동: UI에 에러 알림 전송 (선택적)
    
    Note:
        앱 진입점(main.py)에서 한 번만 호출해야 함
    
    Example:
        >>> from core.exception_handler import install_global_exception_hook
        >>> install_global_exception_hook()
        >>> # 이후 모든 처리되지 않은 예외가 자동으로 로그 기록
    """
    global _installed, _logger
    
    # 중복 설치 방지
    if _installed:
        return
    
    # Logger 인스턴스 생성 (모듈 레벨)
    _logger = get_logger(__name__)
    
    # 원래의 예외 훅 백업
    original_hook = sys.excepthook
    
    def _global_exception_hook(
        exc_type: Type[BaseException],
        exc_value: BaseException,
        exc_traceback: Optional[TracebackType]
    ):
        """
        실제 예외 처리 함수 (sys.excepthook에 의해 자동 호출)
        
        Args:
            exc_type: 예외 타입 (예: ValueError, ZeroDivisionError)
            exc_value: 예외 인스턴스
            exc_traceback: 트레이스백 객체
        """
        # KeyboardInterrupt는 정상 종료로 간주
        if issubclass(exc_type, KeyboardInterrupt):
            original_hook(exc_type, exc_value, exc_traceback)
            return
        
        # _logger가 초기화되었음을 보장 (Pylance 경고 해결 및 런타임 안정성)
        assert _logger is not None, "Global exception handler's logger is not initialized."
        
        # 예외 정보 로깅
        _logger.critical(
            "🚨 처리되지 않은 예외 발생 (Unhandled Exception)",
            exc_info=(exc_type, exc_value, exc_traceback)
        )
        
        # EventBus를 통한 UI 알림 (선택적)
        try:
            from core.event_bus import EVENT_BUS
            error_message = f"{exc_type.__name__}: {exc_value}"
            EVENT_BUS.system.error.emit(error_message)
        except ImportError:
            # EventBus가 없으면 무시
            pass
        except Exception as e:
            # EventBus 호출 실패해도 원래 예외 로깅은 완료되어야 함
            _logger.warning(f"EventBus 알림 실패: {e}")
        
        # 원래의 예외 훅 호출 (프로그램 종료)
        original_hook(exc_type, exc_value, exc_traceback)
    
    # sys.excepthook 교체
    sys.excepthook = _global_exception_hook
    
    _logger.info("전역 예외 훅 설치 완료")
    _installed = True


def uninstall_global_exception_hook():
    """
    전역 예외 훅 제거 (테스트용)
    
    Note:
        일반적으로 사용할 필요 없음. 테스트 환경에서만 사용
    """
    global _installed
    
    if not _installed:
        return
    
    # sys.excepthook를 기본값으로 복원
    sys.excepthook = sys.__excepthook__
    
    if _logger:
        _logger.info("전역 예외 훅 제거 완료")
    
    _installed = False


def is_installed() -> bool:
    """
    전역 예외 훅 설치 여부 확인
    
    Returns:
        bool: 설치되어 있으면 True
    """
    return _installed








# =============================================================================
# --- Smoke Test --- #
"""
python -m core.exception_handler
"""
# =============================================================================
if __name__ == "__main__":
    print("\n" + "="*70)
    print("Exception Handler 테스트")
    print("="*70 + "\n")
    
    # 1. 예외 훅 설치
    print("1️⃣  전역 예외 훅 설치:")
    install_global_exception_hook()
    print(f"   설치 상태: {is_installed()}")
    
    # 2. 중복 설치 테스트
    print("\n2️⃣  중복 설치 테스트:")
    install_global_exception_hook()  # 두 번째 호출
    print("   중복 설치 방지 확인 완료")
    
    # 3. 처리되지 않은 예외 테스트
    print("\n3️⃣  처리되지 않은 예외 발생:")
    print("   (다음 줄에서 에러가 발생하며 자동으로 로그 기록됩니다)\n")
    
    # 의도적으로 예외 발생
    # → 이 예외는 try-except 없이 발생하므로
    # → _global_exception_hook이 자동으로 캐치하여 로그 기록
    x = 1 / 0  # ZeroDivisionError
    
    print("\n" + "="*70)
    print("이 줄은 실행되지 않습니다 (위에서 예외 발생)")
    print("="*70 + "\n")