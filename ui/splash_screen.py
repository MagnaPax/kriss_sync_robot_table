# ui/splash.py
"""
사용자에게 현재 무엇을 하고 있는지, 문제가 생겼다면 재시도 중인지 알림
"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar
from PyQt6.QtCore import Qt



class SplashScreen(QWidget):
    def __init__(self):
        super().__init__()
        
        # 창 설정 (투명 배경, 테두리 없음, 항상 위에)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(400, 250)

        # 메인 레이아웃 및 배경 위젯 설정
        # (투명 배경 위에서 둥근 테두리를 표현하기 위해 내부 위젯을 하나 둡니다)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0) # 여백 제거

        self.background_widget = QWidget()
        self.background_widget.setObjectName("splash_background") # QSS 연결용 셀렉터 id
        main_layout.addWidget(self.background_widget)

        # 내부 콘텐츠 레이아웃
        content_layout = QVBoxLayout(self.background_widget)
        content_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.setContentsMargins(30, 30, 30, 30) # 내부 여백

        # 타이틀
        self.title_label = QLabel("TwinSync Controller")
        self.title_label.setObjectName("splash_title") # QSS 연결 ID
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 상태 메시지
        self.status_label = QLabel("시스템 초기화 중...")
        self.status_label.setObjectName("splash_status") # QSS 연결 ID
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 진행바
        self.progress = QProgressBar()
        self.progress.setObjectName("splash_progress") # QSS 연결 ID
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFixedHeight(25)
        self.progress.setTextVisible(True) # 퍼센트 텍스트 표시

        # 위젯 배치
        content_layout.addWidget(self.title_label)
        content_layout.addStretch(1) # 간격 벌리기
        content_layout.addWidget(self.status_label)
        content_layout.addWidget(self.progress)
        content_layout.addStretch(1)


    def update_status(self, message: str, progress: int = -1):
        """상태 텍스트와 진행률 업데이트 (-1이면 진행률 유지)"""
        self.status_label.setText(message)
        if progress >= 0:
            self.progress.setValue(progress)
        
        # UI 즉시 갱신 (중요: 루프 내에서 화면이 멈추지 않게 함)
        self.repaint()
