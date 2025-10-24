# ui/widgets/status_indicator.py
import sys, os

from PyQt6.QtWidgets import QHBoxLayout, QLabel
from PyQt6.QtGui import QPainter, QPen
from PyQt6.QtCore import Qt, QRectF

# 이 파일의 두 단계 위(=PROJECT_ROOT)를 PYTHONPATH에 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from ui.widgets.base_widget import BaseWidget
from ui.widgets.led_indicator import LEDIndicator



class StatusIndicatorBox(BaseWidget):
    """
    [제목]  ●  상태 텍스트 
    외곽 테두리 색상은 내부 LED(LEDIndicator) 색과 동일.
    """

    def __init__(self, title: str, parent=None, led_size: int = 12):
        self._title_text = title        # StatusIndicatorBox 인스턴스에 값 할당
        self._led_size = led_size       # StatusIndicatorBox 인스턴스에 값 할당
        super().__init__(parent)        # BaseWidget의 생성자 호출

    def _init_ui(self):
        # --- 위젯 생성 ---
        self._lbl_title = QLabel(self._title_text)
        self._led = LEDIndicator(size=self._led_size)
        self._lbl_state = QLabel("")  # update_data()에서 채워짐

        # --- 레이아웃 ---
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)   # 위젯과 border 의 간격
        layout.setSpacing(6)                    # 위젯 사이의 간격

        layout.addWidget(self._lbl_title)       # 위젯 추가
        layout.addWidget(self._led)
        layout.addWidget(self._lbl_state)

        layout.addStretch(1)    # (오른쪽에 스트레치 채워넣음으로써) 위젯들 왼쪽에 몰아넣기

    def update_data(self, data: dict):
        """
        data: { 'state': 'running', 'title': '새 제목'} 형태의 딕셔너리.
                'state'와 'title' 키가 반드시 포함되어야 합니다.
        """
        # 1. 데이터 추출 (키가 없으면 BaseWidget의 safe_update_data에서 처리됨)
        state = data['state']
        title = data['title']
        
        # 2. 제목 업데이트
        self._title_text = title
        self._lbl_title.setText(title)

        # 3. LED 색 업데이트
        self._led.update_data(state)

        # 4. 상태 텍스트 업데이트
        txt = str(state).capitalize()
        self._lbl_state.setText(txt)

        # 5. 위젯 갱신 (테두리 색상 및 텍스트 변경사항 반영)
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
        # LEDIndicator 에 get_color() 메서드를 하나 만들어 두셔도 됩니다.
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
        # 'title' 키가 없는 경우, 현재 위젯의 제목을 가져와서 채워줌
        if 'title' not in data_dict:
            data_dict['title'] = indicator._title_text
        indicator.safe_update_data(data_dict)

    timer = QTimer()
    timer.timeout.connect(tick)
    timer.start(1000)

    # 초기 한 번
    tick()

    # (6) Qt 메인 루프 실행
    sys.exit(app.exec())