# viewmodels/main_window_viewmodel.py
from core.event_bus import EVENT_BUS
from services.plc_service import PLCService
from PyQt6.QtCore import QObject, pyqtSignal
from models.fanuc_pose_model import FANUCPoseModel
from services.sequence_service import SequenceService
from view_models.task_manager_viewmodel import TaskManagerViewModel
from view_models.target_position_viewmodel import TargetPositionViewModel
from view_models.world_coordinates_viewmodel import WorldCoordinatesViewModel



class MainViewModel(QObject):

    # 로컬 시그널 (View가 UI 갱신을 위해 구독)
    # View는 한 개의 ViewModel만 갖기 때문에
    # 라디오방송국(EventBus)으로 '아무나 들어라' 보다 전화(로컬 시그널/바인딩)로 알리는게 더 적절
    connection_status = pyqtSignal(bool)    # 연결 상태 (초록/빨강)
    show_recovery_dialog = pyqtSignal()     # 재접속 모달 띄우기 요청
    log_message = pyqtSignal(str)           # 로그 메시지
    twincat_status_data = pyqtSignal(dict)  # TwinCAT 상태 표시 위젯용 데이터 시그널


    def __init__(self, plc_service: PLCService):
        super().__init__()

        # Service 인스턴스를 소유 (직접 호출 위해)
        self._service = plc_service

        # 하위 뷰모델 생성 및 관리
        self.positon_model = FANUCPoseModel()

        # TargetPosition 뷰모델 생성 (모델 + 서비스 주입)
        self.target_position_vm = TargetPositionViewModel(self.positon_model, self._service)

        self.sequence_service = SequenceService()

        # --- MainViewModel이 뷰모델 소유 --- #
        self.world_coordinates_vm = WorldCoordinatesViewModel()
        # TaskManager는 보통 SequenceService가 필요하므로 여기서 생성해서 주입
        self.task_manager_vm = TaskManagerViewModel(self.sequence_service)




        """
        EventBus 구독
        - 집에 있는 오디오의 라디오 채널을 해당 주파수에 맞춰놓겠다

        예:
            VM : 재난 채널(system.error)에 주파수를 맞춰놓음
            S  : 방송국(EventBus)의 재난 채널(system.error)에 대고 소리침
            VM : PLCService 가 소리치는 것을 들음
            VM : _handle_system_error 에게 일하라고 시킴
        """

        # 'connection_status_changed' 라는 주파수에서 방송이 나오면 내 전화기(self.connection_status)로 연결해
        EVENT_BUS.conn.status_changed.connect(self.connection_status)

        # system.error 에서 방송 나오면 _handle_system_error 한테 일 시킴
        EVENT_BUS.system.error.connect(self._handle_system_error)

        # connection_status_changed 방송 나오면 _update_twincat_widget_status 한테 일 시킴
        EVENT_BUS.conn.status_changed.connect(self._update_twincat_widget_status)


        # --- 초기 상태 동기화 --- #
        # 뷰모델이 생성되는 시점에 이미 연결되어 있다면(StartupManager 덕분에)
        # View에게 바로 연결됐다는 상태를 보내줘야
        if self.is_connected:
            from PyQt6.QtCore import QTimer
            # QTimer.singleShot을 쓰는 이유: View가 완전히 바인딩된 후에 실행되게 하기 위해
            QTimer. singleShot(100, lambda: self._update_twincat_widget_status(True))



    @property
    def is_connected(self) -> bool:
        return self._service.connector.is_connected


    # ==========================================================
    # [View -> ViewModel] View에서 호출하는 명령들
    # ==========================================================
    
    def request_disconnect(self):
        """연결 해제 요청"""
        self._service.disconnect_plc()

    def retry_connection(self, ui_callback) -> bool:
        """
        재접속 시도 (View의 콜백 함수를 받아 Service에 전달)
        """
        return self._service.connect_with_retry(ui_callback)


    # ==========================================================
    # [EventBus -> ViewModel] 내부 로직 처리
    # ==========================================================
    
    def _handle_system_error(self, message: str):
        """시스템 에러 발생 시 처리"""
        if message == "TwinCAT_DISCONNECTED":
            # "복구 화면 띄워!"라고 방송 송출 - View 가 듣고 있다가 UI 처리
            self.show_recovery_dialog.emit()

    def _update_twincat_widget_status(self, is_connected: bool):
        """
        True/False 상태를 StatusIndicatorBox가 이해할 수 있는 dict 형태로 변환하여 송출
        """
        state_text = "connected" if is_connected else "disconnected"
        
        data = {
            'title': 'TwinCAT',   # 위젯 제목
            'state': state_text   # 상태 (색상 결정됨)
        }
        
        # 로컬 시그널로 전화 건다 - View 가 '전화' 받아서 UI 처리 (EVENT BUS 아님)
        self.twincat_status_data.emit(data)