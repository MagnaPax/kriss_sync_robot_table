# view_models/robot_controller_viewmodel.py
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from models.fanuc_pose_model import FANUCPoseModel, FANUCPose
from services.macro_service import MacroService
from config.paths import CONFIG_MACRO_PATH
from core.event_bus import EVENT_BUS
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from services.plc_service import PLCService


class RobotControllerViewModel(QObject):

    # 로컬 시그널 - View 가 구독
    state_changed = pyqtSignal(str)
    robot_poses_clear = pyqtSignal()                # 로봇 좌표 초기화 요청 시그널
    robot_poses_changed = pyqtSignal(FANUCPose)     # 로봇 좌표 변경됨
    macros_loaded = pyqtSignal(dict)                # 매크로 데이터 가져오기 완료
    disable_buttons = pyqtSignal(str, bool)         # 버튼 비활성화


    def __init__(self, model: FANUCPoseModel, plc_service: "PLCService"):
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


        # EventBus 연결
        self._bind_signals()


    def _bind_signals(self):
        EVENT_BUS.control.clear_user_inputs.connect(self._on_clear_manual_inputs)   # 입력 필드 초기화
        EVENT_BUS.data.waypoints_selected.connect(self._on_replace_inputs_by_selected_sequence_on_waypoints_table)      # 웨이포인트에서 선택된 시퀀스
        EVENT_BUS.data.sequence_in_progress.connect(self.disable_buttons.emit)      # '시퀀스 실행중' 방송 청취 -> 내 로컬 시그널로 바로 재방송



    # ===============================================
    # 시그널 슬롯 [물리적 시그널 수신]
    # ===============================================
    @pyqtSlot(str)
    def _on_clear_manual_inputs(self, type_: str):
        """EventBus로부터 '입력 필드 초기화 요청'을 받았을 때 호출"""
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
        # "robot" 또는 "all"일 때 로봇/턴테이블 위젯(RobotControllerWidget) 초기화
        # (TargetPositionWidget은 로봇, 턴테이블 좌표 모두를 담당하므로 이 둘에 반응해야 함)
        if type_ in ["robot", "servo", "all"]:
            # [주의] TargetPositionWidget은 로봇(XYZ), 턴테이블(WPR) 모두 포함하므로
            # "servo" 요청 시에도 턴테이블(WPR) 부분 초기화를 위해 신호를 받아야 함.
            # View에서 clear_widget 구현 시 type_에 따라 부분 초기화를 하거나 
            # 여기서는 단순히 전체 초기화 요청만 보내고 View가 알아서 하도록 할 수 있음.
            # 현재 계획은 "View의 clear_widget 호출"이므로 전체 초기화가 될 가능성이 큼.
            # 만약 부분 초기화가 필요하다면 signal에 인자를 추가해야 함.
            # -> 사용자 요청상 'TargetPositionWidget의 입력 필드가 초기화' 되어야 하므로
            #    단순히 초기화 신호를 보냄.
            self.robot_poses_clear.emit()

    def _handle_sequence_selection(self, row_data: dict):
        """시퀀스 선택 시 입력 필드 업데이트 로직"""
        EVENT_BUS.log.message.emit(f"{self.log_prefix} 선택된 시퀀스 값 전체: {row_data}", "DEBUG")
        
        # 딕셔너리 -> 도메인 모델(FANUCPose) 변환
        try:
            fanuc_pose = FANUCPose.from_dict(row_data)
            self.robot_poses_changed.emit(fanuc_pose)
            EVENT_BUS.log.message.emit(f"{self.log_prefix} 선택된 시퀀스에서 FANUCPose로 변환된 값:{fanuc_pose}", "DEBUG")
        except Exception as e:
            EVENT_BUS.log.message.emit(f"{self.log_prefix} 데이터 파싱 실패: {e}", "WARNING")



    # ===============================================
    # View -> ViewModel 호출 메서드 (Commands)
    # ===============================================
    @pyqtSlot()
    def load_macro_data(self):
        """매크로 데이터 읽어서 뷰에게 전달"""

        try:
            # 서비스한테 시킴
            macro_data = self._macro_service.load_macro(CONFIG_MACRO_PATH)

            if macro_data:
                self.macros_loaded.emit(macro_data)
                EVENT_BUS.log.message.emit(f"{self.log_prefix} 매크로 데이터 로드 성공(매크로 버튼 제목을 뽑아오기 위함)", "INFO")
                
            else:
                self.state_changed.emit("매크로 데이터 로드 실패")
                EVENT_BUS.log.message.emit(f"{self.log_prefix} 매크로 데이터 로드 실패", "WARNING")

        except Exception as e:
            self.state_changed.emit(f"매크로 데이터 로드 실패: {e}")
            EVENT_BUS.log.message.emit(f"{self.log_prefix} 매크로 데이터 로드 실패: {e}", "WARNING")



    def request_move_robot(self, fanuc_pose_obj: FANUCPose):
        """
        로봇 이동 명령을 PLCService로 위임
        View에서 직접 호출
        """

        # 상태 알림
        #   사용자에게 명령이 시스템으로 전송됐다는 피드백 주기 위해
        # View에게 전화 걸어서 알림
        self.state_changed.emit(f"이동 명령 전송 중... (좌표: {fanuc_pose_obj})")

        # PLC 통신을 시작하는 트리거이므로 try-except로 처리
        try:
            # PLCService 호출
            # PLCService.move_robot()은 내부적으로 QThread와 Worker를 생성, 
            # UI 멈춤 없이 비동기로 통신을 수행
            self._plc_service.move_robot_by_pose(fanuc_pose_obj)
        except Exception as e:
            error_msg = f"이동 명령 전송 실패: {e}"
            self.state_changed.emit(error_msg)
            EVENT_BUS.log.message.emit(f"{self.log_prefix} {error_msg}", "ERROR")


    def update_feed_rate(self, feed_rate: float):
        """"""
        EVENT_BUS.log.message.emit(f"{self.log_prefix} 로봇 FEED RATE 변경됨: {feed_rate}", "DEBUG")

        self._plc_service.set_robot_speed(feed_rate)
