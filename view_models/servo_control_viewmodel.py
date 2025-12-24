# view_models/servo_control_viewmodel.py
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from core.event_bus import EVENT_BUS
from communication.servo_adapter import ServoAdapter



class ServoControlViewModel(QObject):
    """서보모터 제어용 뷰모델"""
    def __init__(self, servo_adapter: ServoAdapter):
        super().__init__()
        self.servo = servo_adapter