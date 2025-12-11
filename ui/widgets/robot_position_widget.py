# ui/widgets/robot_position_widget.py
import sys
import math # 역기구학(Inverse Kinematics, IK) 계산을 위해

from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QSizePolicy
)
from PyQt6.QtGui import QPainter, QColor, QPen
from PyQt6.QtCore import Qt, QPointF, QRectF, QTimer

from ui.widgets.base_widget import BaseWidget
from ui.widgets.status_indicator_box import StatusIndicatorBox






# TODO: 이 뷰의 뷰모델의 __int__ 메서드에 아래 내용 추가해야 한다
#   현재 진행중인 시퀀스 구독(connect)해서 UI 갱신하게 만들어야 된다










# ==========================================================
# 1. 로봇 시각화(애니메이션) 위젯 (내부용)
# ==========================================================
class _RobotVisualizer(QWidget):
    """QPainter로 로봇 팔, 작업 영역, 로봇 위치(점)를 그리는 위젯"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(250, 200)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # '목표 위치'를 %로 저장 (x, y)
        self._target_x_percent = 0.5  # 0.0=왼쪽, 1.0=오른쪽
        self._target_y_percent = 0.5  # 0.0=위,   1.0=아래
    

    def set_data(self, x_percent: float, y_percent: float):
        """
        외부에서 로봇 위치(X, Y)를 0.0~1.0 비율로 받아 갱신
        """
        self._target_x_percent = max(0.0, min(1.0, x_percent))
        self._target_y_percent = max(0.0, min(1.0, y_percent))
        self.update() # -> paintEvent() 호출


    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#333"), 10, cap=Qt.PenCapStyle.RoundCap, join=Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(QColor("#555"))

        # 1. 작업 영역(파란 상자)과 목표점(빨간 점)을 먼저 그림
        #    그리고 목표점의 '절대 좌표'를 반환받음
        target_pos = self._draw_work_area_and_dot(painter)

        # 2. 로봇 팔을 그림 (IK 계산)
        self._draw_robot_arm(painter, target_pos)


    def _get_work_area_rect(self) -> QRectF:
        """파란색 작업 영역(Work Area)이 그려질 QRectF를 계산"""
        w = self.width()
        h = self.height()
        work_area_width = w * 0.45
        work_area_height = h * 0.7
        top = (h - work_area_height) / 2
        left = w * 0.52
        return QRectF(left, top, work_area_width, work_area_height)


    def _draw_work_area_and_dot(self, painter: QPainter) -> QPointF:
        """파란색 작업 영역과 그 안의 빨간 점을 그리고, 점의 좌표를 반환"""
        
        # 1. 작업 영역 좌표 계산
        work_area = self._get_work_area_rect()
        
        # 2. 파란색 작업 영역 그리기
        painter.save() # (상태 저장 1)
        painter.setPen(QPen(QColor("#00AEEF"), 3))
        painter.setBrush(QColor("#EAF8FF"))
        painter.drawRoundedRect(work_area, 15.0, 15.0)

        inner_radius = min(work_area.width(), work_area.height()) * 0.4
        painter.setPen(QPen(QColor("#007BFF"), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(work_area.center(), inner_radius, inner_radius)
        painter.restore() # (상태 복원 1)

        # 3. 빨간 점 좌표 계산 (데이터 값 -> 실제 픽셀 좌표)
        dot_x = work_area.left() + (work_area.width() * self._target_x_percent)
        dot_y = work_area.top() + (work_area.height() * self._target_y_percent)
        target_pos = QPointF(dot_x, dot_y)
        
        # 4. 빨간 점 그리기
        painter.save() # (상태 저장 2)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("red"))
        painter.drawEllipse(target_pos, 4, 4)
        painter.restore() # (상태 복원 2)
        
        # 5. 계산된 빨간 점의 절대 좌표를 반환
        return target_pos

    def _draw_robot_arm(self, painter: QPainter, target_pos: QPointF):
        """
        로봇 베이스에서 target_pos(빨간 점)까지 2관절 팔을 역기구학으로 계산하여 그림
        """
        
        # --- 1. 고정값 정의 ---
        # 로봇 베이스(어깨)의 고정 위치
        base_pos = QPointF(self.width() * 0.25, self.height() * 0.8)
        # 로봇 팔의 고정 길이 (위젯 높이에 비례)
        arm1_len = self.height() * 0.4 
        arm2_len = self.height() * 0.4

        # --- 2. 역기구학 (IK) 계산 ---
        # 베이스에서 목표점까지의 전체 거리(D) 계산
        dx = target_pos.x() - base_pos.x()
        dy = target_pos.y() - base_pos.y()
        dist_sq = dx*dx + dy*dy
        dist = math.sqrt(dist_sq)

        # 팔꿈치 좌표 (elbow_pos)
        elbow_pos: QPointF

        max_reach = arm1_len + arm2_len
        if dist >= max_reach:
            # 팔이 닿지 않는 경우: 팔을 쭉 뻗음
            # (목표 방향으로 arm1_len 만큼 떨어진 곳이 팔꿈치)
            angle_rad = math.atan2(dy, dx)
            elbow_pos = QPointF(
                base_pos.x() + arm1_len * math.cos(angle_rad),
                base_pos.y() + arm1_len * math.sin(angle_rad)
            )
        else:
            # 팔이 닿는 경우: 역기구학(Law of Cosines)으로 팔꿈치 위치 계산
            # (설명: https://en.wikipedia.org/wiki/Inverse_kinematics#Two-link_robot_arm)
            
            # 각도 1 (어깨-팔꿈치-손목)
            angle1_rad = math.acos((dist_sq + arm1_len**2 - arm2_len**2) / (2 * dist * arm1_len))
            # 각도 2 (베이스-목표-어깨)
            angle2_rad = math.atan2(dy, dx)
            
            # 팔꿈치 각도 (항상 "elbow up" 자세를 취하도록 - 각도를 뺌)
            elbow_angle_rad = angle2_rad - angle1_rad 
            
            # 팔꿈치 좌표 계산
            elbow_pos = QPointF(
                base_pos.x() + arm1_len * math.cos(elbow_angle_rad),
                base_pos.y() + arm1_len * math.sin(elbow_angle_rad)
            )

        # --- 3. 계산된 좌표로 로봇 팔 그리기 ---
        painter.save()
        
        # 3-1. 로봇 베이스 그리기 (고정된 회색 사각형)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#666")) # 진회색
        painter.drawRoundedRect(QRectF(base_pos.x() - 15, base_pos.y() - 10, 30, 20), 5, 5)

        # 3-2. 로봇 팔 그리기 (계산된 2개의 선)
        pen = QPen(QColor("#333"), 10, cap=Qt.PenCapStyle.RoundCap, join=Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        
        # Arm 1 (베이스 -> 팔꿈치)
        painter.drawLine(base_pos, elbow_pos)
        # Arm 2 (팔꿈치 -> 목표점)
        painter.drawLine(elbow_pos, target_pos) 
        
        # 3-3. 관절 그리기 (하얀색 원)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("white"))
        painter.drawEllipse(base_pos, 5, 5)   # 어깨 관절
        painter.drawEllipse(elbow_pos, 5, 5)  # 팔꿈치 관절
        
        painter.restore()


# ==========================================================
# 2. 메인 로봇 위치 위젯 (조립)
# ==========================================================
class RobotPositionWidget(BaseWidget):
    """
    로봇 위치 메인 위젯
    - BaseWidget을 상속받아 update_data 인터페이스 구현
    - 시각화(_RobotVisualizer), 텍스트(QLabel), 상태창(StatusIndicatorBox) 조립
    """

    def _init_ui(self):
        """BaseWidget의 _init_ui를 재정의하여 UI를 구성"""
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # 1. 로봇 시각화 (수정된 _RobotVisualizer 사용)
        self.visualizer = _RobotVisualizer()
        layout.addWidget(self.visualizer, stretch=1) 

        # 2. 디지털 좌표 표시
        self.digital_readout = QLabel("height: 0.0 || x: 0.0")
        self.digital_readout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.digital_readout.setStyleSheet("font-size: 16px; margin-top: 5px;")
        layout.addWidget(self.digital_readout, stretch=0)

        # 3. 상태 표시줄 (StatusIndicatorBox 위젯 사용)
        self.state_indicator = StatusIndicatorBox("Robot State", led_size=10)
        layout.addWidget(self.state_indicator, stretch=0)

    def update_data(self, data: dict):
        """
        BaseWidget의 추상 메서드(update_data) 구현
        
        Args:
            data (dict): {'x': float, 'height': float (Y좌표), 'state': str}
                         (x, height는 0.0~1.0 사이의 %값이라고 가정)
        """
        # (이 함수는 변경 사항 없음)
        # 데이터 추출 (x, height는 0.0~1.0 사이의 %값이라고 가정)
        x_pos = data.get('x', 0.5)
        height_pos = data.get('height', 0.5)
        state = data.get('state', 'waiting')

        # 1. 시각화 위젯 갱신
        self.visualizer.set_data(x_pos, height_pos)

        # 2. 디지털 텍스트 갱신 (소수점 2자리까지)
        self.digital_readout.setText(f"height: {height_pos:.2f} || x: {x_pos:.2f}")

        # 3. 상태 표시줄 갱신
        state_data = {
            'state': state,
            'title': self.state_indicator._title_text # 기존 제목 유지
        }
        self.state_indicator.safe_update_data(state_data)

    def clear_widget(self):
        """위젯을 초기 상태(중심, off)로 리셋"""
        self.update_data({
            'x': 0.5,
            'height': 0.5,
            'state': 'off'
        })
        super().clear_widget()







# ==========================================================
# 3. 단독 실행 (테스트용)
"""
python -m ui.widgets.robot_position_widget
"""
# ==========================================================
if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    main_window = QWidget()
    main_layout = QVBoxLayout(main_window)
    
    test_widget = RobotPositionWidget()
    main_layout.addWidget(test_widget)
    main_window.setWindowTitle("RobotPositionWidget 단독 테스트 (IK)")
    main_window.resize(300, 350)
    main_window.show()

    # --- ⬇️ 테스트 애니메이션 로직 ⬇️ ---

    # 테스트용 데이터
    test_data = {
        'x': 0.5,       # 0.0~1.0 비율
        'height': 0.5,  # 0.0~1.0 비율
        'state': 'running'
    }
    
    # 원형 애니메이션을 위한 각도
    anim_angle = 0
    
    # (추가) 나선형 애니메이션을 위한 반지름 및 방향
    anim_radius = 0.0 # 0.0 (중심) ~ 0.5 (테두리)
    radius_direction = 1  # 1: 밖으로, -1: 안으로

    def update_test():
        global anim_angle, anim_radius, radius_direction
        
        # 1. 각도 업데이트 (계속 회전)
        anim_angle = (anim_angle + 5) % 360 # (속도를 조금 높임)
        
        # 2. 반지름 업데이트 (안팎으로 왕복)
        if anim_radius >= 0.5: # 최대 반지름(테두리)에 도달하면
            radius_direction = -1 # 안쪽으로 방향 전환
        elif anim_radius <= 0.0: # 최소 반지름(중심)에 도달하면
            radius_direction = 1  # 바깥쪽으로 방향 전환
            
        anim_radius += (0.005 * radius_direction) # 0.5%씩 증감
        
        # 3. X, Y 좌표를 나선형으로 계산
        #    (cos/sin 결과(-1~1) * 반지름) + 중심(0.5)
        center_x = 0.5
        center_y = 0.5
        test_data['x'] = center_x + anim_radius * math.cos(math.radians(anim_angle))
        test_data['height'] = center_y + anim_radius * math.sin(math.radians(anim_angle))
        
        # 4. 상태 변경 (기존과 동일)
        if int(anim_angle) % 90 < 10:
             test_data['state'] = 'waiting'
        elif int(anim_angle) % 45 < 10:
             test_data['state'] = 'running'

        # 5. 위젯에 최종 데이터 전달
        test_widget.safe_update_data(test_data)

    timer = QTimer()
    timer.timeout.connect(update_test)
    timer.start(50) # 50ms

    sys.exit(app.exec())