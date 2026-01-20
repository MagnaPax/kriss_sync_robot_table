# view_models/user_coordinates_viewmodel.py
from typing import TYPE_CHECKING, Dict
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from core.event_bus import EVENT_BUS
from models.fanuc_pose_model import FANUCPose
from models.servo_pose_model import ServoPose
from models.servo_pose_key import ServoAxis
from config.data_formats import SERVO_SCHEMA, KEY_TOOL_REV_RPM, KEY_TOOL_ROT_RPM

if TYPE_CHECKING:
    from services.plc_service import PLCService




class UserCoordinatesViewModel(QObject):
    
    # 로컬 시그널
    user_robot_pose_changed = pyqtSignal(FANUCPose)         # 로봇의 위치       - 사용자 좌표계
    user_tool_revolution_changed = pyqtSignal(ServoPose)    # 툴의 회전 상태    - 사용자 좌표계
    user_tool_rotation_changed = pyqtSignal(ServoPose)      # 툴의 자전 상태    - 사용자 좌표계
    user_turntable_pose_changed = pyqtSignal(ServoPose)     # 턴테이블의 상태   - 사용자 좌표계
    origin_buttons_disabled = pyqtSignal(str, bool)         # 위젯 활성화/비활성화



    def __init__(self, plc_service: "PLCService"):
        super().__init__()
        self._log_prefix = f"[{self.__class__.__name__}]"
        self._plc_service = plc_service

        # 값 저장 변수 생성 (Raw: 실제 위치, Offset: 사용자가 잡은 0점)
        self._raw_robot_pose = FANUCPose()
        self._robot_offset = FANUCPose()

        self._raw_servo_states: Dict[ServoAxis, ServoPose] = {}
        self._servo_offsets: Dict[ServoAxis, ServoPose] = {
            axis: ServoPose(0.0, 0.0) for axis in ServoAxis
        }

        # EVENT_BUS 시그널 연결
        self._bind_signals()


    def _bind_signals(self):
        EVENT_BUS.control.robot_current_pose.connect(self._on_robot_pose_received)
        EVENT_BUS.control.servo_current_motion.connect(self._on_servo_data_received)
        # '시퀀스 실행중' 방송 청취 -> 내 로컬 시그널로 바로 재방송
        EVENT_BUS.data.sequence_in_progress.connect(self.origin_buttons_disabled.emit)



    # ===============================================
    # 시그널 슬롯 [물리적 시그널 수신]
    # ===============================================
    @pyqtSlot(object)
    def _on_robot_pose_received(self, pose: FANUCPose):
        self._handle_make_robot_user_coordinates(pose)

    @pyqtSlot(dict)
    def _on_servo_data_received(self, servo_states: Dict[ServoAxis, ServoPose]):
        self._handle_make_servo_user_coordinates(servo_states)


    # ===============================================
    # 핸들러 [논리적 흐름 담당]
    # ===============================================
    def _handle_make_robot_user_coordinates(self, pose: FANUCPose):
        """실제 로봇 좌표를 받아서 오프셋을 뺀 '사용자 좌표'를 계산하여 방송"""
        self._raw_robot_pose = pose
        
        # 사용자 좌표 계산 (현재 World 좌표 - 기준점)
        user_pose = FANUCPose(
            x=pose.x - self._robot_offset.x,
            y=pose.y - self._robot_offset.y,
            z=pose.z - self._robot_offset.z,
            w=pose.w - self._robot_offset.w,
            p=pose.p - self._robot_offset.p,
            r=pose.r - self._robot_offset.r
        )
        self.user_robot_pose_changed.emit(user_pose)

    def _handle_make_servo_user_coordinates(self, servo_states: Dict[ServoAxis, ServoPose]):
        """실제 서보 상태를 받아서 오프셋을 뺀 '사용자 좌표'를 계산하여 방송"""
        self._raw_servo_states = servo_states

        # 각 축별로 오프셋 적용하여 재방송
        if ServoAxis.TOOL_REVOLUTION in servo_states:
            raw = servo_states[ServoAxis.TOOL_REVOLUTION]
            off = self._servo_offsets[ServoAxis.TOOL_REVOLUTION]
            # [스케일링 복원] (Raw - Offset) 후 deg/s -> RPM 변환
            scale = SERVO_SCHEMA[KEY_TOOL_REV_RPM].get('scale_factor', 6.0)
            user_vel = (raw.velocity - off.velocity) / scale
            self.user_tool_revolution_changed.emit(ServoPose(raw.angle - off.angle, user_vel))

        if ServoAxis.TOOL_ROTATION in servo_states:
            raw = servo_states[ServoAxis.TOOL_ROTATION]
            off = self._servo_offsets[ServoAxis.TOOL_ROTATION]
            # [스케일링 복원] (Raw - Offset) 후 deg/s -> RPM 변환
            scale = SERVO_SCHEMA[KEY_TOOL_ROT_RPM].get('scale_factor', 6.0)
            user_vel = (raw.velocity - off.velocity) / scale
            self.user_tool_rotation_changed.emit(ServoPose(raw.angle - off.angle, user_vel))

        if ServoAxis.TURNTABLE in servo_states:
            raw = servo_states[ServoAxis.TURNTABLE]
            off = self._servo_offsets[ServoAxis.TURNTABLE]
            self.user_turntable_pose_changed.emit(ServoPose(raw.angle - off.angle, raw.velocity - off.velocity))


    # ===============================================
    # View -> ViewModel 호출 메서드 (Commands)
    # ===============================================
    def origin_robot_pose(self):
        """현재 로봇 위치를 0으로 설정 (오프셋 업데이트)"""
        self._robot_offset = self._raw_robot_pose   # 현재 World 좌표를 기준점으로 설정
        # 입력 필드 초기화 요청 방송
        EVENT_BUS.control.clear_user_inputs.emit("robot")
        EVENT_BUS.log.message.emit(f"{self._log_prefix} 사용자 좌표계(로봇) 원점 설정 완료", "INFO")


    def origin_turntable_pose(self):
        """현재 턴테이블(Axis 3) 위치를 0으로 설정"""
        if ServoAxis.TURNTABLE in self._raw_servo_states:
            self._servo_offsets[ServoAxis.TURNTABLE] = self._raw_servo_states[ServoAxis.TURNTABLE]
            # 입력 필드 초기화 요청 방송
            EVENT_BUS.control.clear_user_inputs.emit("servo")
            EVENT_BUS.log.message.emit(f"{self._log_prefix} 사용자 좌표계(턴테이블) 원점 설정 완료", "INFO")

    def origin_all_pose(self):
        """모든 좌표(로봇 + 모든 서보)를 0으로 설정"""
        # 로봇 초기화
        self.origin_robot_pose()
        
        # 모든 서보(공전툴, 자전툴, 턴테이블) 초기화
        for axis in ServoAxis:
            if axis in self._raw_servo_states:
                self._servo_offsets[axis] = self._raw_servo_states[axis]
        
        # 입력 필드 초기화 요청 방송
        EVENT_BUS.control.clear_user_inputs.emit("all")
        EVENT_BUS.log.message.emit(f"{self._log_prefix} 사용자 좌표계(로봇, 턴테이블) 원점 설정 완료", "INFO")
