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
from pathlib import Path
from .panels import left_panel, center_panel, right_panel

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
        self.status_label.setObjectName("status_label")  # CSS Selector 용
        self.status_label.setProperty("status", "disconnected")  # 상태 속성 설정
        self.statusBar.addWidget(self.status_label)

        # 중심 위젯과 레이아웃
        self.centralWidget = QWidget()
        self.setCentralWidget(self.centralWidget)
        self.mainLayout = QHBoxLayout(self.centralWidget)


        # 패널
        self.mainLayout.addWidget(left_panel.LeftPanel())
        self.mainLayout.addWidget(center_panel.CenterPanel())
        self.mainLayout.addWidget(right_panel.RightPanel())

        # 패널 레이아웃 비율 설정
        self.mainLayout.setStretch(0, 1)  # Left    첫째가 남는 공간 중 1만큼
        self.mainLayout.setStretch(1, 1)  # Center  둘째가 남는 공간 중 1만큼
        self.mainLayout.setStretch(2, 2)  # Right   셋째가 남는 공간 중 2만큼


        # 메인 윈도우에 스타일 적용
        self.apply_style()


    # 스타일시트 읽기 및 적용
    def apply_style(self):
        """QSS 파일 읽기 및 적용"""
        qss_path = Path("styles/stylesheet.qss")
        
        if qss_path.exists():
            try:
                with open(qss_path, "r", encoding='UTF-8') as file:
                    stylesheet = file.read()
                    self.setStyleSheet(stylesheet)  # MainWindow에 적용
                    print("✅ 스타일시트 로드 성공")
            except Exception as e:
                print(f"❌ 스타일시트 로드 실패: {e}")
        else:
            print(f"⚠️ 스타일시트 파일 없음: {qss_path}")

