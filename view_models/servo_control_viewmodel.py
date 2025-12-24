# view_models/servo_control_viewmodel.py
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from core.event_bus import EVENT_BUS



class ServoControlViewModel(QObject):
    """서보모터 제어용 뷰모델"""
    def __init__(self, plc_service: "PLCService"):
        """
        인자:
            plc_service: 앱 전체에서 공유되는 PLC 서비스 인스턴스
        """
        super().__init__()
        self._log_prefix = f"[{self.__class__.__name__}]"
        self._plc_service = plc_service

    def start_manual(self, data: dict[str, float]):
        """
        수동 동작 시작
        단위 변환 및 상세 제어 로직은 Adapter/Model 레이어로 위임
        """
        try:
            EVENT_BUS.log.message.emit(f"{self._log_prefix} 서보모터 수동 동작 시작 요청: {data}", "INFO")
            
            # 서비스에 명령 위임
            # PLCService.move_robot()은 내부적으로 QThread와 Worker를 생성, UI 멈춤 없이 비동기로 통신을 수행
            self._plc_service.move_servo_by_manual(data)

        except Exception as e:
            EVENT_BUS.log.message.emit(f"{self._log_prefix} 서보모터 수동 동작 시작 실패: {e}", "ERROR")

    def stop_manual(self):
        """모든 축 정지"""
        try:
            EVENT_BUS.log.message.emit(f"{self._log_prefix} 서보모터 수동 동작 정지 명령", "INFO")
            self._plc_service.stop_servo_all()
        except Exception as e:
            EVENT_BUS.log.message.emit(f"{self._log_prefix} 서보모터 수동 동작 정지 실패: {e}", "ERROR")

    def home_manual(self):
        """모든 축(혹은 지정된 축) 원점 복귀"""
        try:
            EVENT_BUS.log.message.emit(f"{self._log_prefix} 서보모터 수동 원점 복귀 명령", "INFO")
            # 턴테이블(Axis 3) 원점 복귀 우선 수행
            self._plc_service.home_servo_all()
            # 툴(1, 2)도 필요 시 추가
            self._plc_service.home_servo_axis(1)
            self._plc_service.home_servo_axis(2)
        except Exception as e:
            EVENT_BUS.log.message.emit(f"{self._log_prefix} 서보모터 수동 원점 복귀 실패: {e}", "ERROR")