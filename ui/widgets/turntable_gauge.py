# ui/widgets/turntable_widget.py
import sys

from typing import Optional
from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QSizePolicy, QHBoxLayout
from PyQt6.QtGui import QPainter, QColor, QPen, QPolygonF
from PyQt6.QtCore import Qt, QPointF, QRectF, QSize, QTimer, pyqtProperty

from ui.widgets.base_widget import BaseWidget
from ui.widgets.status_indicator_box import StatusIndicatorBox
from view_models.turntable_gauge_viewmodel import TurntableGaugeViewModel



# ==========================================================
# 1. 커스텀 게이지 드로잉 위젯 (내부용)
# ==========================================================
class _GaugePainter(QWidget):
    """QPainter를 사용하여 원형 턴테이블 게이지를 그리는 위젯"""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumSize(200, 200)
        # 위젯의 크기가 변할 때 가로/세로 비율을 유지하며 확장되도록 설정
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        self._angle: float = 0.0                # 현재 테이블 각도
        # [시각화 전용 변수] 직교 좌표계(X,Y)를 원형 게이지에 그리기 위해 각도/거리로 변환한 값
        # (Bird's-eye View: 위에서 내려다본 Robot X Move (로봇 X축 이동) 평면상 위치)
        self._robot_x_move_angle: float = 0.0          # Robot X Move Angle
        self._robot_x_move_radius_ratio: float = 0.9   # Robot X Move Radius Ratio
        self._robot_z: float = 0.0                     # 로봇 높이 (Z축)

        # 기본 색상 (QSS에서 덮어씌울 변수들 - 초기값은 검정/흰색 등 의미없는 색상)
        self._circle_color = QColor(Qt.GlobalColor.black)
        self._scale_line_color = QColor(Qt.GlobalColor.black)
        self._scale_text_color = QColor(Qt.GlobalColor.black)
        self._arrow_color = QColor(Qt.GlobalColor.black)
        # 로봇 툴 위치 (Tool Position) - 빨간 점
        self._tool_position_color = QColor(Qt.GlobalColor.black)
        # 웨이포인트 -> Robot X Move Trajectory (로봇 X축 이동 궤적)
        self._robot_x_move_trajectory_color = QColor(Qt.GlobalColor.lightGray) 
        
        self._waypoints: list = [] # 웨이포인트 목록 [{'robot_x_move_angle': ..., 'robot_x_move_radius_ratio': ...}, ...]

    # --- QProperty 정의 (Stylesheet 연동용) ---
    def get_circle_color(self): return self._circle_color
    def set_circle_color(self, c): self._circle_color = c; self.update()
    circleColor = pyqtProperty(QColor, get_circle_color, set_circle_color)

    def get_robot_x_move_trajectory_color(self): return self._robot_x_move_trajectory_color
    def set_robot_x_move_trajectory_color(self, c): self._robot_x_move_trajectory_color = c; self.update()
    robotXMoveTrajectoryColor = pyqtProperty(QColor, get_robot_x_move_trajectory_color, set_robot_x_move_trajectory_color)

    def get_scale_line_color(self): return self._scale_line_color
    def set_scale_line_color(self, c): self._scale_line_color = c; self.update()
    scaleLineColor = pyqtProperty(QColor, get_scale_line_color, set_scale_line_color)

    def get_scale_text_color(self): return self._scale_text_color
    def set_scale_text_color(self, c): self._scale_text_color = c; self.update()
    scaleTextColor = pyqtProperty(QColor, get_scale_text_color, set_scale_text_color)

    def get_arrow_color(self): return self._arrow_color
    def set_arrow_color(self, c): self._arrow_color = c; self.update()
    arrowColor = pyqtProperty(QColor, get_arrow_color, set_arrow_color)

    def get_tool_position_color(self): return self._tool_position_color
    def set_tool_position_color(self, c): self._tool_position_color = c; self.update()
    toolPositionColor = pyqtProperty(QColor, get_tool_position_color, set_tool_position_color)



    def set_data(self, angle: float, robot_x_move_angle: float, robot_x_move_radius_ratio: float, robot_z: float):
        """외부(TurntableWidget)에서 각도 데이터를 받아 위젯 갱신"""
        self._angle = angle
        self._robot_x_move_angle = robot_x_move_angle
        # 0.0 (중심) ~ 1.0 (테두리) 사이 값으로 제한
        self._robot_x_move_radius_ratio = max(0.0, min(1.0, robot_x_move_radius_ratio))
        self._robot_z = robot_z # Z축 높이 (mm)
        self.update()  # -> Qt -> paintEvent() : Qt 에게 paintEvent()를 호출하도록 요청

    def set_waypoints(self, waypoints: list):
        """웨이포인트 목록 업데이트"""
        self._waypoints = waypoints
        self.update()


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

        # 3. 웨이포인트 그리기 (정적 배경 위에, 동적 요소 아래에)
        self._draw_waypoints(painter, center, radius)

        # 4. 동적 요소 그리기 (빨간 점, 파란 화살표)
        self._draw_dynamic_elements(painter, center, radius)


    def _draw_static_background(self, painter: QPainter, center: QPointF, radius: float):
        """정적 배경 그리기 (원, 각도, 0도 기준선 등)"""
        
        # 1. 파란색 원
        painter.setPen(QPen(self._circle_color, 3))
        painter.setBrush(Qt.BrushStyle.NoBrush)     # 색 채우기 없음(테두리만)
        painter.drawEllipse(center, radius, radius) # 원 그리기
        
        # 2. 0도 기준선 (회색 점선)
        painter.setPen(QPen(self._scale_line_color, 2, Qt.PenStyle.DashLine))
        painter.drawLine(QPointF(center.x(), center.y()), QPointF(center.x(), center.y() - radius))

        # 3. 턴테이블 밖 각도 표시 (0°, 90°, 180°, 270°)
        painter.setPen(self._scale_text_color)
        font = painter.font()
        font.setPointSize(10)
        painter.setFont(font)
        
        text_radius = radius + 15
        painter.drawText(QRectF(center.x() - 20, center.y() - text_radius - 10, 40, 20), Qt.AlignmentFlag.AlignCenter, "0°")
        painter.drawText(QRectF(center.x() + text_radius - 10, center.y() - 10, 40, 20), Qt.AlignmentFlag.AlignLeft, "90")
        painter.drawText(QRectF(center.x() - 20, center.y() + text_radius - 10, 40, 20), Qt.AlignmentFlag.AlignCenter, "180")
        painter.drawText(QRectF(center.x() - text_radius - 30, center.y() - 10, 40, 20), Qt.AlignmentFlag.AlignRight, "270")

    def _draw_waypoints(self, painter: QPainter, center: QPointF, radius: float):
        """웨이포인트 목록 그리기"""
        if not self._waypoints:
            return

        painter.save()
        painter.translate(center)
        
        # Robot X Move Trajectory 스타일 (작고 연한 점)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._robot_x_move_trajectory_color)
        
        for wp in self._waypoints:
            robot_x_move_angle = wp.get('robot_x_move_angle', 0.0)
            robot_x_move_radius_ratio = wp.get('robot_x_move_radius_ratio', 0.0)
            
            painter.save()
            painter.rotate(robot_x_move_angle)
            
            # 위치 계산
            dist = radius * robot_x_move_radius_ratio
            pos = QPointF(0, -dist)
            
            # 작은 점 그리기
            painter.drawEllipse(pos, 3, 3) # 반지름 3
            
            painter.restore()
            
        painter.restore()


    def _draw_dynamic_elements(self, painter: QPainter, center: QPointF, radius: float):
        """움직이는 요소 그리기 (화살표와 빨간점)"""
        
        # --- 1. 파란색 화살표 (현재 각도) ---
        painter.save()              # 화가의 현재 상태(좌표계, 펜, 붓 등) 저장
        painter.translate(center)   # 원점을 원의 중심으로 이동
        painter.rotate(self._angle) # 도화지 전체를 '현재 각도(self._angle)'만큼 회전
        
        # arrow_color = QColor("#3498db")
        painter.setPen(QPen(self._arrow_color, 4, Qt.PenStyle.SolidLine))
        # 회전된 도화지의 정중앙(0,0)에서 12시 방향(0, -반지름*0.85)으로 파란색 선(화살표 몸통) 그리기
        painter.drawLine(QPointF(0, 0), QPointF(0, -radius * 0.85)) 

        # 화살촉(삼각형)
        arrow_head = QPolygonF([
            QPointF(0, -radius * 0.9),
            QPointF(-6, -radius * 0.9 + 18),
            QPointF(6, -radius * 0.9 + 18)
        ])

        painter.setBrush(self._arrow_color)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(arrow_head)
        
        painter.restore() # painter.save() 했던 상태로 복원 (회전/이동하기 전으로 리셋)

        # --- 2. 빨간색 점 (로봇 위치) ---
        """
        위의 파란 화살표와 똑같은 구조

        save(): 저장 ➔ translate(center): 중앙 이동 ➔ rotate(self._robot_visual_angle): 로봇 각도만큼 회전 ➔ drawEllipse(...): 12시 방향에 빨간 점 그리기 ➔ restore(): 복원
        """
        painter.save()
        painter.translate(center)
        painter.rotate(self._robot_x_move_angle) # Robot X Move Angle만큼 캔버스 회전

        
        # [Z축 시각화 로직]
        # Z값이 0(바닥)에 가까울수록 진하게(Opaque) + 작게(Small) (핀포인트 느낌)
        # Z값이 클수록(위로 갈수록) 연하게(Transparent) + 크게(Large) (퍼지는 느낌)
        
        # 기준 높이 설정 (예: 0mm ~ 300mm)
        MAX_Z = 300.0
        z_clamped = max(0.0, min(float(self._robot_z), MAX_Z))
        
        # intensity: 1.0 (바닥/Close) ~ 0.0 (최대 높이/Far)
        intensity = 1.0 - (z_clamped / MAX_Z) 
        
        # 크기 계산: intensity가 클수록(가까울수록) 작아야 함
        # intensity 1.0 -> 4 (최소)
        # intensity 0.0 -> 10 (최대)
        dot_radius = 10 - (intensity * 6)
        
        # 색상 계산: intensity가 클수록(가까울수록) 진해야 함 (변경 없음)
        dot_color = QColor(self._tool_position_color)
        alpha = int(50 + (intensity * 205)) # 최소 50 ~ 최대 255
        dot_color.setAlpha(alpha)


        # 중심으로부터의 거리를 비율(ratio)로 계산
        dot_distance_from_center = radius * self._robot_x_move_radius_ratio
        
        # 12시 방향(위쪽)으로 dot_distance_from_center 만큼 떨어진 곳에 점을 그림
        dot_pos = QPointF(0, -dot_distance_from_center)        
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(dot_color)
        
        # 원 그리기 (반지름 적용)
        painter.drawEllipse(dot_pos, dot_radius, dot_radius)
        
        painter.restore()

    def resizeEvent(self, event): # type: ignore[override]
        """
        위젯 크기가 변해도 정사각형 모양이 찌그러지지 않게 비율을 유지하도록 강제
        Qt의 윈도우 시스템(이벤트 루프)에 의해 자동으로 호출 되는 콜백함수
        PySide6.QtWidgets.QGraphicsWidget.resizeEvent
        """

        # 가로/세로 중 작은 사이즈 저장
        new_size = int(min(event.size().width(), event.size().height()))
        # 작은 길이에 맞게 위젯 크기 재설정(게이지 찌그러지지 않는 비결)
        self.resize(new_size, new_size)     
        super().resizeEvent(event)

    def sizeHint(self):
        """레이아웃에 적절한 크기 힌트 제공"""
        return QSize(220, 220)


# ==========================================================
# 2. 메인 턴테이블 위젯 (조립)
# ==========================================================
class TurntableGaugeWidget(BaseWidget):
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
        self.gauge_widget.setObjectName("turntable_gauge_painter") # QSS ID 설정 (커스텀 속성 적용용)

        # 1) 가로 중앙 정렬 위해 수평 레이아웃으로 감싸기
        gaugebox = QHBoxLayout()
        gaugebox.addStretch(1)                              # ← 왼쪽 빈공간
        gaugebox.addWidget(self.gauge_widget, stretch=1)    # ← 가운데 게이지(늘어남)
        gaugebox.addStretch(1)                              # ← 오른쪽 빈공간
        # 2) 이 HBox를 VBox에 stretch=1 로 추가
        layout.addLayout(gaugebox, stretch=1)

        # 디지털 텍스트(회전횟수, 각도 표시)
        self.digital_readout = QLabel("00 rounds 0.0°")
        self.digital_readout.setObjectName("turntable_readout")
        self.digital_readout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # layout.addWidget(self.digital_readout, stretch=0)

        # 상태 표시줄 (StatusIndicatorBox 위젯 사용)
        self.state_indicator = StatusIndicatorBox("TurnTable State", led_size=10)
        # layout.addWidget(self.state_indicator, stretch=0)

        # ViewModel 생성 및 연결
        self.view_model = TurntableGaugeViewModel()
        self.view_model.ui_data_updated.connect(self.update_data)
        self.view_model.waypoints_updated.connect(self.update_waypoints)

    def update_waypoints(self, waypoints: list):
        """ViewModel -> 웨이포인트 데이터 수신 -> GaugeWidget 전달"""
        self.gauge_widget.set_waypoints(waypoints)

    def update_data(self, data: dict):
        """
        BaseWidget의 추상 메서드(update_data) 구현

        Controller(혹은 ViewModel)가 아래 형태의 데이터를 전달해 줄 것이라고 가정
        
        Args:
            data (dict): {'angle': float, 'robot_angle': float, 'rounds': int, 'state': str}
        """
        # 데이터 추출
        angle = float(data.get('angle', 0.0))
        # 로봇 시각화 데이터 (ViewModel에서 계산됨)
        # "Robot X Move" - 로봇 X축(및 평면) 이동 시각화
        robot_x_move_angle = float(data.get('robot_x_move_angle', 0.0))
        robot_x_move_radius_ratio = float(data.get('robot_x_move_radius_ratio', 0.9))

        rounds = int(data.get('rounds', 0))
        state = str(data.get('state', 'waiting'))

        # 추가 데이터 추출 (View 표시용)
        robot_z = float(data.get('robot_z', 0.0))
        robot_f = float(data.get('robot_f', 0.0))
        turntable_vel = float(data.get('servo_turntable_vel', 0.0))


        # 게이지 위젯에 값 전달
        # self.gauge_widget.set_data(angle, robot_x_move_angle)
        self.gauge_widget.set_data(angle, robot_x_move_angle, robot_x_move_radius_ratio, robot_z)

        # 디지털 텍스트에 값 전달
        # 포맷: [회전수] [각도 / 속도] | [Z높이 / f속도]
        # 예: 05 rounds 120.5° (10.0°/s) | Z: 150.0mm F: 50.0%
        text = (
            f"{rounds:02d} rounds {angle:.1f}° ({turntable_vel:.1f}°/s)\n"
            f"Z: {robot_z:.1f}mm  F: {robot_f:.1f}"
        )
        self.digital_readout.setText(text)

        # 상태 표시줄 갱신
        state_data = {
            'state': state, # type: ignore
            'title': self.state_indicator._title_text # type: ignore # 기존 제목 유지
        }
        self.state_indicator.safe_update_data(state_data)

    def clear_widget(self):
        """위젯 초기화 -> 초기 상태값 딕셔너리 전달"""
        self.update_data({
            'angle': 0.0,
            'robot_x_move_angle': 0.0,
            'robot_x_move_radius_ratio': 0.0,
            'rounds': 0,
            'state': 'off'
        })
        super().clear_widget()


# ==========================================================
# 3. 단독 실행 (테스트용)
"""
python -m ui.widgets.turntable_gauge
"""
# ==========================================================
if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    main_window = QWidget()
    main_layout = QVBoxLayout(main_window)
    
    test_widget = TurntableGaugeWidget()
    main_layout.addWidget(test_widget)
    main_window.setWindowTitle("TurntableGaugeWidget 단독 테스트")
    main_window.resize(300, 450)
    main_window.show()

    # 테스트용 데이터
    test_data = {
        'angle': 0.0,
        'rounds': 0,
        'robot_x_move_angle': 270.0, # 빨간 점 초기 위치
        'robot_x_move_radius_ratio': 0.9, # 반지름 90%에서 시작
        'state': 'running'
    }

    # 반지름이 움직이는 방향 (1: 바깥쪽, -1: 안쪽)
    radius_direction = -1    

    def update_test():
        # 전역 변수인 radius_direction을 수정하겠다고 선언
        global radius_direction

        test_data['angle'] = (float(test_data['angle']) + 1.5) % 360
        test_data['robot_x_move_angle'] = (float(test_data['robot_x_move_angle']) - 0.5) % 360


        # 빨간 점이 안팎으로 움직이는 애니메이션
        rad_perc = float(test_data['robot_x_move_radius_ratio'])

        if rad_perc <= 0.1: # 중심(10%)에 가까워지면
            radius_direction = 1 # 밖으로 이동
        elif rad_perc >= 0.9: # 테두리(90%)에 가까워지면
            radius_direction = -1 # 안으로 이동
            
        # 0.01 (1%)씩 방향에 따라 증감
        rad_perc += (0.01 * radius_direction)
        test_data['robot_x_move_radius_ratio'] = rad_perc        


        # 90도 근처에서 'waiting' 상태로 변경
        if int(test_data['angle']) % 90 < 2:
             test_data['state'] = 'waiting'
             # 0도 통과 시 라운드 증가
             if float(test_data['angle']) < 2:
                 test_data['rounds'] = int(test_data['rounds']) + 1
        elif int(test_data['angle']) % 45 < 2: # 45도 근처에서 'running'
             test_data['state'] = 'running'

        test_widget.safe_update_data(test_data)

    timer = QTimer()
    timer.timeout.connect(update_test)
    timer.start(50) # 50ms (0.05초)

    sys.exit(app.exec())