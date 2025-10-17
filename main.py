"""
애플리케이션 진입점
- KRISS의 "다축 제어기 H/W Upgrade 및 EtherCAT을 이용한 동기화 시스템 개발" 프로젝트 시작점
- QApplication 초기화 및 MainWindow 실행
- Phase 0: 프로젝트 초기화
- 작성자: 한천희
- 버전: 0.1.0 (2025.10.17)
"""

import sys
from PyQt6.QtWidgets import QApplication
from ui import MainWindow

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())            # 앱을 실행 후 이벤트 루프 시작. 앱이 종료될 때까지 대기

if __name__ == "__main__":
    main()
