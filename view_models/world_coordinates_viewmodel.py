# view_models/world_coordinates_viewmodel.py
from typing import Dict
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from core.event_bus import EVENT_BUS
from models.fanuc_pose_model import FANUCPose
from models.servo_pose_model import ServoPose
from models.servo_pose_key import ServoAxis
from config.data_formats import SERVO_SCHEMA, KEY_TOOL_REV_RPM, KEY_TOOL_ROT_RPM



class WorldCoordinatesViewModel(QObject):

    # 로컬 시그널 - View 가 구독
    robot_pose_changed = pyqtSignal(FANUCPose)      # 로봇의 현재 위치
    tool_revolution_changed = pyqtSignal(ServoPose) # 툴의 회전 상태
    tool_rotation_changed = pyqtSignal(ServoPose)   # 툴의 자전 상태
    turntable_pose_changed = pyqtSignal(ServoPose)  # 턴테이블의 현재 상태


    def __init__(self):
        super().__init__()

        # 로봇: 1대1 매칭이므로 곧바로 재방송
        EVENT_BUS.control.robot_current_pose.connect(self.robot_pose_changed.emit)

        # 서보: 딕셔너리를 받아서 나눠주기 위해 Slot 과 연결
        EVENT_BUS.control.servo_current_motion.connect(self._on_servo_data_received)


    @pyqtSlot(dict)
    def _on_servo_data_received(self, servo_states: Dict[ServoAxis, ServoPose]):
        """
        분배기 역할
            EventBus에서 통째로 넘어온 dict 꾸러미를 풀어서 
            각각의 Key(ServoAxis)에 맞는 데이터를 꺼낸 뒤 
            해당하는 Signal로 재방송(Re-emit) 해주는 로직
        """
        # [Axis 1] 툴 공전 데이터가 있으면 -> 전용 시그널 발송
        if ServoAxis.TOOL_REVOLUTION in servo_states:
            pose = servo_states[ServoAxis.TOOL_REVOLUTION]
            # [스케일링 복원] deg/s -> RPM (SERVO_SCHEMA의 scale_factor 역산)
            scale = SERVO_SCHEMA[KEY_TOOL_REV_RPM].get('scale_factor', 6.0)
            pose_rpm = ServoPose(pose.angle, pose.velocity / scale)
            self.tool_revolution_changed.emit(pose_rpm)

        # [Axis 2] 툴 자전 데이터가 있으면 -> 전용 시그널 발송
        if ServoAxis.TOOL_ROTATION in servo_states:
            pose = servo_states[ServoAxis.TOOL_ROTATION]
            # [스케일링 복원] deg/s -> RPM
            scale = SERVO_SCHEMA[KEY_TOOL_ROT_RPM].get('scale_factor', 6.0)
            pose_rpm = ServoPose(pose.angle, pose.velocity / scale)
            self.tool_rotation_changed.emit(pose_rpm)

        # [Axis 3] 턴테이블 데이터가 있으면 -> 전용 시그널 발송
        if ServoAxis.TURNTABLE in servo_states:
            pose_turntable = servo_states[ServoAxis.TURNTABLE]
            self.turntable_pose_changed.emit(pose_turntable)
