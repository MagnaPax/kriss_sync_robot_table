# demo_worker.py

from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from fanuc_logic import FanucController
from .demo_plc_mock_model import MockFanucController
from .file_handler import load_text, load_csv
from .demo_logger import logger
from .sequence_parser import parse_txt_to_sequence, parse_csv_to_sequence




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
    """파일 로드를 담당하는 워커"""
    file_loaded = pyqtSignal(bool, str, dict)  # (성공 여부, 메시지, 읽은 데이터)
    finished = pyqtSignal()

    def __init__(self, file_path: Path, file_type: str):
        super().__init__()
        self.file_path = file_path
        self.file_type = file_type

    @pyqtSlot()
    def run(self):

        # print("워커의 run 메서드 호출됨: FileLoadWorker")
        # print(f"파일경로: {self.file_path}\n파일타입: {self.file_type}")

        try:
            if self.file_type == 'txt':
                # 파일 전체를 하나의 문자열로 읽어온다.
                raw_text = load_text(self.file_path)

                # 문자열을 줄 단위 리스트로 변환한다.
                lines = raw_text.splitlines()

                # 변환된 리스트를 파서에 전달하고, 그 결과를 저장한다.
                parsed_data = parse_txt_to_sequence(lines)

            elif self.file_type == 'csv':
                raw_csv_data = load_csv(self.file_path)
                parsed_data = parse_csv_to_sequence(raw_csv_data)

            else:
                # 지원하지 않는 파일 타입에 대한 예외 처리
                raise ValueError(f"지원하지 않는 파일 형식입니다: {self.file_type}")
            
            # print(f"원본->파서 통과한 값:\n{parsed_data}\n타입:{type(parsed_data)}",)
            self.file_loaded.emit(True, f"파일 로드 성공: {self.file_path.name}", parsed_data)

        except Exception as e:
            self.file_loaded.emit(False, f"파일 로드 실패: {e}", [])
        finally:
            self.finished.emit()