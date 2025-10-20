"""
MainWindow 클래스
- kriss_sync_robot_turn_table 프로젝트의 메인 UI 윈도우
- QMainWindow를 상속하여 메뉴바, 상태바, 중앙 레이아웃 구성
- Phase 1: 정적 UI로 시안과 동일한 레이아웃 제공 (g02.md)
- 작성자: [팀/개발자 이름]
- 버전: 0.1.0 (2025.10.17)
"""

from PyQt6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QLabel, QStatusBar, QMenuBar, QMenu
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

class MainWindow(QMainWindow):
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("KRISS Robot Polishing Machine")
        self.setWindowIcon(QIcon("resources/icons/kriss.gif"))
        self.setGeometry(100, 100, 1200, 800)  # 초기 창 크기

        # 상태바 설정
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.status_label = QLabel("Disconnected")  # 초기 상태
        self.statusBar.addWidget(self.status_label)

