# view_models/sequence_worker.py
"""
ViewModel을 대신해서 Model의 작업을 대신 호출한다
"""
from PyQt6.QtCore import QObject, pyqtSignal
from ..models.sequence_model import SequenceModel





class SequenceWorker(QObject):
    """
    백그라운드 스레드에서 Model 호출

    ViewModel은 나에게 일을 시키고 UI 스레드로 복귀 - 앱 멈춤 없다
    """

    # ViewModel이 구독할 시그널(실제 아님. 예제 시그널)
    completed = pyqtSignal(str)
    failed = pyqtSignal(str)


    def __init__(self):
        super().__init__()

        # Model 인스턴스
        self.model = SequenceModel()



    def run(self):
        try:
            # 시간이 오래 걸리는 Model의 작업을 대신 호출
            result = self.model.
            # ViewModel에게 작업 완료 보고
            self.completed.emit(result)
            pass
        except Exception as e:
            pass