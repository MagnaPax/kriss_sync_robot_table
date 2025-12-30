# ./main.py
"""
앱 실행 스크립트 (Entry Point)

- KRISS의 "다축 제어기 H/W Upgrade 및 EtherCAT을 이용한 동기화 시스템 개발" 프로젝트의 실행 파일
- 이 스크립트는 애플리케이션의 인프라(AppEngine)를 구동하고 부팅 관리자(StartupManager)에게 실행 권한을 위임한다.
- UI 로직이나 비즈니스 로직은 포함하지 않으며, 오직 '조립'과 '시작'의 역할만 수행한다.

[버전 이력]
- v0.1.0 (2025.10.17): 초기 버전 (절차적 코드)
- v0.2.0 (2025.11.11): AppEngine 도입 (싱글톤 구조)
- v0.3.1 (2025.11.20): LogListener 초기화 책임 이동
- v0.4.0 (2025.11.28): StartupManager 도입 (SoC 적용, 부팅 시퀀스 분리)
"""
import sys

from core.application import AppEngine      # [인프라]  앱 전역 설정 및 생명주기 관리 (싱글톤)
from core.log_listener import LogListener   # [로깅]    EventBus 신호를 Logger로 전달하는 중재자
from core.startup import StartupManager     # [부팅]    스플래시 화면, 접속 시도 등 실행 흐름 제어



def main():
    """
    앱의 진입점
    
    역할:
        1. 인프라 초기화 (AppEngine, Logger)
        2. 부팅 시나리오 위임 (StartupManager)
        3. 이벤트 루프 실행

    특징:
        - 추후 로그인, 버전 체크등의 기능을 추가하고 싶다면 
        - main.py 이 아닌 StartupManager.run() 메서드만 수정하면 된다
    """

    # 1. AppEngine 인스턴스를 생성하여 애플리케이션을 초기화 한다
    # 이 과정에서 로깅, 예외 처리, 테마 등이 자동으로 설정 된다
    # AppEngine은 싱글톤 패턴을 사용하며, 내부적으로 sys.argv를 처리한다.
    app = AppEngine(sys.argv)


    # 2. LogListener 초기화 (EventBus와 Logger 연결)
    # LogListener가 EventBus 시그널을 구독하도록 main.py에서 생성
    # 인스턴스를 변수에 할당해서 가비지 컬렉터가 수거하는 것을 방지한다.
    _log_listener = LogListener()


    # 3. AppEngine의 초기화 로직 실행 (Bootstrap)
    # AppEngine 클래스 내부에서도 EventBus 사용 가능(LogListener 들을 수 있음)
    app.bootstrap()


    # 4. 부팅 시나리오 실행 (스플래시 -> 접속 -> 메인윈도우)
    #   StartupManager 가 앱의 실행 흐름(Flow)과 UI 제어를 담당
    startup = StartupManager()
    _main_window = startup.run()


    # 5. 이벤트 루프를 시작하고, 앱이 종료되면 종료 코드를 반환한다
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
