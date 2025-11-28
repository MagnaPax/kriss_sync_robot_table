# ./main.py
"""
애플리케이션 실행 스크립트 (Launcher)

- KRISS의 "다축 제어기 H/W Upgrade 및 EtherCAT을 이용한 동기화 시스템 개발" 프로젝트의 실행 파일
- 이 스크립트는 AppEngine을 초기화하고 메인 윈도우(MainWindow)를 실행한다
- 애플리케이션의 핵심 초기화 로직(로깅, 예외 처리, 테마 등)은 AppEngine에서 중앙 관리된다
- 작성자: 한천희

- 버전: 0.1.0 (2025.10.17) - 초기 버전
- 버전: 0.2.0 (2025.11.11) - AppEngine 도입으로 구조 변경
- 버전: 0.3.1 (2025.11.20) - LogListener 초기화 책임을 main.py로 이동
"""

import sys

# QApplication을 직접 사용하는 대신, 전역 설정을 관리하는 AppEngine을 사용
from core.application import AppEngine
from core.log_listener import LogListener

from ui import MainWindow

def main():
    # AppEngine 인스턴스를 생성하여 애플리케이션을 초기화 한다
    # 이 과정에서 로깅, 예외 처리, 테마 등이 자동으로 설정 된다
    # AppEngine은 싱글톤 패턴을 사용하며, 내부적으로 sys.argv를 처리한다.
    app = AppEngine(sys.argv)

    # LogListener 초기화 (EventBus와 Logger 연결)
    # LogListener가 EventBus 시그널을 구독하도록 main.py에서 생성
    # 인스턴스를 변수에 할당해서 가비지 컬렉터가 수거하는 것을 방지한다.
    log_listener = LogListener()
    
    # 메인 윈도우 생성 및 표시
    window = MainWindow()
    window.show()

    # 이벤트 루프를 시작하고, 앱이 종료되면 종료 코드를 반환한다
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
