# ui/widgets/status_indicator.py
import sys, os

from PyQt6.QtWidgets import QHBoxLayout, QLabel
from PyQt6.QtGui import QPainter, QPen
from PyQt6.QtCore import Qt, QRectF


# 이 파일의 두 단계 위(=PROJECT_ROOT)를 PYTHONPATH에 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from ui.widgets.base_widget import BaseWidget
from ui.widgets.lamp_indicator import LampIndicator

# from .base_widget import BaseWidget
# from .lamp_indicator import LampIndicator

class StatusIndicatorBox(BaseWidget):
    """
    [제목]  ●  상태 텍스트 
    외곽 테두리 색상은 내부 LED(LampIndicator) 색과 동일.
    """

    def __init__(self,
                 title: str,
                 parent=None,
                 led_size: int = 12):
        self._title_text = title
        self._led_size = led_size
        super().__init__(parent)

    def _init_ui(self):
        # 1) 서브 위젯 생성
        self._lbl_title = QLabel(self._title_text)
        self._lbl_state = QLabel("")  # update_data()에서 채워짐
        self._led = LampIndicator(size=self._led_size)

        # 2) 레이아웃 배치
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)  # border와 간격
        layout.setSpacing(6)
        layout.addWidget(self._lbl_title)
        layout.addWidget(self._led)
        layout.addWidget(self._lbl_state)
        layout.addStretch(1)

        # Optionally 스타일 조정
        # self._lbl_title.setStyleSheet("font-weight:bold;")
        # self._lbl_state .setStyleSheet("font-size:12px;")

    def set_title(self, title: str):
        """제목만 별도로 변경"""
        self._title_text = title
        self._lbl_title.setText(title)
        self.update()        

    # def update_data(self, state: str, title: str | None = None):
    def update_data(self, data: dict):
        """
        data: {'state': 'running', 'title': '새 제목'} 형태의 딕셔너리
        """

        state = data.get('state')
        if state is None:
            state = "off"
        
        title = data.get('title')
        if title :
            self.set_title(title)
        
        # 1) LED 색 업데이트 (internal safe_update_data 쓰지 않고 내부 호출)
        self._led.update_data(state)

        # 2) 텍스트는 대문자 첫글자 등 원하는 형식으로
        txt = str(state).capitalize()
        self._lbl_state.setText(txt)

        # 3) 텍스트가 바뀌었으니 위젯 갱신
        self.update()

    def clear_widget(self):
        super().clear_widget()
        self._led.clear_widget()
        self._lbl_state.clear()
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        """
        LED의 현재 색(self._led._color)을 꺼내와서
        widget 전체를 감싸는 테두리를 같은 색으로 그림.
        """
        super().paintEvent(event)

        # LED 내부에 private 속성으로 색이 저장되어 있으므로 직접 꺼내오거나,
        # LampIndicator 에 get_color() 메서드를 하나 만들어 두셔도 됩니다.
        color = getattr(self._led, '_color', None)
        if color is None:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pen = QPen(color, 2)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        # layout margins(8,4,8,4) 만큼 안쪽으로 들어가서 그리기
        r = self.rect().adjusted(1, 1, -1, -1)
        painter.drawRoundedRect(QRectF(r), 5, 5)

        painter.end()








if __name__ == '__main__':
    import sys
    import itertools
    from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout
    from PyQt6.QtCore import QTimer

    # (1) QApplication 생성
    app = QApplication(sys.argv)

    # (2) 테스트용 윈도우 + 레이아웃
    window = QWidget()
    window.setWindowTitle("StatusIndicatorBox 단독 테스트")
    layout = QVBoxLayout(window)

    # (3) StatusIndicatorBox 인스턴스 생성
    indicator = StatusIndicatorBox("서버 상태", led_size=16)
    layout.addWidget(indicator)

    window.show()

    # (4) 순환할 상태 리스트 & itertools.cycle 로 무한 반복
    # states = ["running", "waiting", "connected", "disconnected", "error"]
    states_data = [
        {'state': 'running'},
        {'state': 'waiting', 'title': '대기 중...'},  # <-- 제목 변경 테스트
        {'state': 'connected', 'title': '서버 상태'}, # <-- 제목 복원 테스트
        {'state': 'disconnected'},
        {'state': 'error'}
    ]
    cycle_data = itertools.cycle(states_data)

    # (5) 1초마다 다음 상태로 업데이트
    def tick():
        data_dict = next(cycle_data)
        indicator.update_data(data_dict)

    timer = QTimer()
    timer.timeout.connect(tick)
    timer.start(1000)

    # 초기 한 번
    tick()

    # (6) Qt 메인 루프 실행
    sys.exit(app.exec())