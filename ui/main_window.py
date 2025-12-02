# ui/main_window.py
"""
MainWindow 클래스
- kriss_sync_robot_turn_table 프로젝트의 메인 UI 윈도우
- QMainWindow를 상속하여 메뉴바, 상태바, 중앙 레이아웃 구성
- Phase 1: 정적 UI로 시안과 동일한 레이아웃 제공 (g02.md)
- 작성자: [팀/개발자 이름]
- 버전: 0.1.0 (2025.10.17)
"""

from PyQt6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QLabel, QStatusBar
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from pathlib import Path
from .panels import left_panel, center_panel, right_panel


class MainWindow(QMainWindow):
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("KRISS Robot Polishing Machine")
        self.setWindowIcon(QIcon("resources/icons/kriss.gif"))
        self.setGeometry(100, 100, 1200, 800)  # 초기 창 크기

        # 상태바 설정. statusBar()는 QMainWindow의 메서드로, 상태바가 없으면 생성하고 반환합니다.
        status_bar = self.statusBar()
        self.status_label = QLabel("Disconnected")  # 초기 상태
        self.status_label.setObjectName("status_label")  # CSS Selector 용
        self.status_label.setProperty("status", "disconnected")  # 상태 속성 설정
        if status_bar:  # status_bar가 None이 아닌지 확인
            status_bar.addWidget(self.status_label)

        # 중심 위젯과 레이아웃
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.mainLayout = QHBoxLayout(central_widget)


        # 패널
        # 부모를 centralWidget로 명시
        self.mainLayout.addWidget(left_panel.LeftPanel(central_widget))
        self.mainLayout.addWidget(center_panel.CenterPanel(central_widget))
        self.mainLayout.addWidget(right_panel.RightPanel(central_widget))

        # 패널 레이아웃 비율 설정
        self.mainLayout.setStretch(0, 1)  # Left    첫째가 남는 공간 중 1만큼
        self.mainLayout.setStretch(1, 1)  # Center  둘째가 남는 공간 중 1만큼
        self.mainLayout.setStretch(2, 2)  # Right   셋째가 남는 공간 중 2만큼
