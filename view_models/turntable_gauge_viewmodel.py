# view_models/turntable_gauge_viewmodel.py
import math
from PyQt6.QtCore import QObject, pyqtSignal
from typing import Dict, Any, Optional

from models.fanuc_pose_model import FANUCPose
from models.fanuc_pose_key import FANUCPoseKey
from models.servo_pose_model import ServoPose
from models.servo_pose_key import ServoAxis, ServoPoseKey

class TurntableGaugeViewModel(QObject):
    """
    TurntableGauge 위젯을 위한 뷰모델
    
    역할:
    1. Model (FANUCPose, ServoPose) 데이터를 수신
    2. View (TurntableGauge)가 그리기 쉬운 형태(Angle, Percentage 등)로 가공 (Business Logic)
    3. Primitive Type으로 View에 전달 (Strict Decoupling)
    """

    # View 업데이트용 시그널 (dict: {'angle': float, 'robot_angle': float, ...})
    ui_data_updated = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        
        # 상태 저장소
        self._current_angle: float = 0.0
        self._robot_x: float = 0.0
        self._robot_y: float = 0.0
        self._rounds: int = 0
        self._state: str = "waiting"

        self._max_reach_mm: float = 2000.0  # 로봇 팔 길이 (반지름 정규화용)

    def update_model_data(self, data: Dict[str, Any]):
        """
        외부(Service/Controller)에서 모델 데이터를 받아 상태를 갱신하고 View에 알림
        
        Args:
            data (dict): Mixed data containing keys like 'pose', 'servo_pose', etc.
        """
        
        changed = False

        # 1. 턴테이블 각도 처리 (ServoPose -> Angle)
        # ---------------------------------------------------------------------
        servo_pose = data.get('servo_pose', data.get('turntable_pose'))
        if isinstance(servo_pose, ServoPose):
            new_angle = float(servo_pose.angle)
            if self._current_angle != new_angle:
                self._current_angle = new_angle
                changed = True
        elif 'angle' in data: # Fallback
            new_angle = float(data['angle'])
            if self._current_angle != new_angle:
                self._current_angle = new_angle
                changed = True
                
        # 2. 로봇 위치 처리 (FANUCPose -> X, Y)
        # ---------------------------------------------------------------------
        robot_pose = data.get('pose')
        if isinstance(robot_pose, FANUCPose):
            if self._robot_x != robot_pose.x or self._robot_y != robot_pose.y:
                self._robot_x = robot_pose.x
                self._robot_y = robot_pose.y
                changed = True
        else: # Fallback (Keys)
            x_key = FANUCPoseKey.X.model_key
            y_key = FANUCPoseKey.Y.model_key
            
            # get(key, default) -> default가 아니라 기존값 유지? 아니면 0.0?
            # 여기서는 데이터가 있을 때만 갱신
            if x_key in data:
                self._robot_x = float(data[x_key])
                changed = True
            if y_key in data:
                self._robot_y = float(data[y_key])
                changed = True

        # 3. 기타 상태 처리
        # ---------------------------------------------------------------------
        if 'rounds' in data:
            self._rounds = int(data['rounds'])
            changed = True
            
        if 'state' in data:
            self._state = str(data['state'])
            changed = True

        # 변경사항이 있으면 View에 통지
        # (최적화를 위해 매번 보내지 않고 변경시에만 보낼 수도 있음, 여기서는 단순화)
        if changed:
            self._notify_view()
            
    def _notify_view(self):
        """가공된 데이터를 View로 전송"""
        
        # [Business Logic] Cartesian(X,Y) -> Polar(Angle, Radius) 변환
        # ---------------------------------------------------------
        # X축(12시) 기준, Y축(9시/270도) 가정을 적용
        # atan2(y, x) -> 수학적 각도 (X축 기준 반시계)
        
        math_angle_rad = math.atan2(self._robot_y, self._robot_x)
        math_angle_deg = math.degrees(math_angle_rad)
        
        # 변환 공식: -math_angle (12시=0, 시계방향)
        robot_display_angle = (-math_angle_deg) % 360
        
        # 거리 정규화
        dist = math.sqrt(self._robot_x**2 + self._robot_y**2)
        radius_percent = min(dist / self._max_reach_mm, 1.0)
        
        # View용 데이터 패킷 생성 (Primitive Types Only)
        view_data = {
            'angle': self._current_angle,
            'robot_angle': robot_display_angle,
            'robot_radius_percent': radius_percent,
            'rounds': self._rounds,
            'state': self._state
        }
        
        self.ui_data_updated.emit(view_data)