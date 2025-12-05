# view_models/target_position_viewmodel.py
from PyQt6.QtCore import Qt, QObject, pyqtSignal, pyqtSlot
from models.position_model import PositionModel, Position
from services.plc_service import PLCService
from services.macro_service import MacroService
from config.paths import CONFIG_MACRO_PATH



class TargetPositionViewModel(QObject):

    # View에게 상태를 알리는 시그널
    state_changed = pyqtSignal(str)
    macros_loaded = pyqtSignal(dict)    # 매크로 데이터 가져오기 완료


    def __init__(self, model: PositionModel, plc_service: PLCService):
        """
        인자들:
            model: 데이터 모델 인스턴스
            plc_service: 앱 전역에서 공유되는 PLC 서비스 인스턴스
        """
        super().__init__()

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
            else:
                self.state_changed.emit("매크로 데이터 로드 실패")

        except Exception as e:
            self.state_changed.emit(f"매크로 데이터 로드 실패: {e}")


    def request_move_robot(self, position: Position):
        """
        로봇 이동 명령을 PLCService로 위임
        View에서 직접 호출
        """

        # 상태 알림
        #   사용자에게 명령이 시스템으로 전송됐다는 피드백 주기 위해
        # View에게 전화 걸어서 알림
        self.state_changed.emit(f"이동 명령 전송 중... (좌표: {position})")

        # PLCService 호출
        # PLCService.move_robot()은 내부적으로 QThread와 Worker를 생성, 
        # UI 멈춤 없이 비동기로 통신을 수행
        self._plc_service.move_robot(position)

