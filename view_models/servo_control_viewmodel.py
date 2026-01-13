# view_models/servo_control_viewmodel.py
from typing import TYPE_CHECKING
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from core.event_bus import EVENT_BUS
from config.data_formats import (
    KEY_TURNTABLE_DEG,
    KEY_TURNTABLE_FEED_RATE,
    KEY_TOOL_REV_RPM,
    KEY_TOOL_ROT_RPM
)

if TYPE_CHECKING:
    from services.plc_service import PLCService



class ServoControlViewModel(QObject):
    """서보모터 제어용 뷰모델"""

    # 로컬 시그널 - View 가 구독
    busy_state_changed = pyqtSignal(dict)
    servo_inputs_clear = pyqtSignal()                   # 서보 입력 필드 초기화 요청 시그널
    servo_axis_motion_changed = pyqtSignal(dict)        # 서보 축 값 바꾸기
    disable_buttons = pyqtSignal(bool)                  # 버튼 비활성화


    def __init__(self, plc_service: "PLCService"):
        """
        인자:
            plc_service: 앱 전체에서 공유되는 PLC 서비스 인스턴스
        """
        super().__init__()
        self._log_prefix = f"[{self.__class__.__name__}]"
        self._plc_service = plc_service

        # EventBus 연결
        self._bind_signals()


    def _bind_signals(self):
        # '바쁨 상태' 방송이 오면 -> 내 로컬 시그널로 그대로 재방송
        EVENT_BUS.data.servo_busy_status.connect(self.busy_state_changed.emit)
        # [EventBus 구독] 수동 입력 필드 초기화 요청
        EVENT_BUS.control.clear_user_inputs.connect(self._on_clear_manual_inputs)
        # [EventBus 구독] 웨이포인트 선택됨
        EVENT_BUS.data.waypoints_selected.connect(self._on_replace_inputs_by_selected_sequence_on_waypoints_table)
        # '시퀀스 실행중' 방송이 오면 -> 내 로컬 시그널로 그대로 재방송
        EVENT_BUS.data.sequence_running_changed.connect(self.disable_buttons)



    # ===============================================
    # 시그널 슬롯 [물리적 시그널 수신]
    # ===============================================
    @pyqtSlot(str)
    def _on_clear_manual_inputs(self, type_: str):
        """EventBus로부터 입력 필드 초기화 요청 수신"""
        self._handle_clear_inputs(type_)

    @pyqtSlot(dict)
    def _on_replace_inputs_by_selected_sequence_on_waypoints_table(self, row_data: dict):
        """WaypointsTable에서 선택된 시퀀스를 View에게 전달하여 입력 필드를 채우게 함"""
        self._handle_sequence_selection(row_data)



    # ===============================================
    # 핸들러 [논리적 흐름 담당]
    # ===============================================
    def _handle_clear_inputs(self, type_: str):
        """입력 필드 초기화 로직"""
        # "servo" 또는 "all" 일 때만 반응
        if type_ in ["servo", "all"]:
            self.servo_inputs_clear.emit()

    def _handle_sequence_selection(self, row_data: dict):
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
        try:
            self._plc_service.move_servo_by_manual(data)
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
