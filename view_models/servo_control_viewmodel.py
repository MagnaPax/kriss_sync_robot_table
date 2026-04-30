# view_models/servo_control_viewmodel.py
from typing import TYPE_CHECKING, Dict, Any
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from core.event_bus import EVENT_BUS
from config.data_formats import (
    KEY_TURNTABLE_DEG,
    KEY_TURNTABLE_FEED_RATE,
    KEY_TOOL_REV_RPM,
    KEY_TOOL_ROT_RPM
)
from models.servo_pose_model import ServoPose
from models.servo_pose_key import ServoAxis

if TYPE_CHECKING:
    from services.plc_service import PLCService



class ServoControlViewModel(QObject):
    """서보모터 제어용 뷰모델"""

    # 로컬 시그널 - View 가 구독
    busy_state_changed = pyqtSignal(dict)               # 서보가 움직이고 있는지 아닌지
    servo_inputs_clear = pyqtSignal()                   # 서보 입력 필드 초기화 요청 시그널
    servo_axis_motion_changed = pyqtSignal(dict)        # 서보 축 값 바꾸기
    disable_buttons = pyqtSignal(str, bool)             # 버튼 비활성화


    def __init__(self, plc_service: "PLCService"):
        """
        인자:
            plc_service: 앱 전체에서 공유되는 PLC 서비스 인스턴스
        """
        super().__init__()
        self._log_prefix = f"[{self.__class__.__name__}]"
        self._plc_service = plc_service

        # 사용자 좌표계(서보) 값 캐싱
        self._current_user_servo_states: dict[ServoAxis, ServoPose] = {}

        # EventBus 연결
        self._bind_signals()



    def _bind_signals(self):
        # '움직이고 있다'는 방송이 오면 -> 내 로컬 시그널로 그대로 재방송
        EVENT_BUS.control.servo_physical_moving_status_changed.connect(self.busy_state_changed.emit)
        # [EventBus 구독] 수동 입력 필드 초기화 요청
        EVENT_BUS.control.clear_user_inputs.connect(self._on_clear_manual_inputs)
        # [EventBus 구독] 웨이포인트 선택됨
        EVENT_BUS.data.waypoints_selected.connect(self._on_replace_inputs_by_selected_sequence_on_waypoints_table)
        # '시퀀스 실행중' 방송 청취 -> 내 로컬 시그널로 바로 재방송
        EVENT_BUS.data.sequence_in_progress.connect(self.disable_buttons.emit)



    # ===============================================
    # 시그널 슬롯 [물리적 시그널 수신]
    # ===============================================
    @pyqtSlot(str)
    def _on_clear_manual_inputs(self, type_: str):
        """EventBus로부터 입력 필드 초기화 요청 수신"""
        self._handle_clear_inputs(type_)

    @pyqtSlot(dict)
    def _on_replace_inputs_by_selected_sequence_on_waypoints_table(self, row_data: Dict[str, Any]):
        """WaypointsTable에서 선택된 시퀀스를 View에게 전달하여 입력 필드를 채우게 함"""
        self._handle_sequence_selection(row_data)

    @pyqtSlot(object)
    def _on_user_tool_revolution_pose_changed(self, pose: ServoPose):
        self._current_user_servo_states[ServoAxis.TOOL_REVOLUTION] = pose

    @pyqtSlot(object)
    def _on_user_tool_rotation_pose_changed(self, pose: ServoPose):
        self._current_user_servo_states[ServoAxis.TOOL_ROTATION] = pose

    @pyqtSlot(object)
    def _on_user_turntable_pose_changed(self, pose: ServoPose):
        self._current_user_servo_states[ServoAxis.TURNTABLE] = pose



    # ===============================================
    # 핸들러 [논리적 흐름 담당]
    # ===============================================
    def _handle_clear_inputs(self, type_: str):
        """입력 필드 초기화 로직"""
        # "servo" 또는 "all" 일 때만 반응
        if type_ in ["servo", "all"]:
            self.servo_inputs_clear.emit()

    def _handle_sequence_selection(self, row_data: Dict[str, Any]):
        """시퀀스 선택 시 입력 필드 업데이트 로직"""
        EVENT_BUS.log.message.emit(f"{self._log_prefix} 선택된 시퀀스 값: {row_data}", "DEBUG")
        
        try:
            # 필요한 값만 추출하여 딕셔너리 생성
            servo_data = {
                KEY_TURNTABLE_DEG:       float(row_data.get(KEY_TURNTABLE_DEG, 0.0)),
                KEY_TURNTABLE_FEED_RATE: float(row_data.get(KEY_TURNTABLE_FEED_RATE, 10.0)),
                KEY_TOOL_REV_RPM:        float(row_data.get(KEY_TOOL_REV_RPM, 0.0)),
                KEY_TOOL_ROT_RPM:        float(row_data.get(KEY_TOOL_ROT_RPM, 0.0))
            }

            self.servo_axis_motion_changed.emit(servo_data)
            EVENT_BUS.log.message.emit(f"{self._log_prefix} 선택된 시퀀스에서 추출한 서보 값:{servo_data}", "DEBUG")

        except Exception as e:
            EVENT_BUS.log.message.emit(f"{self._log_prefix} 서보 데이터 파싱 실패: {e}", "WARNING")



    # ===============================================
    # View -> ViewModel 호출 메서드 (Commands)
    # ===============================================
    def start_manual(self, data: dict[str, float]):
        """
        수동 동작 시작
        단위 변환 및 상세 제어 로직은 Adapter/Model 레이어로 위임
        """

        # PLC 통신을 시작하는 트리거이므로 try-except로 처리
        try:
            # 입력받은 data는 "사용자가 원하는 좌표와 속도" 이므로,
            # 현재 상태를 고려하여 "실제 목표 좌표와 속도"로 변환
            target_data = self._calculate_target_manual_data(data)
            
            self._plc_service.move_servo_by_manual(target_data)

        except Exception as e:
            EVENT_BUS.log.message.emit(f"{self._log_prefix} 서보모터 수동 동작 시작 실패: {e}", "ERROR")

    def stop_manual(self):
        """모든 축 정지"""
        try:
            self._plc_service.stop_servo_all()
        except Exception as e:
            EVENT_BUS.log.message.emit(f"{self._log_prefix} 서보모터 수동 동작 정지 실패: {e}", "ERROR")

    def home_manual(self):
        """모든 축(혹은 지정된 축) 원점 복귀"""
        try:
            self._plc_service.home_servo_all()
        except Exception as e:
            EVENT_BUS.log.message.emit(f"{self._log_prefix} 서보모터 수동 원점 복귀 실패: {e}", "ERROR")

    def reset_manual(self):
        """모든 축 에러 리셋"""
        try:
            self._plc_service.reset_servo_all()
        except Exception as e:
            EVENT_BUS.log.message.emit(f"{self._log_prefix} 서보모터 에러 리셋 실패: {e}", "ERROR")



    # ===============================================
    # 헬퍼 메서드
    # ===============================================
    def _calculate_target_manual_data(self, input_data: Dict[str, float]) -> Dict[str, float]:
        """
        실제로 이동할 거리와 속도 계산 (Delta)
        TargetDelta = TargetUser - CurrentUser
        """
        # 결과 담을 딕셔너리
        target_data: Dict[str, float] = {}

        # 1. 턴테이블 (Angle)
        if KEY_TURNTABLE_DEG in input_data:
            target_user_deg = float(input_data[KEY_TURNTABLE_DEG])
            
            curr_user = self._current_user_servo_states.get(ServoAxis.TURNTABLE)

            if curr_user:
                # Delta 계산 (입력값 - 현재값)
                delta_deg = target_user_deg - curr_user.angle
                target_data[KEY_TURNTABLE_DEG] = delta_deg
                EVENT_BUS.log.message.emit(f"{self._log_prefix} 턴테이블 이동량 계산: {target_user_deg} - {curr_user.angle} = {delta_deg}", "DEBUG")

        # 2. 공전 툴 (RPM)
        if KEY_TOOL_REV_RPM in input_data:
            target_user_rpm = float(input_data[KEY_TOOL_REV_RPM])
            curr_user = self._current_user_servo_states.get(ServoAxis.TOOL_REVOLUTION)
            
            if curr_user:
                # RPM은 '속도'이지만, 여기서도 사용자가 입력한 값과 현재 값의 차이만큼을
                # '변화시켜라' 라는 의미보다는,
                # "나는 100RPM으로 돌고 싶어" -> 현재 0RPM -> 100RPM 명령 (Delta 100)
                # "나는 100RPM으로 돌고 싶어" -> 현재 90RPM -> 10RPM 명령 (Delta 10) ??
                # 로봇(위치)과 달리 속도(RPM) 제어에서 Delta를 쓰는건 조금 어색하지만
                # 사용자 요구사항이 "입력값 - 기준값 = 최종 목표" 이므로 이를 따름.
                # "이 값을 기준으로 ... 뺀 값이 최종 목표 각도와 속도이다" 라고 명시함.
                
                # Delta RPM 계산
                delta_rpm = target_user_rpm - curr_user.velocity
                target_data[KEY_TOOL_REV_RPM] = delta_rpm
                EVENT_BUS.log.message.emit(f"{self._log_prefix} 공전 속도량 계산: {target_user_rpm} - {curr_user.velocity} = {delta_rpm}", "DEBUG")

        # 3. 자전 툴 (RPM)
        if KEY_TOOL_ROT_RPM in input_data:
            target_user_rpm = float(input_data[KEY_TOOL_ROT_RPM])
            curr_user = self._current_user_servo_states.get(ServoAxis.TOOL_ROTATION)
            
            if curr_user:
                delta_rpm = target_user_rpm - curr_user.velocity
                target_data[KEY_TOOL_ROT_RPM] = delta_rpm
                EVENT_BUS.log.message.emit(f"{self._log_prefix} 자전 속도량 계산: {target_user_rpm} - {curr_user.velocity} = {delta_rpm}", "DEBUG")

        # 피드 속도(Feed Rate) 등 다른 키값들은 Delta 계산 대상이 아닐 수 있음 (보통 절대값 설정)
        # 하지만 KEY_TURNTABLE_FEED_RATE 등이 input_data에 있다면 그대로 넘겨줘야 함.
        # 위 로직에서 target_data = {}로 시작했으므로, 누락된 키들을 복사해야 함.
        for key, value in input_data.items():
            if key not in target_data:
                target_data[key] = value

        return target_data


