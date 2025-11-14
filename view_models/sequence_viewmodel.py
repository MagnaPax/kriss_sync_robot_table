# view_models/sequence_viewmodel.py
"""
View  ←→  ViewModel  →  Model

시퀀스 뷰모델 (Presentation Logic)
"""
from PyQt6.QtCore import QObject, pyqtSignal

class SequenceViewModel(QObject):

    current_step_changed = pyqtSignal(int)
    progress_changed = pyqtSignal(float)
    step_highlight_requested = pyqtSignal(int)  # 강조 표시 되도록 요청
    sequence_completed = pyqtSignal()
    
    def __init__(self):
        pass

    def _connect_events(self):
        pass

    def load_sequence(self):
        pass

    def start_sequence(self):
        pass

    def execute_next_step(self):
        pass
