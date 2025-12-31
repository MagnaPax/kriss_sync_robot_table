# view_models/user_coordinates_viewmodel.py
from typing import TYPE_CHECKING, Dict
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from core.event_bus import EVENT_BUS
from models.fanuc_pose_model import FANUCPose
from models.servo_pose_model import ServoPose
from models.servo_pose_key import ServoAxis

if TYPE_CHECKING:
    from services.plc_service import PLCService




class UserCoordinatesViewModel(QObject):
    
    # 로컬 시그널
    user_robot_pose_changed = pyqtSignal(FANUCPose)      # 로봇의 현재 위치
    user_tool_revolution_changed = pyqtSignal(ServoPose) # 툴의 회전 상태
    user_tool_rotation_changed = pyqtSignal(ServoPose)   # 툴의 자전 상태
    user_turntable_pose_changed = pyqtSignal(ServoPose)  # 턴테이블의 현재 상태


    def __init__(self, plc_service: "PLCService"):
        super().__init__()
        self._log_prefix = f"[{self.__class__.__name__}]"
        self._plc_service = plc_service

        # [1] 값 저장 변수 생성 (Raw: 실제 위치, Offset: 사용자가 잡은 0점)
        self._raw_robot_pose = FANUCPose()
        self._robot_offset = FANUCPose()

        self._raw_servo_states: Dict[ServoAxis, ServoPose] = {}
        self._servo_offsets: Dict[ServoAxis, ServoPose] = {
            axis: ServoPose(0.0, 0.0) for axis in ServoAxis
        }

        # [2] EVENT_BUS 시그널 연결
        EVENT_BUS.control.robot_current_pose.connect(self._on_robot_pose_received)
        EVENT_BUS.control.servo_current_motion.connect(self._on_servo_data_received)


    # [3] 데이터 저장 및 상대 좌표 계산 로직
    @pyqtSlot(object)
    def _on_robot_pose_received(self, pose: FANUCPose):
        """실제 로봇 좌표를 받아서 오프셋을 뺀 '사용자 좌표'를 계산하여 방송"""
        self._raw_robot_pose = pose
        
        # 상대 좌표 계산 (Raw - Offset)
        user_pose = FANUCPose(
            x=pose.x - self._robot_offset.x,
            y=pose.y - self._robot_offset.y,
            z=pose.z - self._robot_offset.z,
            w=pose.w - self._robot_offset.w,
            p=pose.p - self._robot_offset.p,
            r=pose.r - self._robot_offset.r
        )
        self.user_robot_pose_changed.emit(user_pose)

    @pyqtSlot(dict)
    def _on_servo_data_received(self, servo_states: Dict[ServoAxis, ServoPose]):
        """실제 서보 상태를 받아서 오프셋을 뺀 '사용자 좌표'를 계산하여 방송"""
        self._raw_servo_states = servo_states

        # 각 축별로 오프셋 적용하여 재방송
        if ServoAxis.TOOL_REVOLUTION in servo_states:
            raw = servo_states[ServoAxis.TOOL_REVOLUTION]
            off = self._servo_offsets[ServoAxis.TOOL_REVOLUTION]
            self.user_tool_revolution_changed.emit(ServoPose(raw.angle - off.angle, raw.velocity - off.velocity))

        if ServoAxis.TOOL_ROTATION in servo_states:
            raw = servo_states[ServoAxis.TOOL_ROTATION]
            off = self._servo_offsets[ServoAxis.TOOL_ROTATION]
            self.user_tool_rotation_changed.emit(ServoPose(raw.angle - off.angle, raw.velocity - off.velocity))

        if ServoAxis.TURNTABLE in servo_states:
            raw = servo_states[ServoAxis.TURNTABLE]
            off = self._servo_offsets[ServoAxis.TURNTABLE]
            self.user_turntable_pose_changed.emit(ServoPose(raw.angle - off.angle, raw.velocity - off.velocity))


    # ================================
    # [3.1 ~ 3.3] 원점 설정 (Origin) 로직
    # ================================
    def origin_robot_pose(self):
        """현재 로봇 위치를 0으로 설정 (오프셋 업데이트)"""
        self._robot_offset = self._raw_robot_pose
        EVENT_BUS.log.message.emit(f"{self._log_prefix} 로봇 사용자 좌표계 원점 설정 완료", "INFO")

    def origin_servo_pose(self):
        """현재 턴테이블(Axis 3) 위치를 0으로 설정"""
        if ServoAxis.TURNTABLE in self._raw_servo_states:
            self._servo_offsets[ServoAxis.TURNTABLE] = self._raw_servo_states[ServoAxis.TURNTABLE]
            EVENT_BUS.log.message.emit(f"{self._log_prefix} 턴테이블 사용자 좌표계 원점 설정 완료", "INFO")

    def origin_all_pose(self):
        """모든 좌표(로봇 + 모든 서보)를 0으로 설정"""
        # 로봇 초기화
        self.origin_robot_pose()
        
        # 모든 서보 초기화
        for axis in ServoAxis:
            if axis in self._raw_servo_states:
                self._servo_offsets[axis] = self._raw_servo_states[axis]
        
        EVENT_BUS.log.message.emit(f"{self._log_prefix} 모든 장치 사용자 좌표계 원점 설정 완료", "INFO")
