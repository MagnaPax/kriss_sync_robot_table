# ui/widgets/turntable_widget.py
import sys
import os
import math

from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QSizePolicy, QHBoxLayout
)
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QPolygonF
)
from PyQt6.QtCore import Qt, QPointF, QRectF, QSize, QTimer

from .base_widget import BaseWidget
from .led_indicator import LEDIndicator
from .status_indicator_box import StatusIndicatorBox



# ==========================================================
# 1. 커스텀 게이지 드로잉 위젯 (내부용)
# ==========================================================
class _GaugePainter(QWidget):
    """QPainter를 사용하여 원형 턴테이블 게이지를 그리는 위젯"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(200, 200)
        # 위젯의 크기가 변할 때 가로/세로 비율을 유지하며 확장되도록 설정
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        self._angle: float = 0.0                # 현재 테이블 각도
        self._robot_angle: float = 0.0          # 현재 로봇 각도
        self._robot_radius_percent: float = 0.9 # 로봇의 반지름 위치(기본값 90%)


    def set_data(self, angle: float, robot_angle: float, robot_radius_percent: float):
        """외부(TurntableWidget)에서 각도 데이터를 받아 위젯 갱신"""
        self._angle = angle
        self._robot_angle = robot_angle
        # 0.0 (중심) ~ 1.0 (테두리) 사이 값으로 제한
        self._robot_radius_percent = max(0.0, min(1.0, robot_radius_percent))
        self.update()  # -> Qt -> paintEvent() : Qt 에게 paintEvent()를 호출하도록 요청


    def paintEvent(self, event) -> None:  # type: ignore[override]
        """
        위젯 그리기 (핵심 로직)
        
        Qt 가 다시 그려야 되겠다고 판단할 때마다 자동으로 호출된다
        - self.update() 호출될 때
        - 창이 가려졌다가 다시 나타날 때 등 
        """

        painter = QPainter(self)    # 화가 객체 생성. 도화지는 self(_GaugePainter 위젯)라고 알림
        painter.setRenderHint(QPainter.RenderHint.Antialiasing) # 부드럽게(Anti-aliasing) 그리기

        # 1. 좌표계 설정 (정사각형 기준)
        side = min(self.width(), self.height())     # 창이 직사각형 되어도 게이지 찌그러지지 않게
        center = QPointF(self.width() / 2, self.height() / 2)
        radius = side * 0.4  # 40% (텍스트를 위한 여백)

        # 2. 정적 요소 그리기 (원, 텍스트, 0도선)
        self._draw_static_background(painter, center, radius)

        # 3. 동적 요소 그리기 (빨간 점, 파란 화살표)
        self._draw_dynamic_elements(painter, center, radius)


    def _draw_static_background(self, painter: QPainter, center: QPointF, radius: float):
        """정적 배경 그리기 (원, 각도, 0도 기준선 등)"""
        
        # 1. 파란색 원
        painter.setPen(QPen(QColor("#007BFF"), 3))
        painter.setBrush(Qt.BrushStyle.NoBrush)     # 색 채우기 없음(테두리만)
        painter.drawEllipse(center, radius, radius) # 원 그리기
        
        # 2. 0도 기준선 (회색 점선)
        painter.setPen(QPen(QColor(Qt.GlobalColor.gray), 2, Qt.PenStyle.DashLine))
        painter.drawLine(QPointF(center.x(), center.y()), QPointF(center.x(), center.y() - radius))

        # 3. 턴테이블 밖 각도 표시 (0°, 90°, 180°, 270°)
        painter.setPen(QColor("#666666"))
        font = painter.font()
        font.setPointSize(10)
        painter.setFont(font)
        
        text_radius = radius + 15
        painter.drawText(QRectF(center.x() - 20, center.y() - text_radius - 10, 40, 20), Qt.AlignmentFlag.AlignCenter, "0°")
        painter.drawText(QRectF(center.x() + text_radius - 10, center.y() - 10, 40, 20), Qt.AlignmentFlag.AlignLeft, "90")
        painter.drawText(QRectF(center.x() - 20, center.y() + text_radius - 10, 40, 20), Qt.AlignmentFlag.AlignCenter, "180")
        painter.drawText(QRectF(center.x() - text_radius - 30, center.y() - 10, 40, 20), Qt.AlignmentFlag.AlignRight, "270")


    def _draw_dynamic_elements(self, painter: QPainter, center: QPointF, radius: float):
        """움직이는 요소 그리기 (화살표와 빨간점)"""
        
        # --- 1. 파란색 화살표 (현재 각도) ---
        painter.save()              # 화가의 현재 상태(좌표계, 펜, 붓 등) 저장
        painter.translate(center)   # 원점을 원의 중심으로 이동
        painter.rotate(self._angle) # 도화지 전체를 '현재 각도(self._angle)'만큼 회전
        
        arrow_color = QColor("#3498db")
        painter.setPen(QPen(arrow_color, 4, Qt.PenStyle.SolidLine))
        # 회전된 도화지의 정중앙(0,0)에서 12시 방향(0, -반지름*0.85)으로 파란색 선(화살표 몸통) 그리기
        painter.drawLine(QPointF(0, 0), QPointF(0, -radius * 0.85)) 

        # 화살촉(삼각형)
        arrow_head = QPolygonF([
            QPointF(0, -radius * 0.9),
            QPointF(-6, -radius * 0.9 + 18),
            QPointF(6, -radius * 0.9 + 18)
        ])
        painter.setBrush(arrow_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(arrow_head)
        
        painter.restore() # painter.save() 했던 상태로 복원 (회전/이동하기 전으로 리셋)

        # --- 2. 빨간색 점 (로봇 위치) ---
        """
        위의 파란 화살표와 똑같은 구조

        save(): 저장 ➔ translate(center): 중앙 이동 ➔ rotate(self._robot_angle): 로봇 각도만큼 회전 ➔ drawEllipse(...): 12시 방향에 빨간 점 그리기 ➔ restore(): 복원
        """
        painter.save()
        painter.translate(center)
        painter.rotate(self._robot_angle) # 로봇 각도만큼 캔버스 회전

        # 중심으로부터의 거리를 _robot_radius_percent로 계산
        dot_distance_from_center = radius * self._robot_radius_percent
        
        # dot_pos = QPointF(0, -radius * 0.9)
        # 12시 방향(위쪽)으로 dot_distance_from_center 만큼 떨어진 곳에 점을 그림
        dot_pos = QPointF(0, -dot_distance_from_center)        
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("red"))
        painter.drawEllipse(dot_pos, 4, 4)
        
        painter.restore()

    def resizeEvent(self, event): # type: ignore[override]
        """
        위젯 크기가 변해도 정사각형 모양이 찌그러지지 않게 비율을 유지하도록 강제
        Qt의 윈도우 시스템(이벤트 루프)에 의해 자동으로 호출 되는 콜백함수
        PySide6.QtWidgets.QGraphicsWidget.resizeEvent
        """

        # 가로/세로 중 작은 사이즈 저장
        new_size = min(event.size().width(), event.size().height()) 
        # 작은 길이에 맞게 위젯 크기 재설정(게이지 찌그러지지 않는 비결)
        self.resize(new_size, new_size)     
        super().resizeEvent(event)

    def sizeHint(self):
        """레이아웃에 적절한 크기 힌트 제공"""
        return QSize(220, 220)


# ==========================================================
# 2. 메인 턴테이블 위젯 (조립)
# ==========================================================
class TurntableWidget(BaseWidget):
    """
    턴테이블 게이지 메인 위젯
    - 게이지, 텍스트, 상태창을 조립
    - BaseWidget을 상속받아 update_data 인터페이스 구현
    """

    def _init_ui(self):
        """
        BaseWidget의 _init_ui를 override(재정의)
        BaseWidget의 __init__이 실행될 때 자동으로 호출 됨
        """
        layout = QVBoxLayout(self)  # 수직 레이아웃
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)  # 위에 붙어있게 정렬

        # 원형 게이지 (커스텀 위젯)
        self.gauge_widget = _GaugePainter()     # 객체 생성
        # 1) 가로 중앙 정렬 위해 수평 레이아웃으로 감싸기
        gaugebox = QHBoxLayout()
        gaugebox.addStretch(1)                              # ← 왼쪽 빈공간
        gaugebox.addWidget(self.gauge_widget, stretch=1)    # ← 가운데 게이지(늘어남)
        gaugebox.addStretch(1)                              # ← 오른쪽 빈공간
        # 2) 이 HBox를 VBox에 stretch=1 로 추가
        layout.addLayout(gaugebox, stretch=1)

        # 디지털 텍스트(회전횟수, 각도 표시)
        self.digital_readout = QLabel("00 rounds 0.0°")
        self.digital_readout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.digital_readout.setStyleSheet("font-size: 18px; font-weight: bold; margin-top: 5px;")
        layout.addWidget(self.digital_readout, stretch=0)

        # 상태 표시줄 (StatusIndicatorBox 위젯 사용)
        self.state_indicator = StatusIndicatorBox("TurnTable State", led_size=10)
        layout.addWidget(self.state_indicator, stretch=0)

    def update_data(self, data: dict):
        """
        BaseWidget의 추상 메서드(update_data) 구현

        Controller(혹은 ViewModel)가 아래 형태의 데이터를 전달해 줄 것이라고 가정
        
        Args:
            data (dict): {'angle': float, 'robot_angle': float, 'rounds': int, 'state': str}
        """
        # 데이터 추출
        angle = data.get('angle', 0.0)
        robot_angle = data.get('robot_angle', 0.0)

        # 로봇 반지름 위치 추출 (기본값: 0.9 = 90% 테두리)
        robot_radius_percent = data.get('robot_radius_percent', 0.9)        

        rounds = data.get('rounds', 0)
        state = data.get('state', 'waiting')

        # 게이지 위젯에 값 전달
        # self.gauge_widget.set_data(angle, robot_angle)
        self.gauge_widget.set_data(angle, robot_angle, robot_radius_percent)

        # 디지털 텍스트에 값 전달
        self.digital_readout.setText(f"{rounds:02d} rounds {angle:.1f}°")

        # 상태 표시줄 갱신
        state_data = {
            'state': state,
            'title': self.state_indicator._title_text # 기존 제목 유지
        }
        self.state_indicator.safe_update_data(state_data)

    def clear_widget(self):
        """위젯 초기화 -> 초기 상태값 딕셔너리 전달"""
        self.update_data({
            'angle': 0.0,
            'robot_angle': 0.0,
            'robot_radius_percent': 0.0,
            'rounds': 0,
            'state': 'off'
        })
        super().clear_widget()


# ==========================================================
# 3. 단독 실행 (테스트용)
"""
python -m ui.widgets.gau_G
"""
# ==========================================================
if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    main_window = QWidget()
    main_layout = QVBoxLayout(main_window)
    
    test_widget = TurntableWidget()
    main_layout.addWidget(test_widget)
    main_window.setWindowTitle("TurntableWidget 단독 테스트")
    main_window.resize(300, 450)
    main_window.show()

    # 테스트용 데이터
    test_data = {
        'angle': 0.0,
        'rounds': 0,
        'robot_angle': 270.0, # 빨간 점 초기 위치
        'robot_radius_percent': 0.9, # 반지름 90%에서 시작
        'state': 'running'
    }

    # 반지름이 움직이는 방향 (1: 바깥쪽, -1: 안쪽)
    radius_direction = -1    

    def update_test():
        # 전역 변수인 radius_direction을 수정하겠다고 선언
        global radius_direction

        test_data['angle'] = (test_data['angle'] + 1.5) % 360
        test_data['robot_angle'] = (test_data['robot_angle'] - 0.5) % 360


        # 빨간 점이 안팎으로 움직이는 애니메이션
        rad_perc = test_data['robot_radius_percent']

        if rad_perc <= 0.1: # 중심(10%)에 가까워지면
            radius_direction = 1 # 밖으로 이동
        elif rad_perc >= 0.9: # 테두리(90%)에 가까워지면
            radius_direction = -1 # 안으로 이동
            
        # 0.01 (1%)씩 방향에 따라 증감
        rad_perc += (0.01 * radius_direction)
        test_data['robot_radius_percent'] = rad_perc        


        # 90도 근처에서 'waiting' 상태로 변경
        if int(test_data['angle']) % 90 < 2:
             test_data['state'] = 'waiting'
             # 0도 통과 시 라운드 증가
             if test_data['angle'] < 2:
                 test_data['rounds'] += 1
        elif int(test_data['angle']) % 45 < 2: # 45도 근처에서 'running'
             test_data['state'] = 'running'

        test_widget.safe_update_data(test_data)

    timer = QTimer()
    timer.timeout.connect(update_test)
    timer.start(50) # 50ms (0.05초)

    sys.exit(app.exec())