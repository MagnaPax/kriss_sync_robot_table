# view_models/sequence_worker.py
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal
from models.sequence_model import SequenceModel
from utils.file_handler import load_text, load_csv




class SequenceWorker(QObject):
    """
    백그라운드 스레드에서 Model 호출

    ViewModel은 나에게 일을 시키고 UI 스레드로 복귀 - 앱 멈춤 없다
    """

    # 로컬 시그널 (Service가 구독)
    result = pyqtSignal(bool, str, list)    # 작업 결과 알림(성공여부, 메시지, 읽은 데이터)
    finished = pyqtSignal()                 # 작업 종료 알림


    def __init__(self, file_path: Path):
        super().__init__()

        self._log_prefix = f"[{self.__class__.__name__}]"

        self._file_path = file_path

        # Model 인스턴스
        self.model = SequenceModel()


    def run(self):
        """시간이 오래 걸리는 비동기 작업(시퀀스 파일 읽기)을 수행"""

        sequence_data = None

        try:
            sequence_data = load_csv(self._file_path)

            print(f"{self._file_path}")

            # 작업 결과 보고
            # argument 순서: 성공여부, 메시지, 읽은 데이터
            self.result.emit(True, f"{self._log_prefix} 파일({self._file_path}) 읽기 완료", sequence_data)

        except Exception as e:
            # 작업 결과 보고
            self.result.emit(False, f"{self._log_prefix} 파일({self._file_path}) 읽기 실패: {e}", sequence_data)

        finally:
            # 작업 종료 알림
            self.finished.emit()