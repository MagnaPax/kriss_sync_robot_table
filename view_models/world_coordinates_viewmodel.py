# view_models/world_coordinates_viewmodel.py
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from core.event_bus import EVENT_BUS
from models.fanuc_pose_model import FANUCPose

class WorldCoordinatesViewModel(QObject):

    # 로컬 시그널 - View 가 구독
    robot_pose_changed = pyqtSignal(FANUCPose)  # 로봇의 world coordinates 값


    def __init__(self):
        super().__init__()


        # EventBus(전역) -> 내 로컬 시그널로 바로 재방송
        EVENT_BUS.control.robot_current_pose.connect(self.robot_pose_changed.emit)