# core/application.py
"""
App Engine (애플리케이션 부트스트래퍼)
----------------------------------
QApplication을 감싸는 싱글톤 래퍼 클래스

앱 전체를 시작·설정·종료하는 책임을 가진 App Engine(인프라스트럭쳐 레이어)

View, ViewModel, Service, Worker 들의 상위 계층


역할:
- 앱 전체 초기화 (부트스트랩)
- 생명주기 관리 (시작 → 실행 → 종료)
- 전역 시스템 설정 (로깅, 예외 처리, 테마)
- 싱글톤 보장 (QApplication 중복 방지)

설계 원칙:
- 단일 책임: 초기화와 생명주기 관리만
- 의존성 주입: LogListener 외부에서 주입
- 명확한 초기화 순서
- 우아한 종료 (Graceful Shutdown)

사용법:
    from core.application import AppEngine
    from core.log_listener import LogListener
    
    # 1. AppEngine 생성
    app = AppEngine()
    
    # 2. LogListener 초기화
    log_listener = LogListener()
    
    # 3. 메인 윈도우 실행
    window = MainWindow()
    window.show()
    
    # 4. 이벤트 루프 시작
    sys.exit(app.exec())
"""

import sys
import logging
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import QApplication

from utils.logger import get_logger
from core.exception_handler import install_global_exception_hook
from core.event_bus import EVENT_BUS
from config.paths import STYLESHEET_PATH
from styles.style_manager import load_and_apply_stylesheet
from utils.file_exceptions import FileOperationError




# =============================================================================
# AppEngine (애플리케이션 래퍼)
# =============================================================================
class AppEngine(QApplication):
    """
    QApplication을 감싸는 싱글톤 래퍼
    
    특징:
    - 싱글톤 패턴으로 중복 생성 방지
    - 전역 시스템 컴포넌트 자동 초기화
    - 우아한 종료 처리
    
    초기화 순서:
    1. Logger 초기화
    2. 전역 예외 훅 설치
    3. QApplication 초기화
    4. 스타일시트 로드
    5. EventBus 연결 (aboutToQuit)
    
    Note:
        LogListener는 외부에서 생성해야 함 (의존성 주입)
    """
    
    # 싱글톤 패턴
    _instance: Optional['AppEngine'] = None
    _initialized: bool = False
    
    
    def __new__(cls, *args, **kwargs) -> "AppEngine":
        """
        싱글톤 인스턴스 생성
        
        흐름:
        1. 기존 QApplication 인스턴스 확인
        2. 없으면 새로운 AppEngine 생성
        3. 있으면:
            - AppEngine이면 재사용
            - 다른 QApplication이면 에러
        
        Returns:
            AppEngine: 유일한 인스턴스
            
        Raises:
            TypeError: 다른 QApplication 인스턴스가 이미 존재하는 경우
        """

        # 싱글톤 패턴
        # 이미 AppEngine 인스턴스가 있으면 반환
        if cls._instance is not None:
            return cls._instance
        
        # Logger 초기화
        # 아직 LogListener가 연결되지 않았으므로 직접 로깅
        logger = get_logger(__name__)
        
        # 기존 QApplication 인스턴스 확인
        existing_instance = QApplication.instance()
        
        if existing_instance is None:
            # 새로운 AppEngine 생성
            logger.info("AppEngine 인스턴스 생성 중...")
            cls._instance = super().__new__(cls)
            
        elif isinstance(existing_instance, cls):
            # 이미 AppEngine 인스턴스가 존재
            logger.info("기존 AppEngine 인스턴스 재사용")
            cls._instance = existing_instance

        else:
            # 다른 QApplication이 이미 존재 (에러)
            error_msg = (
                "QApplication 인스턴스가 이미 존재하지만 AppEngine이 아닙니다. "
                "AppEngine을 먼저 생성해야 합니다."
            )
            logger.error(error_msg)
            raise TypeError(error_msg)
        
        return cls._instance


    def __init__(self, argv=None):
        """
        AppEngine 초기화

        EventBus나 Settings 클래스처럼 _initialize 메서드를 따로 만들고 __new__에서 호출하는 방식이 가장 깔끔하지만, 이 클래스가 상속하는 QApplication은 C++ 레벨의 초기화 문제 때문에 __init__에서 super().__init__을 부르는 현재 방식이 더 안정적일 수 있다


        Args:
            argv: 커맨드 라인 인자 (None이면 sys.argv 사용)

        이 메서드는 너무 빨리 실행되기 때문에 EVENT BUS 아닌 직접 로그
        """

        # (방어코드) 초기화는 1회만 수행
        # _initialized 플래그 사용
        if AppEngine._initialized:
            return
        
        # 아직 LogListener가 연결되지 않았으므로 직접 로깅
        self.logger = get_logger(__name__)
        
        try:
            # QApplication 초기화
            super().__init__(argv or sys.argv)
            self.logger.info("QApplication 초기화 완료")
            
        except Exception as e:
            self.logger.critical(
                f"❌ QApplication 초기화 실패: {e}",
                exc_info=True
            )
            raise

        # --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- #
        # 실제 초기화를 담당하는 bootstrap 메서드는 `./main.py` 에서 호출
        # --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- --- #

        # aboutToQuit 시그널 연결 (앱 종료 시 정리)
        self.aboutToQuit.connect(self._shutdown)

        # 초기화 완료
        AppEngine._initialized = True


    def bootstrap(self):
        """
        앱의 실제 초기화 로직 (LogListener 연결 후 호출됨)

        여기서부터는 EVENT_BUS를 사용하여 로그를 남길 수 있다
        """

        EVENT_BUS.system_info.emit("시스템 부트스트랩 시작...")
        
        # 전역 예외 훅 설치
        self._install_exception_hook()

        # 스타일시트 로드
        self._load_stylesheet()

        EVENT_BUS.system_info.emit("시스템 부트스트랩 완료")


    def _install_exception_hook(self):
        """
        전역 예외 훅 설치
        
        처리되지 않은 예외를 자동으로 로깅
        """
        try:
            install_global_exception_hook()
            EVENT_BUS.ui_log_message.emit(
                "전역 예외 훅 설치됨", "INFO"
            )
        except Exception as e:
            EVENT_BUS.ui_log_message.emit(
                f"❌ 전역 예외 훅 설치 실패: {e}", "ERROR"
            )


    def _load_stylesheet(self):
        """
        전역 스타일시트 로드 및 적용 (theme.py 활용)
        """

        try:
            load_and_apply_stylesheet(self, STYLESHEET_PATH)
            EVENT_BUS.ui_log_message.emit(
                f"스타일시트 로드됨: {STYLESHEET_PATH.name}", "INFO"
            )
        except FileOperationError as e:
            EVENT_BUS.ui_log_message.emit(
                f"  ⚠ 스타일시트 로드 실패: {e}", "WARNING"
            )
        except Exception as e:
            EVENT_BUS.ui_log_message.emit(
                f"  ⚠ 스타일시트 적용 중 알 수 없는 오류: {e}", "ERROR"
            )


    def _shutdown(self):
        """
        앱 종료 시 정리 작업
        
        순서:
        1. 종료 이벤트 발행
        2. EventBus 시그널 연결 해제
        3. 로깅 시스템 종료
        
        Note:
            aboutToQuit 시그널에 의해 자동 호출됨
        """

        EVENT_BUS.ui_log_message.emit("앱 종료 시작...", "INFO")

        # 모든 모듈에게 "종료 준비"라고 방송
        EVENT_BUS.app_shutting_down.emit()
        EVENT_BUS.ui_log_message.emit("종료 이벤트 발행됨", "INFO")
        
        try:
            # EVENT BUS 정리
            EVENT_BUS.disconnect_all()

            # 이제 EventBus가 끊겼으므로 직접 로깅으로 전환
            self.logger.info("EventBus 시그널 연결 해제됨")
            
        except Exception as e:
            self.logger.warning(f"  ⚠ EVENT BUS 정리 실패: {e}")

        self.logger.info("시스템 완전 종료")
        logging.shutdown()





# =============================================================================
# Smoke Test
"""
python -m core.application
"""
# =============================================================================
if __name__ == "__main__":
    from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
    from PyQt6.QtCore import Qt
    
    print("\n" + "="*70)
    print("AppEngine 테스트 (Refactored)")
    print("="*70 + "\n")
    
    # 1. AppEngine 생성 (1단계: 껍데기 생성)
    print("1️⃣  AppEngine 인스턴스 생성:")
    app = AppEngine(sys.argv)
    
    # 2. 싱글톤 확인
    print("\n2️⃣  싱글톤 패턴 확인:")
    app2 = AppEngine()
    print(f"   app1 ID: {id(app)}")
    print(f"   app2 ID: {id(app2)}")
    is_singleton = app is app2
    print(f"   동일 인스턴스: {is_singleton}")
    
    if not is_singleton:
        print("   ❌ 싱글톤 테스트 실패!")
        sys.exit(1)
    else:
        print("   ✅ 싱글톤 테스트 성공")
    
    # 3. LogListener 초기화 (2단계: 귀 열기)
    print("\n3️⃣  LogListener 초기화 (필수):")
    try:
        from core.log_listener import LogListener
        log_listener = LogListener()
        print("   ✅ LogListener 연결 완료 (EventBus 수신 대기 중)")
    except ImportError as e:
        print(f"   ❌ LogListener 로드 실패: {e}")
        sys.exit(1)

    # 4. Bootstrap 실행 (3단계: 실제 로직 실행)
    print("\n4️⃣  Bootstrap 실행 (초기화 로직):")
    print("   (로그 파일에 '시스템 부트스트랩 완료'가 찍혀야 함)")
    app.bootstrap()
    print("   ✅ Bootstrap 호출 완료")
    
    # 5. 테스트 윈도우 생성
    print("\n5️⃣  테스트 윈도우 생성:")
    window = QWidget()
    window.setWindowTitle("AppEngine 테스트")
    window.setGeometry(100, 100, 400, 250)
    
    layout = QVBoxLayout()
    
    label = QLabel(
        "AppEngine 테스트 윈도우\n\n"
        "✅ 확인 사항:\n"
        "1. 콘솔/로그 파일에 초기화 로그가 찍혔는가?\n"
        "2. 스타일시트가 적용되었는가? (배경색 등)\n"
        "3. 종료 시 '시스템 완전 종료' 로그가 남는가?"
    )
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    
    quit_button = QPushButton("테스트 종료")
    quit_button.clicked.connect(app.quit)
    
    layout.addWidget(label)
    layout.addWidget(quit_button)
    
    window.setLayout(layout)
    window.show()
    
    print("   ✅ 테스트 윈도우 표시됨")
    
    # 6. 이벤트 루프 시작
    print("\n6️⃣  이벤트 루프 시작...")
    print("="*70 + "\n")
    
    exit_code = app.exec()
    
    print("\n" + "="*70)
    print(f"앱 종료됨 (종료 코드: {exit_code})")
    print("="*70 + "\n")
    
    sys.exit(exit_code)
