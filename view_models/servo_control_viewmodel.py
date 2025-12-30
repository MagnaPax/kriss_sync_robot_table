# view_models/servo_control_viewmodel.py
from typing import TYPE_CHECKING
from PyQt6.QtCore import QObject, pyqtSignal
from core.event_bus import EVENT_BUS

if TYPE_CHECKING:
    from services.plc_service import PLCService



class ServoControlViewModel(QObject):
    """서보모터 제어용 뷰모델"""
    # View에게 상태를 알리는 시그널 (TaskManagerViewModel과 일관성 유지)
    busy_state_changed = pyqtSignal(dict)

    def __init__(self, plc_service: "PLCService"):
        """
        인자:
            plc_service: 앱 전체에서 공유되는 PLC 서비스 인스턴스
        """
        super().__init__()
        self._log_prefix = f"[{self.__class__.__name__}]"
        self._plc_service = plc_service

        # '바쁨 상태' 방송이 오면 -> 내 로컬 시그널로 재방송
        EVENT_BUS.data.servo_busy_status.connect(self.busy_state_changed.emit)


    # ================================
    # 서보 모터 제어
    # ================================
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
