# ./main.py
"""
애플리케이션 실행 스크립트 (Launcher)

- KRISS의 "다축 제어기 H/W Upgrade 및 EtherCAT을 이용한 동기화 시스템 개발" 프로젝트의 실행 파일
- 이 스크립트는 AppEngine을 초기화하고 메인 윈도우(MainWindow)를 실행한다
- 애플리케이션의 핵심 초기화 로직(로깅, 예외 처리, 테마 등)은 AppEngine에서 중앙 관리된다
- 작성자: 한천희

- 버전: 0.1.0 (2025.10.17) - 초기 버전
- 버전: 0.2.0 (2025.11.11) - AppEngine 도입으로 구조 변경
"""

import sys

# QApplication을 직접 사용하는 대신, 전역 설정을 관리하는 AppEngine을 사용
from core.application import AppEngine
from ui import MainWindow

def main():
    # AppEngine 인스턴스를 생성하여 애플리케이션을 초기화 한다
    # 이 과정에서 로깅, 예외 처리, 테마 등이 자동으로 설정 된다
    app = AppEngine(sys.argv)
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())  # 이벤트 루프를 시작하고, 앱이 종료되면 종료 코드를 반환한다

if __name__ == "__main__":
    main()
