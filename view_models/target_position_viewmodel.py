# view_models/target_position_viewmodel.py
from PyQt6.QtCore import Qt, QObject, pyqtSignal, pyqtSlot
from models.fanuc_pose_model import FANUCPoseModel, FANUCPose
from services.plc_service import PLCService
from services.macro_service import MacroService
from config.paths import CONFIG_MACRO_PATH
from core.event_bus import EVENT_BUS



class TargetPositionViewModel(QObject):

    # View에게 상태를 알리는 시그널
    state_changed = pyqtSignal(str)
    macros_loaded = pyqtSignal(dict)    # 매크로 데이터 가져오기 완료


    def __init__(self, model: FANUCPoseModel, plc_service: PLCService):
        """
        인자들:
            model: 데이터 모델 인스턴스
            plc_service: 앱 전역에서 공유되는 PLC 서비스 인스턴스
        """
        super().__init__()

        # 로그 메세지의 말머리(로그 발생 위치 표시)
        self.log_prefix = f"[{self.__class__.__name__}]"

        # ViewModel이 Model 인스턴스를 소유한다
        self._model = model # (사실상 안 쓰이지만 구조상 유지)

        self._plc_service = plc_service
        self._macro_service = MacroService()


    @pyqtSlot()
    def load_macro_data(self):
        """매크로 데이터 읽어서 뷰에게 전달"""

        try:
            # 서비스한테 시킴
            macro_data = self._macro_service.load_macro(CONFIG_MACRO_PATH)

            if macro_data:
                self.macros_loaded.emit(macro_data)
                EVENT_BUS.log.message.emit(f"{self.log_prefix} 매크로 데이터 로드 성공", "INFO")
                
            else:
                self.state_changed.emit("매크로 데이터 로드 실패")
                EVENT_BUS.log.message.emit(f"{self.log_prefix} 매크로 데이터 로드 실패", "ERROR")

        except Exception as e:
            self.state_changed.emit(f"매크로 데이터 로드 실패: {e}")
            EVENT_BUS.log.message.emit(f"{self.log_prefix} 매크로 데이터 로드 실패: {e}", "ERROR")



    def request_move_robot(self, fanuc_pose_obj: FANUCPose):
        """
        로봇 이동 명령을 PLCService로 위임
        View에서 직접 호출
        """

        # 상태 알림
        #   사용자에게 명령이 시스템으로 전송됐다는 피드백 주기 위해
        # View에게 전화 걸어서 알림
        self.state_changed.emit(f"이동 명령 전송 중... (좌표: {fanuc_pose_obj})")

        # PLCService 호출
        # PLCService.move_robot()은 내부적으로 QThread와 Worker를 생성, 
        # UI 멈춤 없이 비동기로 통신을 수행
        self._plc_service.move_robot_by_pose(fanuc_pose_obj)


    def update_feed_rate(self, feed_rate: float):
        """"""
        EVENT_BUS.log.message.emit(f"FEED RATE 스핀박스 값 변경됨\n사용자 입력값:{feed_rate}", "DEBUG")

        self._plc_service.set_robot_speed(feed_rate)
