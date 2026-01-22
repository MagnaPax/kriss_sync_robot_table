# viewmodels/main_window_viewmodel.py
from typing import Callable, Any
from core.event_bus import EVENT_BUS
from services.plc_service import PLCService
from PyQt6.QtCore import QObject, pyqtSignal
from models.fanuc_pose_model import FANUCPoseModel
from services.sequence_service import SequenceService
from view_models.task_manager_viewmodel import TaskManagerViewModel
from view_models.robot_controller_viewmodel import RobotControllerViewModel
from view_models.world_coordinates_viewmodel import WorldCoordinatesViewModel
from view_models.servo_control_viewmodel import ServoControlViewModel
from view_models.user_coordinates_viewmodel import UserCoordinatesViewModel
from view_models.waypoints_viewmodel import WaypointsViewModel
from view_models.waypoints_viewmodel import WaypointsViewModel
from view_models.progress_bar_viewmodel import ProgressBarViewModel
from view_models.turntable_gauge_viewmodel import TurntableGaugeViewModel



class MainViewModel(QObject):
    """시스템 전체의 생명주기와 상태를 관리"""

    # 로컬 시그널 (View가 UI 갱신을 위해 구독)
    # View는 한 개의 ViewModel만 갖기 때문에
    # 라디오방송국(EventBus)으로 '아무나 들어라' 보다 전화(로컬 시그널/바인딩)로 알리는게 더 적절
    connection_status = pyqtSignal(bool)    # 연결 상태 (초록/빨강)
    show_recovery_dialog = pyqtSignal()     # 재접속 모달 띄우기 요청
    log_message = pyqtSignal(str)           # 로그 메시지
    twincat_status_data = pyqtSignal(dict)  # TwinCAT 상태 표시 위젯용 데이터 시그널


    def __init__(self, plc_service: PLCService):
        """
        PLCService를 외부에서 주입받는 이유
            PLCService는 하드웨어 연결을 담당
            앱 시작할 때 StartupManager에서 PLCService.connect_with_retry 사용해서 TwinCAT 연결
            이미 연결된 plc_service 인스턴스를 유지한 채로 MainViewModel에게 넘겨(Injection)줬기 때문. 그러지 않았다면 여기 MainViewModel에서 새 PLCService를 만들고 다시 연결해야 했다
        """
        super().__init__()

        # --- 공용 서비스 및 데이터 모델 보관 --- #
        self._service = plc_service                 # PLC 통신 서비스 (하드웨어 제어권 - 직접 호출)
        self.positon_model = FANUCPoseModel()       # 로봇 위치 데이터 모델
        self.sequence_service = SequenceService()   # 파일 입출력 서비스


        # --- 뷰모델 생성 (의존성 주입) ---
        # 로봇 컨트롤러가 이동량을 계산할 때 이 정보를 조회해야 하므로 가장 먼저 생성
        self.user_coordinates_vm = UserCoordinatesViewModel(self._service)
        # 매크로 이동 등 실제 좌표 계산에 필요하므로 로봇 컨트롤러보다 먼저 생성하여 주입
        self.world_coordinates_vm = WorldCoordinatesViewModel()
        # 하드웨어(PLC)에 직접 명령을 내려야 하므로 통신 서비스(PLCService)를 주입
        self.servo_controller_vm = ServoControlViewModel(self._service)

        # 데이터 일관성 유지 및 로봇 제어에 필요한 의존성들을 주입
        self.robot_controller_vm = RobotControllerViewModel(
            model=self.positon_model, 
            plc_service=self._service,
            user_coords_vm=self.user_coordinates_vm,
            world_coords_vm=self.world_coordinates_vm
        )
        # 파일을 읽는 서비스와 하드웨어 제어 서비스를 결합하여 자동 공정을 수행하기 위해 주입
        self.task_manager_vm = TaskManagerViewModel(self.sequence_service, self._service)


        # --- 독립적인 UI 표시용 뷰모델들 ---
        self.waypoints_vm = WaypointsViewModel()           # 경로 목록 표시 및 관리
        self.progress_bar_vm = ProgressBarViewModel()       # 전체 공정 진행률 표시
        self.turntable_gauge_vm = TurntableGaugeViewModel() # 턴테이블 각도 시각화 도구



        # [Servo] 사용자 좌표계 -> 서보 제어
        self.user_coordinates_vm.user_turntable_pose_changed.connect(
            self.servo_controller_vm._on_user_turntable_pose_changed
        )
        self.user_coordinates_vm.user_tool_revolution_changed.connect(
            self.servo_controller_vm._on_user_tool_revolution_pose_changed
        )
        self.user_coordinates_vm.user_tool_rotation_changed.connect(
            self.servo_controller_vm._on_user_tool_rotation_pose_changed
        )






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
        EVENT_BUS.conn.connection_status_changed.connect(self.connection_status)

        # system.error 에서 방송 나오면 _handle_system_error 한테 일 시킴
        EVENT_BUS.system.error.connect(self._handle_system_error)

        # connection_status_changed 방송 나오면 _update_twincat_widget_status 한테 일 시킴
        EVENT_BUS.conn.connection_status_changed.connect(self._update_twincat_widget_status)


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

    def emergency_stop(self):
        """비상 정지 요청"""
        self._service.trigger_emergency_stop()

    def retry_connection(self, ui_callback: Callable[..., Any]) -> bool:
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