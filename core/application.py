# core/application.py

import sys
import logging
from PyQt6.QtWidgets import QApplication

from utils.logger import Logger
from config.paths import STYLESHEET_PATH
from core.exception_handler import install_global_exception_hook
from core.event_bus import EVENT_BUS





class AppEngine(QApplication):
    """
    앱 엔진(Application Wrapper)
    QApplication 환경을 감싸(wrpper) 클래스

    목적:
        - 앱 전체에서 QApplication 인스턴스가 하나만 존재하도록 보장 (싱글톤)
        - 전역 예외 처리, 테마 적용, 로깅 초기화, 종료 신호 처리 등을 담당
        - 앱의 “부트스트랩(시작점)” 역할
    """

    # 싱글톤 디자인 패턴
    _instance: AppEngine | None = None   # 클래스의 유일한 인스턴스(객체)를 저장하기 위한 공간
    _initialized: bool = False        # 초기화 코드가 여러번 실행되는 것을 방지하는 flag 변수(스위치)


    def __new__(cls, *args, **kwargs) -> "AppEngine":
        """
        클래스가 앱 전체에서 단 하나의 인스턴스(객체)만 갖도록 보장하는 
        싱글톤(Singleton) 디자인 패턴 구현
        """

        # --- 최초 호출할때만 인스턴스 생성, 그 뒤로는 같은 인스턴스 리턴 --- #
        # 1. 클래스 변수 _instance가 비어있는지(None) 확인
        if cls._instance is None:

            # __new__ 내부에서 발생할 수 있는 예외를 로깅하기 위해
            # 인스턴스 생성 전에 Logger를 먼저 초기화
            # Logger는 싱글톤이므로, 호출 자체로 초기화
            Logger()

            # 2. QApplication.instance() 를 통해 기존 인스턴스가 있는지 확인
            instance = QApplication.instance()

            if instance is None:
                # 3. 없다면, 새로운 AppEngine 인스턴스를 생성
                Logger().logger.info("Creating AppEngine instance...")
                cls._instance = super().__new__(cls)

            elif isinstance(instance, cls):
                # 4. 이미 AppEngine 인스턴스가 있다면 그것을 사용
                Logger().logger.info("Using existing AppEngine instance.")
                cls._instance = instance

            else:
                # 5. AppEngine이 아닌 다른 QApplication 인스턴스가 이미 존재하면,
                #    이는 잘못된 앱 설정이므로 에러 발생
                err_msg = "A QApplication instance already exists, but it is not an AppEngine instance."
                Logger().logger.error(err_msg)
                raise TypeError(err_msg)

        return cls._instance


    def __init__(self, argv=None) -> None:
        """
        인스턴스가 생성된 후, 실제 QApplication 초기화를 수행
        싱글톤 패턴에 의해 __init__은 여러 번 호출될 수 있으므로
        _initialized 플래그로 실제 초기화는 한 번만 실행되도록 보장한다
        """
        # 클래스 변수를 체크하여 이미 초기화되었다면 즉시 반환
        if AppEngine._initialized:
            return

        # Logger 인스턴스를 생성하고 AppEngine 의 속성으로 만든다
        self.logger = Logger().logger

        try:
            # QApplication의 초기화는 한 번만 수행되어야 한다
            # 부모 클래스(QApplication)의 __init__ 호출(누락되면 앱이 작동하지 않음)
            super().__init__(argv or sys.argv) # type: ignore
        except Exception as e:
            self.logger.critical(f"QApplication 초기화 실패: {e}", exc_info=True)

        # --- 1회성 초기화 코드 --- #
        self._initialize_theme()            # → styles/theme_manager.py
        self._initialize_exception_hook()   # → core/exception_handler.py
        self._initialize_event_bus()        # → core/event_bus.py
        
        # 애플리케이션이 종료될 때 실행할 클린업 훅(shutdown 메서드) 등록
        self.aboutToQuit.connect(self.shutdown)


        # 모든 초기화가 끝났으므로 플래그를 True로 설정
        AppEngine._initialized = True
        self.logger.info("Application Engine has been initialized.")





    def _initialize_theme(self):
        """전역 스타일시트를 로드하고 적용합니다."""
        # load_and_apply_stylesheet(self, STYLESHEET_PATH)
        if STYLESHEET_PATH.exists():
            try:
                with open(STYLESHEET_PATH, "r", encoding='UTF-8') as file:
                    stylesheet = file.read()
                    self.setStyleSheet(stylesheet)  # MainWindow에 적용
                    print("✅ 스타일시트 로드 성공")
            except Exception as e:
                print(f"❌ 스타일시트 로드 실패: {e}")
        else:
            print(f"⚠️ 스타일시트 파일 없음: {STYLESHEET_PATH}")

    def _initialize_exception_hook(self):
        install_global_exception_hook()

    def _initialize_event_bus(self):
        """
        이벤트 버스 초기화 및 애플리케이션 시그널 연결.
        EVENT_BUS 자체는 import 시점에 초기화되므로, 여기서는 로깅 및 연결을 수행한다
        """
        self.logger.info("EventBus has been loaded.")

    def shutdown(self):
        """
        앱이 종료(aboutToQuit 시그널)될 때 실행
        애플리케이션의 우아한 종료(Graceful Shutdown)를 처리

        - 실행 중인 작업 중단
        - 데이터 저장
        - 리소스 정리
        - EventBus 신호 해제
        - Logger 핸들러 닫기
        """        

        self.logger.info("🔌 앱 종료 시작")

        try:
            # 1. 다른 모듈에 앱 종료를 알리는 전역 이벤트 발행
            EVENT_BUS.log_emit('app_shutting_down')

            # 2. (필요 시) 실행 중인 작업(예: 통신 스레드) 중단
            # self.robot_controller.stop()

            # 3. (필요 시) 현재 상태(예: 창 위치) 저장
            # self.save_state()

            # 4. EventBus의 모든 시그널 연결을 명시적으로 해제
            EVENT_BUS.disconnect_all()

        except Exception as e:
            self.logger.warning("EventBus 클린업 중 오류 발생: %s", e)

        # 5. 모든 로그가 파일에 기록되도록 로깅 시스템을 정상적으로 종료
        self.logger.info("Application shutdown completed.")
        logging.shutdown()






# =============================================================================
# 단독 실행 (테스트용)
"""
실행 명령어
python -m core.application
"""
# =============================================================================
if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
    
    # AppEngine은 내부적으로 sys.argv를 사용하므로
    # QApplication에 인자를 전달합니다.
    # __new__ 와 __init__ 이 실행되며 로깅, 예외처리, 테마, 이벤트 버스 초기화
    print("=" * 70)
    print("AppEngine 테스트 시작...")
    
    # 1. AppEngine 인스턴스 생성
    # Logger, 예외 후크, 테마, 이벤트 버스가 모두 초기화됩니다.
    app_engine = AppEngine(sys.argv)
    
    # 2. 싱글톤 테스트
    print("\n--- 싱글톤 테스트 ---")
    print(f"Engine 1 ID: {id(app_engine)}")
    
    # 다시 호출해도 __new__에 의해 동일한 인스턴스가 반환되어야 함
    app_engine_2 = AppEngine()
    print(f"Engine 2 ID: {id(app_engine_2)}")
    print(f"동일 인스턴스: {app_engine is app_engine_2}")
    
    if not (app_engine is app_engine_2):
        print("❌ 싱글톤 테스트 실패!")
    else:
        print("✅ 싱글톤 테스트 성공")

    # 3. 간단한 테스트 윈도우 생성 (앱이 바로 종료되지 않게)
    print("\n--- 테스트 윈도우 생성 ---")
    try:
        window = QWidget()
        window.setWindowTitle("AppEngine 테스트")
        window.setGeometry(100, 100, 300, 200)
        
        layout = QVBoxLayout()
        
        # 스타일시트 적용 확인용
        label = QLabel("AppEngine 테스트 윈도우\n스타일시트가 적용되었는지 확인하세요.")
        label.setObjectName("TestLabel") # CSS ID (선택적)
        
        # 종료 버튼 (aboutToQuit 시그널 테스트용)
        quit_button = QPushButton("종료 (Shutdown 테스트)")
        # QApplication.quit()을 호출하면 aboutToQuit 시그널이 발생
        quit_button.clicked.connect(app_engine.quit) 
        
        layout.addWidget(label)
        layout.addWidget(quit_button)
        window.setLayout(layout)
        
        window.show()
        print("테스트 윈도우 표시 완료.")
        print("윈도우를 닫거나 '종료' 버튼을 누르면 앱이 종료됩니다.")
        
        # 4. 이벤트 루프 시작
        print("\nAppEngine.exec() 실행...")
        print("=" * 70)
        
        # app_engine.exec() 호출
        exit_code = app_engine.exec()
        
        print("=" * 70)
        print(f"AppEngine.exec() 종료. (종료 코드: {exit_code})")
        print("EventBus.disconnect_all()이 호출되었어야 합니다.")
        
        # 5. 종료
        sys.exit(exit_code)

    except Exception as e:
        # __init__에서 전역 예외 후크가 설치되었으므로 
        # 이 코드는 실행되지 않아야 정상이지만,
        # 만약의 경우를 대비해 여기서도 로깅
        if hasattr(app_engine, 'logger'):
            app_engine.logger.critical(f"AppEngine 테스트 중 예외 발생: {e}", exc_info=True)
        else:
            print(f"CRITICAL: AppEngine 테스트 중 예외 발생: {e}")
        sys.exit(1)
