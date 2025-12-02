# ui/main_window.py
"""
MainWindow 클래스 (View)
- TwinCAT 연결 끊김 시 복구 모드(Recovery UI) 진입 로직 포함

[주요 기능]
1. 레이아웃 구성 (왼쪽/가운데/오른쪽 패널)
2. 상태바에 TwinCAT 연결 상태 표시 (StatusIndicatorBox 사용)
3. ViewModel 시그널 구독 및 UI 업데이트
4. 재접속 시도 로직 (SplashScreen 재사용)
"""

from PyQt6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QLabel, QMessageBox
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QIcon

# 패널 및 위젯
from ui.panels import left_panel, center_panel, right_panel
from ui.splash_screen import SplashScreen
from ui.widgets.status_indicator_box import StatusIndicatorBox
from view_models.main_window_viewmodel import MainViewModel



class MainWindow(QMainWindow):
    
    def __init__(self, viewmodel: MainViewModel):
        super().__init__()

        # ViewModel 주입 (View는 VM을 알고 있다, 하지만 VM은 View를 모른다)
        self.vm = viewmodel

        # 기본 UI 설정
        self.setWindowTitle("KRISS Robot Polishing Machine")
        self.setWindowIcon(QIcon("resources/icons/kriss.gif"))
        self.setGeometry(100, 100, 1200, 800)  # 초기 창 크기

        # 상태바 설정 (TwinCAT 상태 표시기 추가)
        self._init_status_bar()

        # 중앙 레이아웃 및 패널 설정
        self._init_central_widget()

        # [핵심] ViewModel과 연결 (Data Binding)
        self._bind_viewmodel()



    def _init_status_bar(self):
        """상태바 초기화 및 위젯 추가"""
        status_bar = self.statusBar()
        
        # TwinCAT 상태 표시 위젯 생성 (초기값: Disconnected)
        self.twincat_indicator = StatusIndicatorBox("TwinCAT", led_size=12)
        # 초기 상태 설정
        self.twincat_indicator.safe_update_data({'title': 'TwinCAT', 'state': 'disconnected'})
        
        if status_bar:
            # 상태바 맨 왼쪽에 커스텀 위젯 추가
            status_bar.addWidget(self.twincat_indicator)
            
            # (옵션) 우측 하단에 보조 텍스트 라벨 추가
            self.status_label = QLabel("Ready")
            self.status_label.setMinimumWidth(100)
            self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            status_bar.addPermanentWidget(self.status_label)

    def _init_central_widget(self):
        """중앙 패널 레이아웃 구성"""

        # 중심 위젯과 레이아웃
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.mainLayout = QHBoxLayout(central_widget)

        # 패널 생성 - 부모를 centralWidget로 명시
        # TODO: 나중에 패널 내부에서도 로직이 필요하면 self.vm을 전달하면 된다
        self.left = left_panel.LeftPanel(central_widget)
        self.center = center_panel.CenterPanel(central_widget)
        self.right = right_panel.RightPanel(central_widget)

        self.mainLayout.addWidget(self.left)
        self.mainLayout.addWidget(self.center)
        self.mainLayout.addWidget(self.right)

        # 패널 레이아웃 비율 설정
        self.mainLayout.setStretch(0, 1)  # Left    첫째가 남는 공간 중 1만큼
        self.mainLayout.setStretch(1, 1)  # Center  둘째가 남는 공간 중 1만큼
        self.mainLayout.setStretch(2, 2)  # Right   셋째가 남는 공간 중 2만큼



    # ==========================================================
    def _bind_viewmodel(self):
        """
        [전선 연결] 
        VM의 시그널과 View의 슬롯(Slot, _on 메서드)을 연결(connect) 하는 코드를 한곳에 모아두는 곳
        (초기화) 단계에서 딱 1번 호출됨
        """

        # [연결 상태] VM에서 상태 데이터(dict)가 오면 -> 
        #   위젯 업데이트 함수에 바로 전달
        # VM에서 전화(twincat_status_data 로컬 시그널)가 오면 -> 
        #   StatusIndicatorBox 위젯 업데이트 함수 호출
        self.vm.twincat_status_data.connect(self.twincat_indicator.safe_update_data)
        
        # VM에서 전화(show_recovery_dialog 로컬 시그널)가 오면 show_recovery_ui 에 일시킴
        self.vm.show_recovery_dialog.connect(self.show_recovery_ui)

    @pyqtSlot()
    def show_recovery_ui(self):
        """
        [복구 모드] 연결 끊김 시 재접속 시도 UI (모달) 표시
        """
        # 1. 스플래시 화면 재사용 (모달처럼 띄움)
        recovery_splash = SplashScreen()
        recovery_splash.setWindowTitle("재접속 중...")
        
        # 메인 윈도우 중앙에 배치
        if self.isVisible():
            geo = self.geometry()
            recovery_splash.move(
                geo.center().x() - recovery_splash.width() // 2,
                geo.center().y() - recovery_splash.height() // 2
            )

        recovery_splash.show()
        
        # 2. ViewModel에게 재접속 요청 (UI 업데이트용 콜백 함수 전달)
        #    Service의 connect_with_retry가 실행되면서 splash.update_status를 호출함
        success = self.vm.retry_connection(ui_callback=recovery_splash.update_status)
        
        recovery_splash.close()
        
        # 3. 최종 실패 시 경고창 표시
        if not success:
            QMessageBox.critical(
                self, 
                "재접속 실패", 
                "연결을 복구할 수 없습니다.\n케이블 연결 상태를 확인 후 다시 시도하십시오."
            )