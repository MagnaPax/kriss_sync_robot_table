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
        self._robot_x: float = 0.0
        self._robot_y: float = 0.0
        self._robot_z: float = 0.0
        self._robot_f: float = 0.0 # Feed Rate
        
        self._servo_revolution: float = 0.0 # Axis 1
        self._servo_rotation: float = 0.0   # Axis 2
        self._servo_turntable_degree: float = 0.0   # Axis 3 (Degree)
        self._servo_turntable_velocity: float = 0.0 # Axis 3 (Velocity)

        
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

        # 1. 서보 모터 데이터 처리 (Axis 1, 2, 3)
        # ---------------------------------------------------------------------
        # (A) 개별 ServoPose 객체 (단일 축 - 주로 턴테이블)
        servo_pose = data.get('servo_pose', data.get('turntable_pose'))
        if isinstance(servo_pose, ServoPose):
            # 기본적으로 단일 객체 전달 시 턴테이블(Axis 3)로 가정
            new_angle = float(servo_pose.angle)
            if self._servo_turntable_degree != new_angle:
                self._servo_turntable_degree = new_angle
                changed = True

        # (B) 전체 서보 데이터 (Dict[int, ServoPose] or List)
        # 예: {'servo_axes': {1: Pose(...), 2: Pose(...), 3: Pose(...)}}
        servo_axes = data.get('servo_axes')
        if isinstance(servo_axes, dict):
            # Axis 1: Tool Revolution
            if 1 in servo_axes and isinstance(servo_axes[1], ServoPose):
                rev = float(servo_axes[1].velocity) # 보통 속도 제어
                if self._servo_revolution != rev:
                    self._servo_revolution = rev
                    changed = True
            
            # Axis 2: Tool Rotation
            if 2 in servo_axes and isinstance(servo_axes[2], ServoPose):
                rot = float(servo_axes[2].velocity) # 보통 속도 제어
                if self._servo_rotation != rot:
                    self._servo_rotation = rot
                    changed = True
            
            # Axis 3: Turntable
            if 3 in servo_axes and isinstance(servo_axes[3], ServoPose):
                angle = float(servo_axes[3].angle)
                vel = float(servo_axes[3].velocity)
                
                if self._servo_turntable_degree != angle:
                    self._servo_turntable_degree = angle
                    changed = True
                
                if self._servo_turntable_velocity != vel:
                    self._servo_turntable_velocity = vel
                    changed = True
        
        # (C) Fallback (Legacy)
        elif 'angle' in data: 
            new_angle = float(data['angle'])
            if self._servo_turntable_degree != new_angle:
                self._servo_turntable_degree = new_angle
                changed = True
                
        # 2. 로봇 위치 처리 (FANUCPose -> X, Y)
        # ---------------------------------------------------------------------
        robot_pose = data.get('pose')
        if isinstance(robot_pose, FANUCPose):
            if (self._robot_x != robot_pose.x or 
                self._robot_y != robot_pose.y or
                self._robot_z != robot_pose.z or
                self._robot_f != robot_pose.f):
                
                self._robot_x = robot_pose.x
                self._robot_y = robot_pose.y
                self._robot_z = robot_pose.z
                self._robot_f = robot_pose.f
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
            'angle': self._servo_turntable_degree,
            'robot_angle': robot_display_angle,
            'robot_radius_percent': radius_percent,
            
            # 추가 정보 (View가 원하면 표시 가능)
            'robot_z': self._robot_z,
            'robot_f': self._robot_f,
            'servo_rev_vel': self._servo_revolution,
            'servo_rot_vel': self._servo_rotation,
            'servo_turntable_vel': self._servo_turntable_velocity,

            
            'rounds': self._rounds,
            'state': self._state
        }
        
        self.ui_data_updated.emit(view_data)
