# view_models/turntable_gauge_viewmodel.py
import math
from PyQt6.QtCore import QObject, pyqtSignal
from typing import Dict, Any

from models.fanuc_pose_model import FANUCPose
from models.fanuc_pose_key import FANUCPoseKey
from models.servo_pose_model import ServoPose
from models.servo_pose_key import ServoAxis, ServoPoseKey
from core.event_bus import EVENT_BUS

class TurntableGaugeViewModel(QObject):
    """
    TurntableGauge 위젯을 위한 뷰모델
    
    역할:
    1. Model (FANUCPose, ServoPose) 데이터를 수신
    2. View (TurntableGauge)가 그리기 쉬운 형태(Angle, Percentage 등)로 가공 (Business Logic)
    3. Primitive Type으로 View에 전달 (Strict Decoupling)
    """

    # 로컬 시그널 - View 가 구독
    ui_data_updated = pyqtSignal(dict)                      # UI 데이터
    waypoints_changed = pyqtSignal(list)                    # 시퀀스 데이터 전체
    progressing_step_changed = pyqtSignal(int, int, str)    # 현재 진행중인 시퀀스 스탭


    def __init__(self):
        super().__init__()
        
        # 상태 저장소
        # 1. Robot Pose (FANUCPose)
        self.robot_pose: FANUCPose = FANUCPose()

        # 2. Servo Motion (Dict[ServoAxis, ServoPose])
        self.servo_motions: Dict[ServoAxis, ServoPose] = {
            ServoAxis.TOOL_REVOLUTION: ServoPose(0.0, 0.0),
            ServoAxis.TOOL_ROTATION:   ServoPose(0.0, 0.0),
            ServoAxis.TURNTABLE:       ServoPose(0.0, 0.0)
        }

        
        self._rounds: int = 0
        self._state: str = "waiting"

        self._max_reach_mm: float = 200.0  # 로봇 팔 길이 (반지름 정규화용)

        # EventBus 연결
        self._bind_signals()

    def _bind_signals(self):
        EVENT_BUS.control.robot_current_pose.connect(self.on_update_current_robot_pose)
        EVENT_BUS.control.servo_current_motion.connect(self.on_update_current_servo_motion)
        EVENT_BUS.data.sequence_data_loaded.connect(self.on_sequence_data_loaded)
        EVENT_BUS.data.progress_updated.connect(self._on_progress_updated)          # 현재 실행 중인 시퀀스 단계와 상태



    # ===============================================
    # 시그널 슬롯 [물리적 시그널 처리]
    # ===============================================
    def on_update_current_robot_pose(self, pose: FANUCPose):
        """현재 로봇 위치 업데이트"""
        self._handle_robot_servo_data({'pose': pose})

    def on_update_current_servo_motion(self, servo_states: Dict[ServoAxis, ServoPose]):
        """현재 서보 모터 상태 업데이트"""
        # _handle_robot_servo_data가 'servo_axes' 키로 dict를 받도록 설계됨
        self._handle_robot_servo_data({'servo_axes': servo_states})

    def on_sequence_data_loaded(self, sequence_data: list):
        """시퀀스 데이터 읽기 완료"""
        self._handle_trajectory(sequence_data)

    def _on_progress_updated(self, current: int, total: int, status: str):
        """현재 진행중인 시퀀스 단계 업데이트"""
        self.progressing_step_changed.emit(current, total, status)


    # ===============================================
    # 핸들러 [논리적 흐름 담당]
    # ===============================================
    def _handle_robot_servo_data(self, data: Dict[str, Any]):
        """
        외부(Service/Controller)에서 모델 데이터를 받아 상태를 갱신하고 View에 알림
        """
        
        changed = False

        # 1. 서보 모터 데이터 처리 (Axis 1, 2, 3)
        # ---------------------------------------------------------------------
        # (A) 전체 서보 데이터 (Dict[ServoAxis, ServoPose])
        servo_axes = data.get('servo_axes')
        if isinstance(servo_axes, dict):
            # 통째로 업데이트하거나, 개별 업데이트
            # 여기서는 내부 딕셔너리를 갱신
            for axis, pose in servo_axes.items():
                if axis in self.servo_motions and isinstance(pose, ServoPose):
                    # 값 비교
                    current = self.servo_motions[axis]
                    if current.angle != pose.angle or current.velocity != pose.velocity:
                        self.servo_motions[axis] = pose
                        changed = True

        # (B) 개별 ServoPose (Legacy or single push) - 기본 Turntable로 간주
        servo_pose = data.get('servo_pose', data.get('turntable_pose'))
        if isinstance(servo_pose, ServoPose):
            current = self.servo_motions[ServoAxis.TURNTABLE]
            if current.angle != servo_pose.angle or current.velocity != servo_pose.velocity:
                self.servo_motions[ServoAxis.TURNTABLE] = servo_pose
                changed = True
        
        # (C) Primitive Fallback (Legacy)
        if 'angle' in data: 
            new_angle = float(data['angle'])
            current = self.servo_motions[ServoAxis.TURNTABLE]
            if current.angle != new_angle:
                self.servo_motions[ServoAxis.TURNTABLE] = ServoPose(new_angle, current.velocity)
                changed = True

        # 2. 로봇 위치 처리 (FANUCPose)
        # ---------------------------------------------------------------------
        robot_pose = data.get('pose')
        if isinstance(robot_pose, FANUCPose):
            # dataclass 비교는 모든 필드 검사
            if self.robot_pose != robot_pose:
                self.robot_pose = robot_pose
                changed = True
        else: # Fallback (Keys)
            # 수동 업데이트 (문자열 키 지원)
            # (FANUCPose는 frozen이 아니라고 가정하고 필드 업데이트, 혹은 새로 생성)
            # 여기서는 간단히 필드 확인. FANUCPose는 dataclass.
            # 변경 여부 확인이 복잡하므로, 값이 들어오면 무조건 업데이트 시도
            
            x_val = data.get(FANUCPoseKey.X.model_key)
            y_val = data.get(FANUCPoseKey.Y.model_key)
            
            if x_val is not None:
                self.robot_pose.x = float(x_val) # type: ignore
                changed = True
            if y_val is not None:
                self.robot_pose.y = float(y_val) # type: ignore
                changed = True

            # TODO: 필요에 따라 다른 키들도 처리 가능하면 추가


        # 3. 기타 상태 처리
        # ---------------------------------------------------------------------
        if 'rounds' in data:
            self._rounds = int(data['rounds'])
            changed = True
            
        if 'state' in data:
            self._state = str(data['state'])
            changed = True

        if changed:
            self._notify_view()
            
    def _notify_view(self):
        """가공된 데이터를 View로 전송"""
        
        # [Business Logic] Cartesian(X,Y) -> Polar(Angle, Radius) 변환
        # ---------------------------------------------------------
        # X축(12시) 기준, Y축(9시/270도) 가정을 적용
        # atan2(y, x) -> 수학적 각도 (X축 기준 반시계)
        
        robot_x = self.robot_pose.x
        robot_y = self.robot_pose.y

        math_angle_rad = math.atan2(robot_y, robot_x)
        math_angle_deg = math.degrees(math_angle_rad)
        
        # 변환 공식: -math_angle (12시=0, 시계방향)
        robot_display_angle = (-math_angle_deg) % 360
        
        # 거리 정규화
        dist = math.sqrt(robot_x**2 + robot_y**2)
        radius_percent = min(dist / self._max_reach_mm, 1.0)
        
        # View용 데이터 패킷 생성 (Primitive Types Only)
        view_data = {
            'angle': self.servo_motions[ServoAxis.TURNTABLE].angle,
            
            # Material Cut Trajectory (실제 가공 궤적) 시각화
            # 회전하는 턴테이블 위에서의 상대적 위치
            # 현재 시점(실시간)에서는 로봇의 World 위치가 곧 가공 위치임 (상대성 계산은 Waypoint에서 중요)
            'material_cut_angle': robot_display_angle,       # Material Cut Angle
            'material_cut_radius_ratio': radius_percent,     # Material Cut Radius Ratio
            
            # 추가 정보 (View가 원하면 표시 가능)
            'robot_z': self.robot_pose.z,
            'robot_f': self.robot_pose.f,
            'servo_rev_vel': self.servo_motions[ServoAxis.TOOL_REVOLUTION].velocity,
            'servo_rot_vel': self.servo_motions[ServoAxis.TOOL_ROTATION].velocity,
            'servo_turntable_vel': self.servo_motions[ServoAxis.TURNTABLE].velocity,

            'rounds': self._rounds,
            'state': self._state
        }
        
        self.ui_data_updated.emit(view_data)

    def _handle_trajectory(self, sequence_data: list):
        """웨이포인트들을 시각화용 데이터로 변환하여 로컬 시그널로 emit"""
        visual_waypoints = []
        
        for step in sequence_data:
            # X, Y 좌표 추출 (키 이름은 데이터 소스에 따라 다를 수 있음, 여기서는 소문자 'x', 'y' 가정)
            # 만약 모델 키(FANUCPoseKey)를 쓴다면 step[FANUCPoseKey.X.value] 등일 수 있음
            # SequenceWorker -> FanucPose.from_dict -> to_dict() 거쳤다면 키는 'x','y'...
            
            # 안전하게 가져오기 (문자열일 수 있으므로 float 변환)
            try:
                x = float(step.get('x', 0.0))
                y = float(step.get('y', 0.0))
                
                # Cartesian -> Polar 변환 (Visual Angle)
                math_angle_rad = math.atan2(y, x)
                math_angle_deg = math.degrees(math_angle_rad)
                visual_angle = (-math_angle_deg) % 360
                
                # Distance Percent
                dist = math.sqrt(x**2 + y**2)
                dist_percent = min(dist / self._max_reach_mm, 1.0)
                
                # Material Cut Path 계산 (Material Frame)
                # 가공 궤적 = World Angle - Turntable Angle
                # (턴테이블이 회전해도 궤적이 재료에 고정되어 같이 회전하도록 함)
                step_turntable_deg = float(step.get('turntable_deg', 0.0))
                material_cut_angle = (visual_angle - step_turntable_deg) % 360

                visual_waypoints.append({
                    'material_cut_angle': material_cut_angle,
                    'material_cut_radius_ratio': dist_percent
                })
                
            except (ValueError, TypeError):
                continue
                
        self.waypoints_changed.emit(visual_waypoints)

    def _handle_processing_step(self, current: int, total: int, status: str):
        """진행중인 궤적 표시"""
        self.progressing_step_changed.emit()