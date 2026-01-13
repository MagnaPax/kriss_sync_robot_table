# ui/widgets/turntable_widget.py
import sys

from typing import Optional
from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QSizePolicy, QHBoxLayout, QGroupBox, QScrollBar
from PyQt6.QtGui import QPainter, QColor, QPen, QPolygonF
from PyQt6.QtCore import Qt, QPointF, QRectF, QSize, QTimer, pyqtProperty, pyqtSignal

from ui.widgets.base_widget import BaseWidget
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
        # (Bird's-eye View: 턴테이블 위의 재료 가공 궤적 - Material Cut Trajectory)
        self._material_cut_angle: float = 0.0          # Material Cut Angle
        self._material_cut_radius_ratio: float = 0.9   # Material Cut Radius Ratio
        self._material_cut_angle: float = 0.0          # Material Cut Angle
        self._material_cut_radius_ratio: float = 0.9   # Material Cut Radius Ratio
        self._robot_z: float = 0.0                     # 로봇 높이 (Z축)
        
        # [Zoom 설정] Radius 기반 확대 (Center Zoom)
        self._zoom_scale: float = 1.0 
        self._min_zoom: float = 0.5
        self._max_zoom: float = 20.0

        # 기본 색상 (QSS에서 덮어씌울 변수들 - 초기값은 검정/흰색 등 의미없는 색상)
        self._circle_color = QColor(Qt.GlobalColor.black)
        self._scale_line_color = QColor(Qt.GlobalColor.black)
        self._scale_text_color = QColor(Qt.GlobalColor.black)
        self._arrow_color = QColor(Qt.GlobalColor.black)
        # 로봇 툴 위치 (Tool Position) - 빨간 점
        self._tool_position_color = QColor(Qt.GlobalColor.black)
        # Material Cut Trajectory (실제 소재 가공 궤적)
        self._material_cut_trajectory_color = QColor(Qt.GlobalColor.lightGray) 
        
        self._waypoints: list = [] # 웨이포인트 목록 [{'material_cut_angle': ..., 'material_cut_radius_ratio': ...}, ...]
    
    # --- Signals ---
    # 먼저 시그널 정의
    zoom_changed_signal = pyqtSignal(float) 
    
    # 그 다음 Property 정의에서 notify에 시그널 전달
    def get_zoom_scale(self): return self._zoom_scale
    def set_zoom_scale(self, scale: float):
        self._zoom_scale = max(self._min_zoom, min(self._max_zoom, scale))
        self.update()
        self.zoom_changed_signal.emit(self._zoom_scale)

    zoomInfo = pyqtProperty(float, get_zoom_scale, set_zoom_scale, notify=zoom_changed_signal)


    # --- QProperty 정의 (Stylesheet 연동용) ---
    def get_circle_color(self): return self._circle_color
    def set_circle_color(self, c): self._circle_color = c; self.update()
    circleColor = pyqtProperty(QColor, get_circle_color, set_circle_color)

    def get_material_cut_trajectory_color(self): return self._material_cut_trajectory_color
    def set_material_cut_trajectory_color(self, c): self._material_cut_trajectory_color = c; self.update()
    materialCutTrajectoryColor = pyqtProperty(QColor, get_material_cut_trajectory_color, set_material_cut_trajectory_color)

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



    def set_data(self, angle: float, material_cut_angle: float, material_cut_radius_ratio: float, robot_z: float):
        """외부(TurntableWidget)에서 각도 데이터를 받아 위젯 갱신"""
        self._angle = angle
        self._material_cut_angle = material_cut_angle
        # 0.0 (중심) ~ 1.0 (테두리) 사이 값으로 제한
        self._material_cut_radius_ratio = max(0.0, min(1.0, material_cut_radius_ratio))
        self._robot_z = robot_z # Z축 높이 (mm)
        self.update()  # -> Qt -> paintEvent() : Qt 에게 paintEvent()를 호출하도록 요청

    def set_waypoints(self, waypoints: list):
        """웨이포인트 목록 업데이트"""
        self._waypoints = waypoints
        self.update()

    def wheelEvent(self, event):
        """마우스 휠로 줌 인/아웃 (Radius Scaling)"""
        delta = event.angleDelta().y()
        # 휠 올리면 확대(+), 내리면 축소(-)
        if delta > 0:
            self._zoom_scale = min(self._max_zoom, self._zoom_scale + 0.5)
        else:
            self._zoom_scale = max(self._min_zoom, self._zoom_scale - 0.5)
        self.update()
        self.zoom_changed_signal.emit(self._zoom_scale) # 시그널 발생
        event.accept()




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
        
        # [핵심] Zoom 적용: 반지름 자체를 키운다. 
        # 이렇게 하면 중심(center)은 그대로이고, 원의 크기만 커지거나 작아짐 = 완벽한 Center Zoom
        radius = (side * 0.4) * self._zoom_scale

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
        
        # Material Cut Trajectory 스타일 (작고 연한 점)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._material_cut_trajectory_color)
        
        # [핵심] 턴테이블과 함께 회전하도록 설정 (재료에 고정된 궤적)
        painter.rotate(self._angle) 

        for wp in self._waypoints:
            material_cut_angle = wp.get('material_cut_angle', 0.0)
            material_cut_radius_ratio = wp.get('material_cut_radius_ratio', 0.0)
            
            painter.save()
            painter.rotate(material_cut_angle)
            
            # 위치 계산
            dist = radius * material_cut_radius_ratio
            pos = QPointF(0, -dist)
            
            # 작은 점 그리기 (궤적이 뭉치지 않게 아주 작게 표현)
            painter.drawEllipse(pos, 0.5, 0.5) # 반지름 0.5 (지름 1px)
            
            painter.restore()
            
        painter.restore()


    def _draw_dynamic_elements(self, painter: QPainter, center: QPointF, radius: float):
        """움직이는 요소 그리기 (화살표와 빨간점)"""
        
        # --- 1. 파란색 화살표 (현재 각도) ---
        painter.save()              # 화가의 현재 상태(좌표계, 펜, 붓 등) 저장
        painter.translate(center)   # 원점을 원의 중심으로 이동
        painter.rotate(self._angle) # 도화지 전체를 '현재 각도(self._angle)'만큼 회전
        
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
        
        # 빨간 점은 로봇의 World 위치이므로, 턴테이블 회전과 무관하게 독립적으로 움직임(처럼 보이지만 값은 상대적?)
        # 아니요, 사용자는 "맞닿을 궤적" 즉 Relative Position을 원함?
        # 아니요, 빨간점은 "현재 툴 위치" -> World 좌표계 -> 그냥 그려야 함.
        # 즉 _material_cut_angle 변수는 현재 시점에서 World와 같음.
        painter.rotate(self._material_cut_angle) # 캔버스 회전

        
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
        dot_distance_from_center = radius * self._material_cut_radius_ratio
        
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
class TurntableGauge(BaseWidget):
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
        # --- 레이아웃 설정: ScrollBar 추가를 위해 구조 변경 ---
        # 기존: QVBoxLayout -> QHBoxLayout(Gauge)
        # 변경: QVBoxLayout -> QHBoxLayout(Gauge + ScrollBar)
        
        layout = QVBoxLayout(self)  # 메인 수직 레이아웃
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # 수평 컨테이너 (게이지 + 스크롤바)
        container_layout = QHBoxLayout()
        
        # 1. 왼쪽 빈공간 (중앙 정렬용)
        container_layout.addStretch(1)

        # 2. 원형 게이지 (커스텀 위젯)
        self.gauge_widget = _GaugePainter()
        self.gauge_widget.setObjectName("turntable_gauge_painter")
        container_layout.addWidget(self.gauge_widget, stretch=0) # stretch 0으로 고정 크기 유지 시도

        # 3. 줌 조절 스크롤바 (Vertical)
        self.scroll_bar = QScrollBar(Qt.Orientation.Vertical)
        self.scroll_bar.setObjectName("zoom_scrollbar") # QSS ID 설정
        self.scroll_bar.setRange(5, 200) # 0.5x ~ 20.0x (x10 scaling)
        self.scroll_bar.setValue(10)     # Default 1.0x
        self.scroll_bar.setInvertedAppearance(True) # 위로 갈수록 커지게 (일반적 Zoom UI)
        self.scroll_bar.setFixedWidth(15)
        self.scroll_bar.setToolTip("Zoom In/Out")
        
        # 스크롤바 시그널 연결
        self.scroll_bar.valueChanged.connect(self._on_scrollbar_value_changed)
        # 게이지 휠 이벤트 시그널 연결
        self.gauge_widget.zoom_changed_signal.connect(self._on_gauge_zoom_changed)

        container_layout.addWidget(self.scroll_bar)

        # 4. 오른쪽 빈공간
        container_layout.addStretch(1)

        layout.addLayout(container_layout)

        # ViewModel은 외부(MainVeiwModel)에서 set_view_model()을 통해 주입받음
        self.view_model: Optional[TurntableGaugeViewModel] = None

    def _on_scrollbar_value_changed(self, value):
        """스크롤바 값 변경 -> 게이지 줌 변경"""
        # 스크롤바 값(5~200) -> 줌 스케일(0.5 ~ 20.0)
        scale = value / 10.0
        # 시그널 루프 방지를 위해 blockSignals 할 수도 있으나,
        # set_zoom_scale 내부에서 값을 체크하거나, 단방향 흐름이므로 괜찮음.
        # 하지만 무한 루프 방지를 위해 값 비교
        if abs(self.gauge_widget._zoom_scale - scale) > 0.01:
             self.gauge_widget.set_zoom_scale(scale)

    def _on_gauge_zoom_changed(self, scale):
        """게이지 휠 줌 변경 -> 스크롤바 값 동기화"""
        val = int(scale * 10)
        if self.scroll_bar.value() != val:
            self.scroll_bar.setValue(val)

    def set_view_model(self, vm: TurntableGaugeViewModel):
        """외부에서 ViewModel 주입"""
        self.view_model = vm
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
        # "Material Cut" - 소재 가공 궤적
        material_cut_angle = float(data.get('material_cut_angle', 0.0))
        material_cut_radius_ratio = float(data.get('material_cut_radius_ratio', 0.9))

        rounds = int(data.get('rounds', 0))
        state = str(data.get('state', 'waiting'))

        # 추가 데이터 추출 (View 표시용)
        robot_z = float(data.get('robot_z', 0.0))
        robot_f = float(data.get('robot_f', 0.0))
        turntable_vel = float(data.get('servo_turntable_vel', 0.0))


        # 게이지 위젯에 값 전달
        self.gauge_widget.set_data(angle, material_cut_angle, material_cut_radius_ratio, robot_z)

    def clear_widget(self):
        """위젯 초기화 -> 초기 상태값 딕셔너리 전달"""
        self.update_data({
            'angle': 0.0,
            'material_cut_angle': 0.0,
            'material_cut_radius_ratio': 0.0,
            'rounds': 0,
            'state': 'off'
        })
        super().clear_widget()


# ==========================================================
# 4. 외부 공개용 Wrapper Class (GroupBox 포함)
#    : LeftPanel 등에서 이 클래스를 사용
# ==========================================================
class TurntableGaugeWidget(BaseWidget):
    """
    TurntableGauge를 Bird's-eye View GroupBox로 감싸서 제공하는 래퍼 위젯.
    LeftPanel 등의 UI에서는 이 클래스를 인스턴스화하여 사용한다.
    """
    
    def _init_ui(self):
        # 1. 메인 레이아웃 (여백 제거)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # 2. GroupBox 생성 (로직 이동됨 - Encapsulation)
        self.group_box = QGroupBox("Bird's-eye View")
        group_layout = QVBoxLayout(self.group_box)
        
        # 3. 실제 기능 위젯(TurntableGauge) 생성 및 추가
        self.gauge = TurntableGauge()
        
        # 4. Layout 배치 (위아래 Stretch로 중앙 정렬)
        group_layout.addStretch(1)
        group_layout.addWidget(self.gauge)
        group_layout.addStretch(1)
        
        # 5. GroupBox를 메인 레이아웃에 추가
        main_layout.addWidget(self.group_box)

    def update_data(self, data: dict):
        """데이터 업데이트 위임"""
        # ViewModel이 내부 TurntableGauge에 직접 연결되어 있어 사실상 불필요할 수 있으나,
        # 외부에서 명시적으로 update_data 호출 시 전달 역할.
        if hasattr(self, 'gauge'):
            self.gauge.update_data(data)

    def set_view_model(self, vm: TurntableGaugeViewModel):
        """ViewModel 주입 위임"""
        if hasattr(self, 'gauge'):
            self.gauge.set_view_model(vm)

    def clear_widget(self):
        """초기화 위임"""
        if hasattr(self, 'gauge'):
            self.gauge.clear_widget()


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
        'material_cut_angle': 270.0, # 빨간 점 초기 위치
        'material_cut_radius_ratio': 0.9, # 반지름 90%에서 시작
        'state': 'running'
    }

    # 반지름이 움직이는 방향 (1: 바깥쪽, -1: 안쪽)
    radius_direction = -1    

    def update_test():
        # 전역 변수인 radius_direction을 수정하겠다고 선언
        global radius_direction

        test_data['angle'] = (float(test_data['angle']) + 1.5) % 360
        test_data['material_cut_angle'] = (float(test_data['material_cut_angle']) - 0.5) % 360


        # 빨간 점이 안팎으로 움직이는 애니메이션
        rad_perc = float(test_data['material_cut_radius_ratio'])

        if rad_perc <= 0.1: # 중심(10%)에 가까워지면
            radius_direction = 1 # 밖으로 이동
        elif rad_perc >= 0.9: # 테두리(90%)에 가까워지면
            radius_direction = -1 # 안으로 이동
            
        # 0.01 (1%)씩 방향에 따라 증감
        rad_perc += (0.01 * radius_direction)
        test_data['material_cut_radius_ratio'] = rad_perc        


        if int(test_data['angle']) % 90 < 2:
             test_data['state'] = 'waiting'
             # 0도 통과 시 라운드 증가
             if float(test_data['angle']) < 2:
                 test_data['rounds'] = int(test_data['rounds']) + 1
        elif int(test_data['angle']) % 45 < 2: # 45도 근처에서 'running'
             test_data['state'] = 'running'
        
        # Wrapper의 경우 update_data가 내부 gauge로 전달되는지 테스트
        test_widget.safe_update_data(test_data)

    timer = QTimer()
    timer.timeout.connect(update_test)
    timer.start(50) # 50ms (0.05초)

    sys.exit(app.exec())