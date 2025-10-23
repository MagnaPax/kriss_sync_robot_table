import sys
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton
from PyQt6.QtGui import QPainter, QColor
from PyQt6.QtCore import Qt, QSize, QTimer


# from .base_widget import BaseWidget
from .base_widget import BaseWidget


# ==========================================================
# 1. Status Indicator Widget
# ==========================================================
class StatusIndicator(BaseWidget):
    """
    상태를 표시하는 원형 LED 램프 위젯
    - BaseWidget을 상속받아 update_data 인터페이스 구현
    - 'running', 'waiting', 'red', 'gray' 등의 상태/색상 문자열을 data로 받음
    """

    def __init__(self, parent=None, default_color='gray', size=12):
        """
        StatusIndicator 초기화
        
        Args:
            parent (QWidget, optional): 부모 위젯.
            default_color (str, optional): 초기 색상.
            size (int, optional): 원의 직경 (px).
        """
        self._color = QColor(default_color)
        self._size = size
        # BaseWidget의 __init__이 마지막에 호출되어야 _init_ui가 실행됨
        super().__init__(parent) 

    def _init_ui(self):
        """BaseWidget의 _init_ui를 재정의"""
        self.setFixedSize(self._size, self._size)
        self.clear_widget() # 초기 상태(회색)로 설정

    def update_data(self, data: str):
        """
        BaseWidget의 추상 메서드(update_data) 구현
        
        Args:
            data (str): 상태('running', 'disconnected') 또는 
                        QColor가 이해할 수 있는 색상 이름 (예: 'green', '#FF0000')
        """
        
        # 상태 문자열을 표준 색상으로 매핑
        color_map = {
            # 턴테이블/로봇 상태
            "running": "green",
            "waiting": "yellow",
            
            # 연결 상태
            "connected": "green",
            "connecting": "yellow",
            "disconnected": "red",
            "error": "red",
            
            # 기본 상태
            "off": "gray",
            "disabled": "gray",
        }
        
        # 1. 입력된 data(소문자)가 color_map에 키로 존재하면, 매핑된 값(색상)을 사용
        # 2. 존재하지 않으면, 입력된 data 값 자체를 색상 이름으로 간주 (예: 'blue', '#00FFFF')
        color_name = color_map.get(str(data).lower(), data)
        
        self._color = QColor(color_name)
        self.update()  # paintEvent() 호출을 요청

    def paintEvent(self, a0):
        """QPainter를 사용하여 원을 그립니다."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing) # 원을 부드럽게
        
        painter.setBrush(self._color)
        painter.setPen(Qt.PenStyle.NoPen) # 테두리 없음
        
        # setFixedSize에서 설정한 크기만큼 원을 그림 (테두리 깨짐 방지용 여백 1px)
        padding = 1
        rect = self.rect().adjusted(padding, padding, -padding, -padding)
        painter.drawEllipse(rect)

    def sizeHint(self):
        """레이아웃에 적절한 크기 힌트 제공"""
        return QSize(self._size, self._size)

    def clear_widget(self):
        """위젯을 'off' (회색) 상태로 초기화"""
        self.update_data("gray")
        # BaseWidget의 clear_widget도 호출 (필요시)
        # super().clear_widget()


# ==========================================================
# 2. 단독 실행 (테스트용)
# ==========================================================
if __name__ == '__main__':
    
    app = QApplication(sys.argv)
    
    # 1. 메인 위젯 생성
    main_window = QWidget()
    main_layout = QVBoxLayout(main_window)
    main_window.setWindowTitle("StatusIndicator 단독 테스트")

    # 2. 인디케이터 생성 (테스트를 위해 20px로 크게 만듦)
    indicator = StatusIndicator(size=20) 
    main_layout.addWidget(indicator, alignment=Qt.AlignmentFlag.AlignCenter)

    # 3. 테스트용 버튼 생성 함수
    def create_button(text, state):
        btn = QPushButton(text)
        # safe_update_data를 호출하여 BaseWidget의 기능 테스트
        btn.clicked.connect(lambda: indicator.safe_update_data(state))
        main_layout.addWidget(btn)

    # 4. 버튼 추가
    create_button("Running (green)", "running")
    create_button("Waiting (yellow)", "waiting")
    create_button("Disconnected (red)", "disconnected")
    create_button("Off (gray)", "off")
    create_button("커스텀 색상 (blue)", "blue")

    # 5. 비활성화 테스트 버튼
    btn_disable = QPushButton("위젯 비활성화 (Update 무시)")
    btn_disable.clicked.connect(lambda: indicator.set_enabled(False))
    main_layout.addWidget(btn_disable)
    
    btn_enable = QPushButton("위젯 활성화")
    btn_enable.clicked.connect(lambda: indicator.set_enabled(True))
    main_layout.addWidget(btn_enable)

    main_window.show()
    
    sys.exit(app.exec())