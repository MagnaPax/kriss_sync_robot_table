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

# 설정 파일 경로
try:
    from config.paths import STYLESHEET_PATH
except ImportError:
    # 설정 파일이 없으면 기본 경로 사용
    STYLESHEET_PATH = Path("styles/stylesheet.qss")


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
        # 이미 AppEngine 인스턴스가 있으면 반환
        if cls._instance is not None:
            return cls._instance
        
        # Logger 먼저 초기화 (에러 로깅 위해)
        logger = get_logger(__name__)
        
        # 기존 QApplication 인스턴스 확인
        existing_instance = QApplication.instance()
        
        if existing_instance is None:
            # 새로운 AppEngine 생성
            logger.info("🚀 AppEngine 인스턴스 생성 중...")
            cls._instance = super().__new__(cls)
            
        elif isinstance(existing_instance, cls):
            # 이미 AppEngine 인스턴스가 존재
            logger.info("✅ 기존 AppEngine 인스턴스 재사용")
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
        
        Args:
            argv: 커맨드 라인 인자 (None이면 sys.argv 사용)
            
        Note:
            싱글톤 패턴으로 여러 번 호출될 수 있으므로
            _initialized 플래그로 실제 초기화는 1회만 수행
        """
        # 이미 초기화되었으면 리턴
        if AppEngine._initialized:
            return
        
        # Logger 인스턴스 생성
        self.logger = get_logger(__name__)
        
        try:
            # QApplication 초기화
            super().__init__(argv or sys.argv)
            self.logger.info("✅ QApplication 초기화 완료")
            
        except Exception as e:
            self.logger.critical(
                f"❌ QApplication 초기화 실패: {e}",
                exc_info=True
            )
            raise
        
        # 초기화 시퀀스
        self._initialize_components()
        
        # aboutToQuit 시그널 연결 (앱 종료 시 정리)
        self.aboutToQuit.connect(self._shutdown)
        
        # 초기화 완료
        AppEngine._initialized = True
        self.logger.info("🎉 AppEngine 초기화 완료")
    
    
    def _initialize_components(self):
        """
        전역 시스템 컴포넌트 초기화
        
        순서:
        1. 전역 예외 훅 설치
        2. 스타일시트 로드
        3. EventBus 로드 확인
        
        Note:
            LogListener는 외부에서 생성해야 함
        """
        self.logger.info("📦 시스템 컴포넌트 초기화 시작...")
        
        # 1. 전역 예외 훅 설치
        self._install_exception_hook()
        
        # 2. 스타일시트 로드
        self._load_stylesheet()
        
        # 3. EventBus 로드 확인
        self._verify_event_bus()
        
        self.logger.info("✅ 시스템 컴포넌트 초기화 완료")
    
    
    def _install_exception_hook(self):
        """
        전역 예외 훅 설치
        
        처리되지 않은 예외를 자동으로 로깅
        """
        try:
            install_global_exception_hook()
            self.logger.info("  ✓ 전역 예외 훅 설치됨")
        except Exception as e:
            self.logger.warning(f"  ⚠ 전역 예외 훅 설치 실패: {e}")
    
    
    def _load_stylesheet(self):
        """
        전역 스타일시트 로드 및 적용
        
        설정:
            STYLESHEET_PATH에서 QSS 파일 로드
        """
        if not STYLESHEET_PATH.exists():
            self.logger.warning(f"  ⚠ 스타일시트 파일 없음: {STYLESHEET_PATH}")
            return
        
        try:
            with open(STYLESHEET_PATH, "r", encoding="utf-8") as file:
                stylesheet = file.read()
                self.setStyleSheet(stylesheet)
            
            self.logger.info(f"  ✓ 스타일시트 로드됨: {STYLESHEET_PATH.name}")
            
        except Exception as e:
            self.logger.warning(f"  ⚠ 스타일시트 로드 실패: {e}")
    
    
    def _verify_event_bus(self):
        """
        EventBus 로드 확인
        
        EventBus는 import 시점에 자동 초기화되므로
        여기서는 로드 여부만 확인
        """
        try:
            # EVENT_BUS가 정상적으로 로드되었는지 확인
            _ = EVENT_BUS.metaObject()
            self.logger.info("  ✓ EventBus 로드됨")
        except Exception as e:
            self.logger.warning(f"  ⚠ EventBus 로드 실패: {e}")
    
    
    def _shutdown(self):
        """
        앱 종료 시 정리 작업 (Graceful Shutdown)
        
        순서:
        1. 종료 이벤트 발행 (EVENT_BUS.app_shutting_down)
        2. EventBus 시그널 연결 해제
        3. 로깅 시스템 종료
        
        Note:
            aboutToQuit 시그널에 의해 자동 호출됨
        """
        self.logger.info("🔌 앱 종료 시작...")
        
        try:
            # 1. 다른 모듈에 종료 알림
            EVENT_BUS.app_shutting_down.emit()
            self.logger.info("  ✓ 종료 이벤트 발행됨")
            
        except Exception as e:
            self.logger.warning(f"  ⚠ 종료 이벤트 발행 실패: {e}")
        
        try:
            # 2. EventBus 정리
            EVENT_BUS.disconnect_all()
            self.logger.info("  ✓ EventBus 시그널 연결 해제됨")
            
        except Exception as e:
            self.logger.warning(f"  ⚠ EventBus 정리 실패: {e}")
        
        # 3. 로깅 시스템 종료 (마지막)
        self.logger.info("👋 앱 종료 완료")
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
    print("AppEngine 테스트")
    print("="*70 + "\n")
    
    # 1. AppEngine 생성
    print("1️⃣  AppEngine 초기화:")
    app = AppEngine(sys.argv)
    
    # 2. 싱글톤 확인
    print("\n2️⃣  싱글톤 패턴 확인:")
    app2 = AppEngine()
    print(f"   app1 ID: {id(app)}")
    print(f"   app2 ID: {id(app2)}")
    print(f"   동일 인스턴스: {app is app2}")
    
    if app is not app2:
        print("   ❌ 싱글톤 테스트 실패!")
        sys.exit(1)
    else:
        print("   ✅ 싱글톤 테스트 성공")
    
    # 3. LogListener 초기화 (외부에서)
    print("\n3️⃣  LogListener 초기화:")
    try:
        from core.log_listener import LogListener
        log_listener = LogListener()
        print("   ✅ LogListener 초기화 완료")
    except ImportError:
        print("   ⚠ LogListener를 찾을 수 없습니다 (선택적)")
    
    # 4. 테스트 윈도우 생성
    print("\n4️⃣  테스트 윈도우 생성:")
    window = QWidget()
    window.setWindowTitle("AppEngine 테스트")
    window.setGeometry(100, 100, 400, 200)
    
    layout = QVBoxLayout()
    
    # 라벨
    label = QLabel(
        "AppEngine 테스트 윈도우\n\n"
        "확인 사항:\n"
        "- 스타일시트 적용 여부\n"
        "- 종료 버튼 클릭 시 정상 종료"
    )
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    
    # 종료 버튼
    quit_button = QPushButton("종료 (Shutdown 테스트)")
    quit_button.clicked.connect(app.quit)
    
    layout.addWidget(label)
    layout.addWidget(quit_button)
    layout.addStretch()
    
    window.setLayout(layout)
    window.show()
    
    print("   ✅ 테스트 윈도우 표시됨")
    print("\n   [종료 방법]")
    print("   - 윈도우 닫기")
    print("   - '종료' 버튼 클릭")
    
    # 5. 이벤트 루프 시작
    print("\n5️⃣  이벤트 루프 시작...")
    print("="*70 + "\n")
    
    exit_code = app.exec()
    
    print("\n" + "="*70)
    print(f"앱 종료됨 (종료 코드: {exit_code})")
    print("="*70 + "\n")
    
    sys.exit(exit_code)