# view_models/robot_controller_viewmodel.py
from typing import TYPE_CHECKING
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from core.event_bus import EVENT_BUS
from config.paths import CONFIG_MACRO_PATH
from services.macro_service import MacroService
from models.fanuc_pose_model import FANUCPoseModel, FANUCPose

if TYPE_CHECKING:
    from services.plc_service import PLCService
    from view_models.user_coordinates_viewmodel import UserCoordinatesViewModel
    from view_models.world_coordinates_viewmodel import WorldCoordinatesViewModel



class RobotControllerViewModel(QObject):

    # 로컬 시그널 - View 가 구독
    robot_moving_status_changed = pyqtSignal(dict)              # 로봇 움직이고 있는지 아닌지
    robot_poses_clear = pyqtSignal()                            # 로봇 좌표 초기화 요청 시그널
    robot_poses_changed = pyqtSignal(FANUCPose)                 # 로봇 좌표 변경됨
    macros_loaded = pyqtSignal(dict)                            # 매크로 데이터 가져오기 완료
    sequence_processing_changed = pyqtSignal(str, bool)         # 시퀀스가 실행중임을 알림(비활성화에 사용)


    def __init__(self, model: FANUCPoseModel, plc_service: "PLCService", user_coords_vm: "UserCoordinatesViewModel", world_coords_vm: "WorldCoordinatesViewModel"):
        """
        [의존성 주입(Dependency Injection)을 사용하는 이유]
        만약 외부에서 주입받지 않고, 이 클래스 안에서 `self.xxx = XXX()` 처럼 직접 생성했다면 어떤 문제가 생길까.

        Args:
            model (FANUCPoseModel): 
                - [만약 직접 생성했다면?]
                    다른 뷰모델들과 데이터가 공유되지 않는다. 로봇이 움직여서 다른 화면의 좌표가 바뀌어도
                    이 뷰모델은 자신만의 데이터만 보고 있으므로 화면이 갱신되지 않는 '데이터 불일치'가 발생한다.
            
            plc_service (PLCService): 
                - [만약 직접 생성했다면?]
                    이미 앱 시작 시 PLC와 연결을 맺어두었는데, 여기서 또 `Connect()`를 시도하게 된다.
                    하드웨어 포트는 하나뿐이므로 'Port Occupied' 에러가 나거나, 기존 연결이 끊기는 대참사가 일어난다.
            
            user_coords_vm (UserCoordinatesViewModel) 와 world_coords_vm (WorldCoordinatesViewModel): 
                - 실제 이동 거리를 계산하기 위해 사용자의 좌표계와 로봇의 좌표계가 필요하다.
                - 만약 직접 시그널들을 connect 했다면 필요 하지 않을때도 시그널을 계속 연결하게 된다(시그널 오버헤드)

        """

        super().__init__()

        # 로그 메세지의 말머리(로그 발생 위치 표시)
        self.log_prefix = f"[{self.__class__.__name__}]"

        # ViewModel이 Model 인스턴스를 소유한다
        self._model = model # (사실상 안 쓰이지만 구조상 유지)

        self._plc_service = plc_service
        self._user_coords_vm = user_coords_vm
        self._world_coords_vm = world_coords_vm
        self._macro_service = MacroService()

        # EventBus 연결
        self._bind_signals()



    def _bind_signals(self):
        # '로봇이 움직이고 있다'는 방송이 오면 -> 내 로컬 시그널로 그대로 재방송
        EVENT_BUS.control.robot_moving_status_changed.connect(self.robot_moving_status_changed.emit)
        # 입력 필드 초기화
        EVENT_BUS.control.clear_user_inputs.connect(self._on_clear_manual_inputs)
        # 웨이포인트에서 선택된 시퀀스
        EVENT_BUS.data.waypoints_selected.connect(self._on_replace_inputs_by_selected_sequence_on_waypoints_table)
        # '시퀀스 실행중' 방송 청취 -> 내 로컬 시그널로 바로 재방송
        EVENT_BUS.data.sequence_in_progress.connect(self.sequence_processing_changed.emit)



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
    def load_macro_data(self):
        """매크로 데이터 읽어서 뷰에게 전달"""

        try:
            # 파일 읽는 것 서비스한테 시킴
            macro_data = self._macro_service.load_macro(CONFIG_MACRO_PATH)

            if macro_data:
                # 매크로 데이터 로컬 시그널에 실어서 emit (뷰가 connect해서 사용)
                self.macros_loaded.emit(macro_data)
                EVENT_BUS.log.message.emit(f"{self.log_prefix} 매크로 데이터 로드 성공(매크로 버튼 제목을 뽑아오기 위함)", "INFO")
                
            else:
                EVENT_BUS.log.message.emit(f"{self.log_prefix} 매크로 데이터 로드 실패", "WARNING")

        except Exception as e:
            EVENT_BUS.log.message.emit(f"{self.log_prefix} 매크로 데이터 로드 실패: {e}", "WARNING")

    def update_feed_rate(self, feed_rate: float):
        """사용자가 속도를 변경할때마다 PLC로 송신"""
        EVENT_BUS.log.message.emit(f"{self.log_prefix} 로봇 FEED RATE 변경됨: {feed_rate}", "DEBUG")
        self._plc_service.set_robot_speed(feed_rate)

    def robot_home_manual(self):
        self._plc_service.back_to_robot_home()

    def robot_stop_manual(self):
        self._plc_service.stop_robot()

    def robot_move_manual(self, fanuc_pose_obj: FANUCPose, is_macro_value: bool = False):
        """로봇 이동 명령을 PLCService로 위임"""
        # PLC 통신을 시작하는 트리거이므로 try-except로 처리
        try:
            # 입력창을 통한 값이 들어왔을때와 매크로값이 들어왔을때를 구분하여 처리
            if is_macro_value is False:
                # 사용자 입력 -> User Coordinate 기준 이동량 계산
                coordinates = self._user_coords_vm.cashed_robot_user_position
                target_raw_pose = self._calculate_relative_move_delta(fanuc_pose_obj, coordinates)
            else:
                # 매크로 값 -> World Coordinate 기준 이동량 계산
                coordinates = self._world_coords_vm.cashed_robot_world_position
                target_raw_pose = self._calculate_relative_move_delta(fanuc_pose_obj, coordinates)
            
            self._plc_service.move_robot_by_pose(target_raw_pose)
            
        except Exception as e:
            EVENT_BUS.log.message.emit(f"{self.log_prefix} 이동 명령 전송 실패: {e}", "ERROR")




    # ===============================================
    # 헬퍼 메서드
    # ===============================================
    def _calculate_relative_move_delta(self, target_user_pose: FANUCPose, coordinates: FANUCPose) -> FANUCPose:
        """
        실제 이동 거리(Delta) 계산
        목표좌표와 
        사용자가 입력한 목표 좌표와 World 좌표의 차이(Delta)를 계산한다.
        """
        # 기준 좌표
        stand_coordinates = coordinates
        
        # 차이(Delta) 계산
        delta_x = target_user_pose.x - stand_coordinates.x
        delta_y = target_user_pose.y - stand_coordinates.y
        delta_z = target_user_pose.z - stand_coordinates.z
        delta_w = target_user_pose.w - stand_coordinates.w
        delta_p = target_user_pose.p - stand_coordinates.p
        delta_r = target_user_pose.r - stand_coordinates.r

        # 실제 목표(증분) 좌표 생성
        target_delta = FANUCPose(
            x = delta_x,
            y = delta_y,
            z = delta_z,
            w = delta_w,
            p = delta_p,
            r = delta_r
        )
        
        EVENT_BUS.log.message.emit(f"{self.log_prefix} 이동량 계산: Target({target_user_pose}) - Current({stand_coordinates}) = Delta({target_delta})", "DEBUG")
        return target_delta
