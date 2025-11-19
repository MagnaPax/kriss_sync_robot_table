# view_models/target_position_viewmodel_worker.py
"""
비서(Worker)

ViewModel 대신 Model의 동기화 작업을 호출한다
Model을 호출한 뒤 작업이 끝나면 결과를 방출(emit)한다 - ViewModel이 구독해서 받는다

View → ViewModel → (Worker) → Model
"""

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from models.position_model import PositionModel as Model



class TargetPositionViewModelWorker(QObject):

    # 노출할 시그널 (ViewModel의 메서드가 구독)
    task_completed = pyqtSignal(str)
    task_failed = pyqtSignal(str)
    finished = pyqtSignal()
    
    
    def __init__(self, model: Model):
        super().__init__()
        self.model = model

    @pyqtSlot()
    def run(self):
        """Model의 작업을 대신 호출"""
        
        try:
            result = self.model.do_task()
            self.task_completed.emit(f"작업 완료: {result}")
        except Exception as e:
            self.task_failed.emit(str(e))
        finally:
            # 성공/실패 여부와 관계없이 항상 finished 시그널을 방출하여 스레드 정리
            self.finished.emit()
