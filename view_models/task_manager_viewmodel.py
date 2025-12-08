# view_models/task_manager_viewmodel.py
from PyQt6.QtCore import Qt, QObject, pyqtSignal, pyqtSlot
from pathlib import Path
from services.sequence_service import SequenceService
from core.event_bus import EVENT_BUS



"""
- UI 의 상태 관리
- UI 의 이벤트 처리
- 명령 및 로직 요청
"""



class TaskManagerViewModel(QObject):

    # View에게 상태를 알리는 시그널
    sequence_data_loaded_complete = pyqtSignal(dict)     # 파일 읽기 성공
    sequence_data_loaded_failed = pyqtSignal(str)        # 파일 읽기 실패


    def __init__(self, sequence_service: SequenceService):
        super().__init__()

        # 로그 메세지의 말머리(로그 발생 위치 표시)
        self._log_prefix = f"[{self.__class__.__name__}]"

        self._sequence_service = sequence_service




    def load_sequence_data(self, file_path: Path):
        """시퀀스 파일의 데이터 읽어서 뷰에게 전달"""

        EVENT_BUS.ui_log_message.emit(f"{self._log_prefix} 시퀀스 데이터 읽기 시작", "DEBUG")

        # Service에게 시킴
        sequence_data = self._sequence_service.load_sequence_file(file_path)

        """
        if sequence_data:
            # 성공
            self.sequence_data_loaded_complete.emit(sequence_data)
            EVENT_BUS.ui_log_message.emit(f"{self._log_prefix} 시퀀스 데이터 읽기 성공", "INFO")

        else:
            # 실패
            self.sequence_data_loaded_failed.emit(f"시퀀스 데이터 읽기 실패")
            EVENT_BUS.ui_log_message.emit(f"{self._log_prefix} 시퀀스 데이터가 비어있거나 읽기 실패", "ERROR")
        """