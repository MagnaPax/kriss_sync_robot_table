# demo_worker.py

import debugpy
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from .fanuc_logic import FanucController
from .demo_plc_mock_model import MockFanucController
from .utils.file_handler import load_text, load_csv
from .demo_logger import logger
from .utils.parser import parse_txt_to_sequence, parse_csv_to_sequence
from .parsers.sequence_parser import SequenceParserManager





# 타입 힌트를 위해 Union 사용
ControllerType = FanucController | MockFanucController


# --- 백그라운드 워커 (UI 멈춤 방지) ---
class ConnectionWorker(QObject):
    """'PLC 연결을 담당하는 워커"""
    connection_result = pyqtSignal(bool, str) # (성공 여부, 상태 메시지)
    finished = pyqtSignal()

    def __init__(self, controller: ControllerType):
        super().__init__()
        self.controller = controller

    @pyqtSlot()
    def run(self):
        try:
            # 컨트롤러의 connect_plc 메서드 호출 (실제/Mock 공통)
            success, status_msg = self.controller.connect_plc()
            self.connection_result.emit(success, status_msg)
        finally:
            # 성공/실패 여부와 관계없이 항상 finished 시그널을 방출하여 스레드 정리
            self.finished.emit()



class CommandWorker(QObject):
    """좌표 전송을 담당하는 워커 (라이브/데모 모드 공용)"""
    log_message = pyqtSignal(str)
    command_finished = pyqtSignal(str) # (결과 메시지)
    finished = pyqtSignal()

    def __init__(self, controller: ControllerType, coords: list):
        super().__init__()
        self.controller = controller
        self.coords = coords

    @pyqtSlot()
    def run(self):
        try:
            self.log_message.emit("좌표 전송 시작...(실제 PLC쓰기)")
            # 컨트롤러의 execute_command 메서드 호출 (실제든 Mock이든)
            success, status_msg = self.controller.execute_command(*self.coords)
            
            if not success:
                self.log_message.emit(f"전송 실패: {status_msg}")
            
            self.command_finished.emit(status_msg)
        finally:
            # 성공/실패 여부와 관계없이 항상 finished 시그널을 방출하여 스레드 정리
            self.finished.emit()



class FileLoadWorker(QObject):
    """파일 읽기 담당 워커"""
    file_loaded = pyqtSignal(bool, str, dict)  # (성공 여부, 메시지, 읽은 데이터)
    finished = pyqtSignal()

    def __init__(self, file_path: Path, file_type: str):
        super().__init__()
        self.file_path = file_path
        self.file_type = file_type
        self.parser_manager = SequenceParserManager()

    @pyqtSlot()
    def run(self):

        # print("워커의 run 메서드 호출됨: FileLoadWorker")
        # print(f"파일경로: {self.file_path}\n파일타입: {self.file_type}")

        # 사용자가 선택한 파일의 종류가 무엇인지는 이미 서비스 레이어에서 찾아냈다
        try:

            # 파일 경로에 맞는 파서 객체를 찾는다.
            parser = self.parser_manager.find_parser(self.file_path)

            if self.file_type == 'txt':
                # 파일 내용을 읽어온다.
                raw_text = load_text(self.file_path)
                # 찾아낸 파서로 데이터를 파싱한다.
                parsed_data = parser.parse(raw_text)

            elif self.file_type == 'csv':
                # 파일 내용을 읽어온다.
                raw_csv_data = load_csv(self.file_path)
                # 찾아낸 파서로 데이터를 파싱한다.
                parsed_data = parser.parse(raw_csv_data)

            else:
                # 지원하지 않는 파일 타입에 대한 예외 처리
                raise ValueError(f"지원하지 않는 파일 형식입니다: {self.file_type}")
            
            debugpy.breakpoint

            # 파싱된 데이터를 emit
            # print(f"원본->파서 통과한 값:\n{parsed_data}\n타입:{type(parsed_data)}",)
            self.file_loaded.emit(True, f"파일 로드 및 파싱 성공: {self.file_path.name}", parsed_data)

        except Exception as e:
            self.file_loaded.emit(False, f"파일 로드 실패: {e}", {})
        finally:
            self.finished.emit()



class RobotControlWorker(QObject):
    """
    로봇 제어 명령(시작/일시정지/재개/완전정지)을 수행하는 워커
    Model의 메서드들이 time.sleep()을 포함하므로 별도 스레드에서 실행
    """
    control_result = pyqtSignal(bool, str) # (성공여부, 메시지)
    finished = pyqtSignal()

    def __init__(self, controller: ControllerType, command_type: str):
        super().__init__()
        self.controller = controller
        self.command_type = command_type # 'START', 'PAUSE', 'RESUME', 'STOP'

    @pyqtSlot()
    def run(self):
        success = False
        msg = ""

        try:
            if self.command_type == 'START':
                # 초기 시작: RSR2 펄스 + DI181 ON
                success, msg = self.controller.start_process_loop()
            
            elif self.command_type == 'PAUSE':
                # 일시 정지: Cycle Stop 펄스
                success, msg = self.controller.send_cycle_stop()
            
            elif self.command_type == 'RESUME':
                # 다시 시작: Cycle Start 펄스
                success, msg = self.controller.send_cycle_start()
            
            elif self.command_type == 'STOP':
                # 완전 정지: DI181 OFF
                success, msg = self.controller.set_loop_signal(False)
            
            else:
                success, msg = False, f"알 수 없는 명령 타입: {self.command_type}"

            # 결과 전송
            self.control_result.emit(success, msg)

        except Exception as e:
            self.control_result.emit(False, f"제어 명령 수행 중 오류: {e}")
        
        finally:
            self.finished.emit()