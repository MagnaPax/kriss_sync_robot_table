# view_models/sequence_viewmodel.py
"""
View  ←→  ViewModel ↔ [Worker] ↔ Model

시퀀스 뷰모델 (Presentation Logic)

Worker에게 Model 호출 작업을 지시한 뒤 바로 UI 스레드로 복귀 - 앱 멈춤 없음

"""
from PyQt6.QtCore import QObject, pyqtSignal



class SequenceViewModel(QObject):
    """
    시퀀스 뷰모델 (Presentation Logic)
    """

    # View가 구독할 시그널(실제 아님. 예제 시그널)
    state_changed = pyqtSignal(str)
    progress_changed = pyqtSignal(float)


    def __init__(self):
        pass

    def start_load_task(self):
        """View의 LOAD 버튼 요구 처리"""
        pass

    def start_save_batch_task(self):
        """View의 SAVE BATCH 버튼 요구 처리"""
        pass
