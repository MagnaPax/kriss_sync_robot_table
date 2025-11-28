# demo_viewmodel.py
"""
UI의 상태 관리

UI 이벤트 처리

명령(Command) 및 로직 요청

시퀀스 반복 실행의 “조정자(Controller), '지휘자(Conductor)”
"""
from pathlib import Path
from PyQt6.QtCore import Qt, QObject, pyqtSignal, pyqtSlot, QThread, QMetaObject
from .fanuc_logic import FanucController
from .demo_plc_mock_model import MockFanucController
from .demo_worker import ConnectionWorker, CommandWorker
from .demo_plc_mock_model import MockFanucController
from .demo_service import FileService, PLCService
from .utils.coordinate_utils import dict_to_axis_list     # dict → list 변환


ControllerType = FanucController | MockFanucController


class FanucViewModel(QObject):
    """
    View(UI)와 Model(로직)을 중재하는 ViewModel
    - View는 이 ViewModel의 메서드(슬롯)만 호출
    - ViewModel은 Model의 상태를 관리하고 Worker를 통해 비동기 실행
    - View는 ViewModel의 시그널만 구독
    """

    # --- View가 구독(Observe)할 시그널 ---
    log_updated = pyqtSignal(str)           # 뷰의 로그창
    connection_changed = pyqtSignal(bool, str) # (연결상태, 상태메시지)
    sequence_data = pyqtSignal(dict)        # 시퀀스 데이터 View에 표시
    current_step_info = pyqtSignal(dict)    # 현재 실행 중인 스텝을 View에 표시




    def __init__(self, real_model: FanucController, mock_model: MockFanucController):
        super().__init__()


        # [중요] PLCService 인스턴스 생성 및 연결
        # 기존에는 ViewModel이 직접 Controller를 가지고 있었으나, 
        # 이제 제어 로직은 Service가 담당하므로 Service를 통해야 합니다.
        self._plc_service = PLCService()


        # 일단 기존 코드(직접 연결, 좌표 전송 등)가 깨지지 않도록 
        # Service 내부의 Controller를 공유하거나, Service의 기능을 사용하도록 합니다.

        # 서비스의 시그널을 VM의 시그널로 중계(Relay)
        self._plc_service.log_message.connect(self.log_updated)
        self._plc_service.connection_changed.connect(self.connection_changed)        

        # ViewModel이 Model 인스턴스를 소유
        self._real_model = real_model   # 진짜
        self._mock_model = mock_model   # 가짜

        self._file_service = FileService()


        # Service 의 시그널 구독
        self._bind_service_signals()


        # 데모 모드로 초기설정
        self._is_demo_mode = True
        self._controller: ControllerType = self._mock_model

        # --- 비서와 사무실 준비 --- #
        # 비서 자리 정원 확보
        self._worker_connection: ConnectionWorker | None = None
        self._worker_command: CommandWorker | None = None
        
        # 사무실 계약
        self._thread_connection: QThread | None = None
        self._thread_command: QThread | None = None


        # 시퀀스 순서 실행을 위한 상태 변수
        self._sequence_data: dict = {}       # 원본 데이터 (로그용)
        self._sequence_queue: list = []      # 실행용 리스트 (순서대로 정렬됨)
        self._current_step_index: int = 0    
        self._is_sequence_running: bool = False




    def _bind_service_signals(self):
        """
        VM ⬅️ Service
        Service 의 시그널을 VM 의 슬롯(메서드)에 연결 (옵저버)
        """
        # 파일 읽은 뒤 할 작업 '예약(connect)'
        self._file_service.sequence_data_from_file.connect(self._handle_sequence_data_loaded)   
        
        # TODO: 다른 Service가 추가된다면 여기에 구독 로직을 추가한다



    def _process_current_step(self):
        """
        VM -> Worker
        현재 인덱스의 데이터를 꺼내서 워커에게 전달
        """
        
        # 1. 종료 조건 확인 (리스트 길이와 비교)
        if self._current_step_index >= len(self._sequence_queue):
            self.log_updated.emit("=== 모든 시퀀스 실행 완료 ===")
            self._is_sequence_running = False
            # [옵션] 완료 후 알림 팝업 등을 위해 시그널을 추가할 수도 있음
            return

        # 2. 현재 데이터 가져오기 (리스트에서 인덱스로 접근)
        step_data = self._sequence_queue[self._current_step_index]
        
        # 3. 뷰 업데이트
        self.current_step_info.emit(step_data)
        
        # 스텝 번호는 index + 1
        step_num = self._current_step_index + 1
        self.log_updated.emit(f">> [Step {step_num}/{len(self._sequence_queue)}] 실행 중...")

        # 4. 명령 전송
        mapped_data = self._map_parser_to_command(step_data)
        self.send_command(mapped_data, is_auto=True)


    # --- Worker/Service 가 emit 한 시그널 처리 슬롯(콜백들) --- #

    ########################################
    # -- Service 에서 넘어온 데이터 처리-- #
    ########################################
    @pyqtSlot(dict)
    def _handle_sequence_data_loaded(self, sequence_data: dict):
        """파일이 로드되면 데이터를 저장하고 뷰에 알림"""
        
        # print(f"뷰모델에서 받은 데이터:\n{sequence_data}")

        # 1. 원본 데이터 저장 (뷰 로그 표시용)
        self._sequence_data = sequence_data
        
        # 2. [중요] 딕셔너리를 '실행 순서(Key)'대로 정렬하여 리스트로 변환
        #    이게 없으면 '다음 스텝'을 찾을 수 없습니다.
        #    가정: 키가 '1', '2', '10' 처럼 문자열 정수임.
        try:
            sorted_keys = sorted(sequence_data.keys(), key=int)
            self._sequence_queue = [sequence_data[k] for k in sorted_keys]
            self.log_updated.emit(f"시퀀스 준비 완료: 총 {len(self._sequence_queue)} 단계")
        except ValueError:
            self.log_updated.emit("오류: 시퀀스 데이터의 키(Step ID)가 숫자가 아닙니다.")
            self._sequence_queue = []

        # 3. 뷰에 전달
        self.sequence_data.emit(sequence_data)




    @pyqtSlot()
    def start_auto_sequence(self):
        """저장된 시퀀스를 처음부터 순차적으로 실행"""
        
        # 실행할 데이터가 있는지 확인
        if not self._sequence_queue:
            self.log_updated.emit("오류: 실행할 시퀀스 데이터가 없습니다. 파일을 먼저 로드하세요.")
            return

        if not self._controller.is_connected:
            self.log_updated.emit("오류: PLC가 연결되지 않았습니다.")
            return

        # 상태 초기화
        self._is_sequence_running = True
        self._current_step_index = 0
        self.log_updated.emit("=== 자동 시퀀스 실행 시작 ===")
        
        # 첫 번째 스텝 실행 (재귀의 시작점)
        self._process_current_step()


    ######################
    # --- View <- VM --- #
    ######################
    
    @pyqtSlot(bool)
    def set_demo_mode(self, is_demo: bool):
        """데모 모드 체크박스 상태 변경"""
        self.log_updated.emit(f"데모 모드가 {'ON' if is_demo else 'OFF'} 되었습니다.")
        self.disconnect_plc() # 모드 변경 시 연결 해제
        self._is_demo_mode = is_demo
        self._controller = self._mock_model if is_demo else self._real_model

    @pyqtSlot()
    def connect_plc(self):
        """'연결' 버튼 클릭 처리"""
        self.log_updated.emit("PLC 연결 시도 중...")
        
        # 스레드 생성 및 시작
        self._thread_connection = QThread()
        self._worker_connection = ConnectionWorker(self._controller)
        self._worker_connection.moveToThread(self._thread_connection)

        # 비서(워커)의 작업 결과를 보고받도록 설정(connection_result 시그널 예약)
        self._worker_connection.connection_result.connect(self._handle_connection_result)   

        # 정리 예약
        # Worker의 finished 시그널을 'lambda'로 연결하여 실행 시점을 지연
        #       finished 시그널이 발생할 때, lambda가 _cleanup을 호출
        self._thread_connection.finished.connect(
            lambda: self._cleanup(self._thread_connection, self._worker_connection)
        )
        
        # 비서에게 일 시작하라고 지시 (스레드 시작)
        self._thread_connection.start()
        # 스레드 시작 및 작업 실행 - 이벤트 큐를 통해 워커의 run 메서드 호출
        QMetaObject.invokeMethod(self._worker_connection, "run", Qt.ConnectionType.QueuedConnection)

    @pyqtSlot()
    def load_coordinate_sequence_file(self, file_path_obj: Path):
        """
        VM -> Service
        뷰의 '시퀀스 파일 불러오기' 버튼 클릭 처리
        서비스 레이어에게 일 시킴
        """
        # print("뷰모델의 load_coordinate_sequence_file 메서드 호출됨: FanucViewModel")
        self._file_service.load_file(file_path_obj)


    @pyqtSlot()
    def disconnect_plc(self):
        """연결 해제 처리 (모드 변경 시 또는 앱 종료 시)"""
        if self._controller.is_connected:
            self._controller.disconnect_plc()
        self.connection_changed.emit(False, "PLC 연결이 해제되었습니다.")




    @pyqtSlot(dict)
    def send_command(self, coords_dict: dict, is_auto: bool = False):
        """'좌표 전송' 버튼 클릭 처리"""

        # 자동 실행이 아닐 때만 수동 실행으로 간주 (상태 보호)
        if not is_auto and self._is_sequence_running:
            self.log_updated.emit("경고: 자동 실행 중에는 수동 명령을 보낼 수 없습니다.")
            return
        
        try:
            # coords_list = [
            #     float(coords_dict.get('X', coords_dict.get('x_coord', 0))),
            #     float(coords_dict.get('Y', coords_dict.get('y_coord', 0))),
            #     float(coords_dict.get('Z', coords_dict.get('z_coord', 0))),
            #     float(coords_dict.get('W', coords_dict.get('w_angle', 0))),
            #     float(coords_dict.get('P', coords_dict.get('p_angle', 0))),
            #     float(coords_dict.get('R', coords_dict.get('r_angle', 0))),
            #     float(coords_dict.get('F', coords_dict.get('feed', 0)))
            # ]

            coords_list = dict_to_axis_list(coords_dict)

        except (ValueError, KeyError) as e:
            # self.log_updated.emit("오류: 좌표값이 숫자가 아니거나 누락되었습니다.")
            self.log_updated.emit(f"오류: 좌표값이 숫자가 아니거나 누락되었습니다. {e}")
            self._is_sequence_running = False # 오류 시 중단
            return


        # 스레드 생성 및 시작
        # 멤버 변수(self._thread_command) 에 저장하지 않고 지역 변수 사용
        # 연속 실행 시 멤버변수를 덮어쓰면 이전 스레드가 GC되어 크래시 발생하기 때문
        thread = QThread()
        worker = CommandWorker(self._controller, coords_list)
        worker.moveToThread(thread)

        # 시그널 연결
        worker.command_finished.connect(self._handle_command_finished) # 완료 처리
        # self._worker_command.log_message.connect(self.log_updated) # Worker의 로그를 UI로 전달

        # 워커, 스레드 정리 예약
        # 람다(Lambda)에 현재 생성된 thread와 worker 객체를 기본 인자로 '캡처'해둔다.
        # 이렇게 하면 나중에 self._thread_command가 바뀌더라도, 이 람다는 
        # 자신이 생성될 때의 thread와 worker를 정확히 기억하고 정리하게 된다
        worker.finished.connect(
            lambda t=thread, w=worker: self._cleanup(t, w)
        )
        
        """
        스레드(작업 공간) 생성 및 이벤트 루프 시작
        운영체제(OS) 레벨에서 새로운 Thread 를 물리적으로 생성

        "사무실 문을 열고 컴퓨터를 켜라" (작업 공간 준비)
        """
        thread.start()

        """
        특정 스레드에게 작업 실행 요청
        self._worker 객체의 run 함수를 호출해달라고 이벤트 큐에 요청서(Event)를 제출

        "김대리, 이제 일 시작해!" (작업 지시)
        """
        QMetaObject.invokeMethod(worker, "run", Qt.ConnectionType.QueuedConnection)






    # 워커 객체, 스레드 정리 메서드
    def _cleanup(self, thread: QThread | None = None, worker: QObject | None = None):
        """Worker와 Thread 안전 정리"""

        if thread is not None:
            if thread.isRunning():
                thread.quit()
                if not thread.wait(2000):  # 타임아웃 체크 추가
                    print("경고: 스레드가 정상 종료되지 않았습니다.")
            thread.deleteLater()

        if worker is not None:
            worker.deleteLater()



    ###############################################
    # --- VM <- Worker 보고받을 슬롯 (콜백들) --- #
    ###############################################

    @pyqtSlot(bool, str)
    def _handle_connection_result(self, success: bool, status_msg: str):
        """연결 작업 완료 시 Worker로부터 보고받음"""
        self.log_updated.emit(status_msg)
        self.connection_changed.emit(success, status_msg)

    # @pyqtSlot(str)
    # def _handle_command_finished(self, status_msg: str):
    #     """명령 전송 완료 시 Worker로부터 보고받음"""
    #     self.log_updated.emit(status_msg)
    #     self.connection_changed.emit(self._controller.is_connected, "명령 전송 완료")


    # --- Worker 완료 핸들러 ---
    @pyqtSlot(str)
    def _handle_command_finished(self, status_msg: str):
        """명령 하나가 끝났을 때 호출됨"""
        
        if self._is_sequence_running:
            # 자동 실행 중이라면 다음 스텝으로 진행
            self._current_step_index += 1
            # 재귀 호출처럼 보이지만, 시그널에 의한 비동기 호출이므로 스택 오버플로우 없음
            self._process_current_step()

        else:
            # 수동 실행
            self.log_updated.emit(status_msg)
            self.connection_changed.emit(self._controller.is_connected, "명령 전송 완료")


    def _map_parser_to_command(self, parser_data: dict) -> dict:
        """파서 데이터(소문자 키)를 UI/Command 데이터(대문자 키)로 변환"""
        # 파서 키: x_coord, y_coord ... 
        # Command가 기대하는 키: X, Y, Z ... (또는 위 send_command에서 처리했으므로 생략 가능)
        # 하지만 명시적으로 변환해주면 디버깅에 좋음
        return {
            'X': parser_data.get('x_coord'),
            'Y': parser_data.get('y_coord'),
            'Z': parser_data.get('z_coord'),
            'W': parser_data.get('w_angle'),
            'P': parser_data.get('p_angle'),
            'R': parser_data.get('r_angle'),
            'F': parser_data.get('feed'),
        }
    

    # --- 퍼블릭 메서드 --- #
    def has_sequence_data(self) -> bool:
        """시퀀스 데이터가 있는지 확인"""
        return len(self._sequence_queue) > 0
    






    # ============================================================
    # [추가된 부분] View의 제어 버튼 클릭 시 호출될 메서드들
    # 🖱️ [View -> VM]
    # ============================================================
    @pyqtSlot()
    def control_pause(self):
        """일시 정지 버튼 클릭 시 호출"""
        self.log_updated.emit("🖱️ [View -> VM] 일시 정지 (Pause)")
        self._plc_service.request_pause()

    @pyqtSlot()
    def control_resume(self):
        """다시 시작 버튼 클릭 시 호출"""
        self.log_updated.emit("🖱️ [View -> VM] 다시 시작 (Resume)")
        self._plc_service.request_resume()

    @pyqtSlot()
    def control_full_stop(self):
        """완전 멈춤 버튼 클릭 시 호출"""
        self.log_updated.emit("🖱️ [View -> VM] 완전 멈춤 (Stop)")
        
        # 소프트웨어적으로 시퀀스 루프가 돌고 있다면 즉시 끊어줌
        if self._is_sequence_running:
            self._is_sequence_running = False
            self.log_updated.emit("자동 시퀀스 실행 플래그를 해제했습니다.")

        self._plc_service.request_stop()

    @pyqtSlot()
    def start_auto_sequence(self):
        """자동 시퀀스 시작"""
        if not self.has_sequence_data():
            self.log_updated.emit("오류: 시퀀스 데이터가 없습니다.")
            return

        # 1. 프로세스 시작 신호 (RSR2 Pulse + DI181 ON)
        #    Service를 통해 로봇에게 '나 이제 시작한다'고 알림
        self._plc_service.request_start_process()

        # 2. 상태 설정
        self._is_sequence_running = True
        self._current_step_index = 0
        self.log_updated.emit("=== 자동 시퀀스 데이터 전송 시작 ===")
        
        # 3. 데이터 전송 루프 시작
        self._process_current_step()