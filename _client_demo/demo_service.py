# demo_service.py

import mimetypes
from pathlib import Path
from typing import Optional
from PyQt6.QtCore import Qt, QObject, pyqtSignal, pyqtSlot, QThread, QMetaObject, QThread
from .demo_worker import ConnectionWorker, CommandWorker, FileLoadWorker, RobotControlWorker
from .demo_logger import logger
from .fanuc_logic import FanucController
from .demo_plc_mock_model import MockFanucController


# 타입 힌트를 위해 Union 사용
ControllerType = FanucController | MockFanucController


class FileService(QObject):
    """시퀀스 처리 서비스 클래스"""

    # 시그널 - 뷰모델이 구독
    sequence_data_from_file = pyqtSignal(dict)
    


    def __init__(self):
        super().__init__()

        # 비서(Worker) 직군 '정원 확보'
        self.file_worker: FileLoadWorker | None = None

        # 새로운 사무실(QThread) '공간 확보'
        self.file_thread: QThread | None = None


    def load_file(self, file_path: Path):
        """파일 읽기"""

        if self.file_thread:  # 이미 작업 중이면 무시
            return
        
        # 읽어 온 파일 종류 파악(csv, txt)
        file_type = self._detact_file_type(file_path)


        # 사무실 계약
        self.file_thread = QThread()
        # 순수 QObject, 스레드 세이프
        self.file_worker = FileLoadWorker(file_path, file_type)
        # 비서를 새 사무실로 전근 발령
        self.file_worker.moveToThread(self.file_thread)


        # 작업 결과 시그널 예약
        self.file_worker.file_loaded.connect(self._handle_file_loaded)


        # 스레드 정리
        self.file_worker.finished.connect(
            lambda: self._cleanup(self.file_thread, self.file_worker)
        )        


        # 스레드 시작
        self.file_thread.start()

        # 스레드 시작 및 작업 실행 - 이벤트 큐를 통해 워커의 run 메서드 호출
        QMetaObject.invokeMethod(self.file_worker, "run", Qt.ConnectionType.QueuedConnection)




    @pyqtSlot(bool, str, dict)
    def _handle_file_loaded(self, result: bool, status_msg: str, sequence_data: dict):
        """파일 로드 작업 완료 시 Worker로부터 보고받음"""

        # print("\n워커에서 작업 끝나서 서비스 레이어에 예약된 시그널 호출됨: _handle_file_loaded")
        # print(f"\n결과:{result}\n메시지:{status_msg}\n데이터:{sequence_data}")

        if result:
            logger.info(status_msg)
            self.sequence_data_from_file.emit(sequence_data)
            # print(f"워커->서비스에서 emit->뷰모델이구독: {sequence_data}\n파일타입{type(sequence_data)}")

        elif not result:
            logger.error(status_msg)
            # self.log_updated.emit(status_msg)
            # self.connection_changed.emit(result, status_msg)

        # logger.info(status_msg)
        # self.log_updated.emit(status_msg)
        # self.connection_changed.emit(success, status_msg)



    def _detact_file_type(self, file_path: Path) -> str:
        """csv, txt 중 파일 종류가 무엇인지 판단"""

        # mimetype 구하기 (tuple: (type, encoding))
        mime_type, encoding = mimetypes.guess_type(str(file_path))

        if mime_type == 'text/csv':
            return 'csv'
        elif mime_type == 'text/plain':
            return 'txt'
        
        # mimetype 으로 판단되지 않을 때는 확장자 검사로 찾아내기
        file_suffix = file_path.suffix.lower()

        if file_suffix == '.txt':
            return 'txt'
        elif file_suffix == '.csv':
            return 'csv'

        else:
            # 파일 형태를 끝까지 못 찾아낸다면
            logger.warning(f"지원하지 않는 파일 형식입니다: {file_path}")
            raise ValueError(f"지원하지 않는 파일 형식입니다: {file_path}")




    @pyqtSlot()
    def _cleanup(self, thread: QThread | None = None, worker: QObject | None = None):
        """Worker와 Thread 안전하게 정리"""
        if thread and thread.isRunning():
            thread.quit()
            thread.wait(3000)

        if worker:
            worker.deleteLater()
            worker = None



class PLCService(QObject):
    """
    PLC 통신 및 제어 로직을 전담하는 서비스
    - Model(Real/Mock) 관리
    - Worker 및 Thread 관리

    시그널은 시퀀스를 “한 단계씩 실행해주는” 역할까지만 한다
    현재 처리해야 될 시퀀스를 넘겨주는 것은 뷰모델의 역할
    """

    # 시그널 - 뷰모델이 구독(Observe)
    log_message = pyqtSignal(str)              # 뷰의 로그창에 보낼 메세지
    connection_changed = pyqtSignal(bool, str) # (성공여부, 메시지)
    command_finished = pyqtSignal(str)         # 명령 하나가 끝났을 때


    def __init__(self):
        super().__init__()
        
        # 모델 인스턴스 생성 - 서비스가 모델을 소유
        self._real_model = FanucController()        # 진짜
        self._mock_model = MockFanucController()    # 가짜

        # 기본값은 데모 모드
        self._current_controller: ControllerType = self._mock_model

        # 스레드/워커 참조 변수
        self._thread = None     # 사무실 계약
        self._worker = None     # 비서 자리 정원 확보


    def set_demo_mode(self, is_demo: bool):
        """데모 모드 체크박스 상태 변경"""
        # 모드 변경 전 안전하게 연결 해제
        if self._current_controller.is_connected:
            self.disconnect_plc()   # 모드 변경 시 연결 해제
            
        self._current_controller = self._mock_model if is_demo else self._real_model
        mode_str = "데모(가상)" if is_demo else "실제(Real)"
        self.log_message.emit(f"운전 모드가 [{mode_str}]로 변경되었습니다.")

    def is_connected(self) -> bool:
        return self._current_controller.is_connected

    def connect_plc(self):
        """PLC 연결 요청"""

        if self._is_busy(): return

        self.log_message.emit("PLC 연결 시도 중...")


        # 스레드 생성 및 시작
        self._thread = QThread()
        self._worker = ConnectionWorker(self._current_controller)
        self._worker.moveToThread(self._thread)

        # 결과 시그널 연결
        # 비서(워커)의 작업 결과를 보고받도록 설정(connection_result 시그널의 emit 예약)
        self._worker.connection_result.connect(self._handle_connection_result)
        
        # 정리 로직 연결
        self._worker.finished.connect(self._cleanup)


        """
        스레드(작업 공간) 생성 및 이벤트 루프 시작
        운영체제(OS) 레벨에서 새로운 Thread 를 물리적으로 생성

        "사무실 문을 열고 컴퓨터를 켜라" (작업 공간 준비)
        """
        self._thread.start()


        """
        특정 스레드에게 작업 실행 요청
        self._worker 객체의 run 함수를 호출해달라고 이벤트 큐에 요청서(Event)를 제출

        "김대리, 이제 일 시작해!" (작업 지시)
        """
        QMetaObject.invokeMethod(self._worker, "run", Qt.ConnectionType.QueuedConnection)

    def disconnect_plc(self):
        """연결 해제 처리 (모드 변경 시 또는 앱 종료 시)"""
        if self._current_controller.is_connected:
            self._current_controller.disconnect_plc()
        self.connection_changed.emit(False, "PLC 연결이 해제되었습니다.")

    def send_command(self, coords_list: list):
        """명령(좌표) 전송 요청"""

        if self._is_busy(): return

        self._thread = QThread()
        self._worker = CommandWorker(self._current_controller, coords_list)
        self._worker.moveToThread(self._thread)

        self._worker.log_message.connect(self.log_message)  # Worker의 로그를 UI로 전달
        self._worker.command_finished.connect(self.command_finished)
        self._worker.finished.connect(self._cleanup)

        self._thread.start()
        QMetaObject.invokeMethod(self._worker, "run", Qt.ConnectionType.QueuedConnection)


    # [추가된 부분] 로봇 제어 명령 요청 메서드들
    # ==========================================================

    def request_start_process(self):
        """[시작] 프로세스 루프 시작 (RSR2 Pulse + DI181 ON)"""
        self._execute_control_worker('START')

    def request_pause(self):
        """[일시정지] Cycle Stop 신호 전송"""
        self._execute_control_worker('PAUSE')

    def request_resume(self):
        """[재개] Cycle Start 신호 전송"""
        self._execute_control_worker('RESUME')

    def request_stop(self):
        """[완전정지] DI181 Loop 신호 OFF"""
        self._execute_control_worker('STOP')


    def _execute_control_worker(self, command_type: str):
        """(내부 헬퍼) 제어 워커 생성 및 실행"""
        if self._is_busy(): return

        self.log_message.emit(f"명령 요청 중... ({command_type})")

        # 스레드 생성
        self._thread = QThread()
        # 워커 생성 (현재 컨트롤러와 명령 타입 전달)
        self._worker = RobotControlWorker(self._current_controller, command_type)
        self._worker.moveToThread(self._thread)

        # 시그널 연결
        self._worker.control_result.connect(self._handle_control_result) # 결과 처리
        self._worker.finished.connect(self._cleanup) # 정리

        # 실행
        self._thread.start()
        QMetaObject.invokeMethod(self._worker, "run", Qt.ConnectionType.QueuedConnection)



    # --- 내부 헬퍼 ---
    def _is_busy(self) -> bool:
        """현재 작업 중인지 확인"""
        if self._thread and self._thread.isRunning():
            self.log_message.emit("현재 다른 작업이 진행 중입니다.")
            return True
        return False

    @pyqtSlot()
    def _cleanup(self):
        """스레드 자원 정리 (안전 버전)"""
        
        # 1. 스레드 정리
        if self._thread:
            if self._thread.isRunning():
                self._thread.quit()
                # 최대 2초 대기 (무한 대기 방지)
                if not self._thread.wait(2000): 
                    # 로그를 남기거나 강제 종료 처리
                    print("⚠️ 경고: 스레드가 정상 종료되지 않아 강제 정리합니다.")
                    # self._thread.terminate() # 필요하다면 최후의 수단으로 사용
            
            self._thread.deleteLater()
            self._thread = None  # [중요] 변수를 비워야 다음 작업 가능

        # 2. 워커 정리
        if self._worker:
            self._worker.deleteLater()
            self._worker = None  # [중요] 변수 초기화



    # --- 워커 콜백 ---
    @pyqtSlot(bool, str)
    def _handle_connection_result(self, success: bool, msg: str):
        self.log_message.emit(msg)
        self.connection_changed.emit(success, msg)

    @pyqtSlot(bool, str)
    def _handle_control_result(self, success: bool, msg: str):
        # [추가] 제어 명령 결과 처리
        if success:
            self.log_message.emit(f"✅ {msg}")
        else:
            self.log_message.emit(f"❌ 오류: {msg}")
