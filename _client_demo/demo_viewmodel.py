# demo_viewmodel.py
from PyQt6.QtCore import Qt, QObject, pyqtSignal, pyqtSlot, QThread, QMetaObject
from fanuc_logic import FanucController
from _client_demo.demo_plc_mock_model import MockFanucController
from _client_demo.demo_worker import ConnectionWorker, CommandWorker
from _client_demo.demo_plc_mock_model import MockFanucController


ControllerType = FanucController | MockFanucController


class FanucViewModel(QObject):
    """
    View(UI)와 Model(로직)을 중재하는 ViewModel
    - View는 이 ViewModel의 메서드(슬롯)만 호출
    - ViewModel은 Model의 상태를 관리하고 Worker를 통해 비동기 실행
    - View는 ViewModel의 시그널만 구독
    """

    # --- View가 구독(Observe)할 시그널 ---
    log_updated = pyqtSignal(str)
    connection_changed = pyqtSignal(bool, str) # (연결상태, 상태메시지)


    def __init__(self, real_model: FanucController, mock_model: MockFanucController):
        super().__init__()

        # ViewModel이 Model 인스턴스를 소유
        self._real_model = real_model   # 진짜
        self._mock_model = mock_model   # 가짜

        # 기본값은 데모 모드        
        self._is_demo_mode = True
        self._controller: ControllerType = self._mock_model

        # --- 비서와 사무실 준비 --- #
        # 비서 고용
        self._worker_connection: ConnectionWorker | None = None
        self._worker_command: CommandWorker | None = None
        
        # 사무실 생성
        self._thread_connection: QThread | None = None
        self._thread_command: QThread | None = None


    ##############################
    # --- View가 호출할 슬롯 --- #
    ##############################
    
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
    def disconnect_plc(self):
        """연결 해제 처리 (모드 변경 시 또는 앱 종료 시)"""
        if self._controller.is_connected:
            self._controller.disconnect_plc()
        self.connection_changed.emit(False, "PLC 연결이 해제되었습니다.")

    @pyqtSlot(dict)
    def send_command(self, coords_dict: dict):
        """'좌표 전송' 버튼 클릭 처리"""
        try:
            coords_list = [
                float(coords_dict['X']), float(coords_dict['Y']), float(coords_dict['Z']),
                float(coords_dict['W']), float(coords_dict['P']), float(coords_dict['R']),
                float(coords_dict['F'])
            ]
        except (ValueError, KeyError):
            self.log_updated.emit("오류: 좌표값이 숫자가 아니거나 누락되었습니다.")
            return
            
        # 스레드 생성 및 시작
        self._thread_command = QThread()
        self._worker_command = CommandWorker(self._controller, coords_list)
        self._worker_command.moveToThread(self._thread_command)

        # 시그널 연결
        self._worker_command.log_message.connect(self.log_updated) # Worker의 로그를 UI로 전달
        self._worker_command.command_finished.connect(self._handle_command_finished)

        # 워커, 스레드 정리 예약
        # self._worker_command.finished.connect(self._cleanup(self._command_thread, self._worker_command))
        self._worker_command.finished.connect(
            lambda: self._cleanup(self._thread_command, self._worker_command)
        )
        
        # 스레드 시작
        self._thread_command.start()
        # 스레드 시작 및 작업 실행 - 이벤트 큐를 통해 워커의 run 메서드 호출
        QMetaObject.invokeMethod(self._worker_command, "run", Qt.ConnectionType.QueuedConnection)


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



    #########################################
    # --- Worker가 보고할 슬롯 (콜백들) --- #
    #########################################

    @pyqtSlot(bool, str)
    def _handle_connection_result(self, success: bool, status_msg: str):
        """연결 작업 완료 시 Worker로부터 보고받음"""
        self.log_updated.emit(status_msg)
        self.connection_changed.emit(success, status_msg)

    @pyqtSlot(str)
    def _handle_command_finished(self, status_msg: str):
        """명령 전송 완료 시 Worker로부터 보고받음"""
        self.log_updated.emit(status_msg)
        self.connection_changed.emit(self._controller.is_connected, "명령 전송 완료")
