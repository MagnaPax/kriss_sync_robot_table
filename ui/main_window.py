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

from PyQt6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QMessageBox, QDialog
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QIcon

from core.event_bus import EVENT_BUS
from core.settings import SETTINGS
# 패널 및 위젯
from ui.splash_screen import SplashScreen
from ui.widgets.base_widget import BaseWidget
from view_models.main_window_viewmodel import MainViewModel
from ui.widgets.status_indicator_box import StatusIndicatorBox
from ui.panels import left_panel, center_panel, right_panel


class MainWindow(QMainWindow):
    
    def __init__(self, viewmodel: MainViewModel):
        super().__init__()

        # ViewModel 주입 (View는 VM을 알고 있다, 하지만 VM은 View를 모른다)
        self.vm = viewmodel

        # 기본 UI 설정
        self.setWindowTitle(SETTINGS.app.name)
        self.setWindowIcon(QIcon(SETTINGS.app.icon_path))
        self.setGeometry(100, 100, 1200, 800)  # 초기 창 크기

        # --- UI 초기화 --- #
        self._init_status_bar()     # 상태바 설정 (TwinCAT 상태 표시기 추가)
        self._init_central_widget() # 중앙 레이아웃 및 패널 설정

        # --- 데이터 바인딩 --- #
        self._bind_viewmodel()      # View <-> ViewModel

        # --- UI 이벤트 바인딩 --- #
        self._bind_ui_events()

        # 전역 로딩 다이얼로그 (Lazy Loading)
        self.loading_dialog: QProgressDialog | None = None


    # =====================
    # 메인 윈도우 화면 배치
    # =====================
    def _init_status_bar(self):
        """상태바 초기화 및 위젯 추가"""
        status_bar = self.statusBar()
        
        # TwinCAT 상태 표시 위젯 생성 (초기값: Disconnected)
        self.twincat_indicator = StatusIndicatorBox("TwinCAT", led_size=12)
        # 초기 상태 설정
        self.twincat_indicator.safe_update_data({'title': 'TwinCAT', 'state': 'disconnected'})

        if status_bar:
            # 상태바 맨 왼쪽에 커스텀 위젯 추가 (stretch=0 : 최소 크기만 차지)
            status_bar.addWidget(self.twincat_indicator, 0)

            # 빈 공간을 채우는 투명 위젯
            #    이 위젯이 남은 공간(stretch=1)을 전부 먹어버려서
            #    twincat_indicator과 아래의 status_label를 양쪽 끝으로 밀어버린다
            dummy_widget = QWidget()
            status_bar.addPermanentWidget(dummy_widget, 1)

            # 상태바 오른쪽에 보조 텍스트 레이블 추가
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
        self.mainLayout.setSpacing(0)   # 패널 사이의 간격 (Spacing)
        self.mainLayout.setContentsMargins(5, 3, 5, 0)

        # 패널 생성 - 부모를 centralWidget로 명시
        # TODO: 나중에 패널 내부에서도 로직이 필요하면 self.vm을 전달하면 된다
        self.left = left_panel.LeftPanel(self.vm, central_widget)
        self.center = center_panel.CenterPanel(self.vm, central_widget)
        self.right = right_panel.RightPanel(self.vm, central_widget)

        self.mainLayout.addWidget(self.left)
        self.mainLayout.addWidget(self.center)
        self.mainLayout.addWidget(self.right)

        # 패널 레이아웃 비율 설정
        self.mainLayout.setStretch(0, 3)  # Left    30%
        self.mainLayout.setStretch(1, 3)  # Center  30%
        self.mainLayout.setStretch(2, 4)  # Right   40%



    # ==========================================================
    # 바인딩 섹션 (데이터 / UI 이벤트 분리)
    # ==========================================================
    def _bind_viewmodel(self):
        """
        [전선 연결] 
        VM의 시그널과 View의 슬롯(Slot, _on 메서드)을 연결(connect) 하는 코드를 한곳에 모아두는 곳
        __init__(초기화) 단계에서 딱 1번 호출된다
        """

        # --- VM의 시그널(전화) 연결 --- #
        self.vm.twincat_status_data.connect(self.twincat_indicator.safe_update_data)    # PLC 연결 상태 화면 표시
        self.vm.show_recovery_dialog.connect(self._on_recovery_dialog)                  # 재접속 모달 표시

        # --- 이벤트 버스 시그널(라디오 방송) 연결 --- #
        EVENT_BUS.system.operation_error_alert.connect(self._on_operation_error_dialog)   # 작업 중 발생한 에러 팝업
        EVENT_BUS.system.loading_started.connect(self._on_loading_started)      # 파일 읽기 시작
        EVENT_BUS.system.loading_finished.connect(self._on_loading_finished)    # 파일 읽기 끝

    def _bind_ui_events(self):
        """
        위젯들의 UI 이벤트(에러, 알림 등)를 메인 윈도우와 연결
        
        모든 위젯이 BaseWidget을 상속받기 때문에
        일일이 명시하지 않고 'findChildren'으로 찾아서 한꺼번에 연결할 수 있다
        """
        
        # MainWindow 산하의 모든 BaseWidget을 다 찾는다
        #       LeftPanel, CenterPanel, RightPanel 안에 깊숙이 박힌 것까지 다 찾아낸다
        all_widgets = self.findChildren(BaseWidget)

        for widget in all_widgets:
            # 에러 시그널 연결 (중복 연결 방지를 위해 try-except 또는 uniqueConnection 사용 가능)
            try:
                # 이미 연결되어 있을 수 있으므로 끊고 다시 연결하거나
                # 단순히 연결 (Qt는 기본적으로 다중 연결 허용)
                widget.error_occurred.connect(self.show_error_popup)
            except Exception:
                pass
            
            # TODO: 나중에 다른 공통 이벤트가 생기면 여기서 또 연결하면 된다
            # widget.status_changed.connect(self.update_status_bar)


    # ==========================================================
    # 공통 핸들러
    # ==========================================================
    @pyqtSlot()
    def _on_recovery_dialog(self):
        """
        [복구 모드] 연결 끊김 시 재접속 시도 UI (모달) 표시
        """
        # 스플래시 화면 재사용 (모달처럼 띄움)
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
        
        # ViewModel에게 재접속 요청 (UI 업데이트용 콜백 함수 전달)
        #    Service의 connect_with_retry가 실행되면서 splash.update_status를 호출함
        success = self.vm.retry_connection(ui_callback=recovery_splash.update_status)
        
        recovery_splash.close()
        
        # 최종 실패 시 경고창 표시
        if not success:
            QMessageBox.critical(
                self, 
                "재접속 실패", 
                "연결을 복구할 수 없습니다.\n케이블 연결 상태를 확인 후 다시 시도하십시오."
            )

    @pyqtSlot(str, str)
    def _on_operation_error_dialog(self, title: str, message: str):
        """작업 에러 발생 시 모달 다이얼로그 표시"""
        QMessageBox.critical(self, title, message)

    @pyqtSlot(str)
    def show_error_popup(self, error_message: str):
        """
        [공통 에러 처리]
        BaseWidget를 상속받은 모든 위젯에서 self.error_occurred.emit(msg)를 호출하면
        이 함수가 실행되어 경고창을 띄운다
        """
        QMessageBox.critical(self, "오류", error_message)

    @pyqtSlot(str)
    def _on_loading_started(self, message: str):
        """파일 읽기 다이얼로그 표시"""
        if self.loading_dialog is None:
            # 단순 메시지 창을 위한 QDialog 구성
            self.loading_dialog = QDialog(self)
            self.loading_dialog.setObjectName("loading_dialog") # QSS 스타일링용 ID
            
            # Frameless 설정
            self.loading_dialog.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
            self.loading_dialog.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            self.loading_dialog.setWindowModality(Qt.WindowModality.WindowModal)

            # 메인 레이아웃 (여백 없음)
            main_layout = QVBoxLayout(self.loading_dialog)
            main_layout.setContentsMargins(0, 0, 0, 0)
            
            # 배경 위젯 (실제 다이얼로그 디자인)
            self.loading_bg = QWidget(self.loading_dialog)
            self.loading_bg.setObjectName("loading_bg")
            self.loading_bg.setProperty("type", "success") # QSS 타입
            main_layout.addWidget(self.loading_bg)

            # 내용 레이아웃
            content_layout = QVBoxLayout(self.loading_bg)
            content_layout.setContentsMargins(20, 20, 20, 20)
            
            self.loading_label = QLabel(self.loading_dialog)
            self.loading_label.setObjectName("loading_label") # QSS 스타일링용 ID
            self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.loading_label.setWordWrap(True)
            content_layout.addWidget(self.loading_label)

            # 창 크기 고정 및 디자인 설정
            self.loading_dialog.setFixedSize(300, 100)
            # 도움말 버튼(?) 제거 (Frameless라 사실 의미없음)
            # self.loading_dialog.setWindowFlags(self.loading_dialog.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        self.loading_label.setText(message)
        self.loading_dialog.show()
        
        # 즉시 렌더링 (메인 스레드가 곧 블로킹될 것이므로 미리 그려야 함)
        import PyQt6.QtWidgets
        PyQt6.QtWidgets.QApplication.processEvents()

    @pyqtSlot()
    def _on_loading_finished(self):
        """파일 읽기 다이얼로그 닫기"""
        if self.loading_dialog:
            self.loading_dialog.close()
