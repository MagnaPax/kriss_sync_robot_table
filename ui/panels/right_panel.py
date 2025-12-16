from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QGroupBox, QFrame
from ui.widgets.waypoints_widget import WaypointsWidget



class RightPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("right_panel")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Sunken)

        # 수직 레이아웃
        layout = QVBoxLayout(self)

        # 위젯들
        waypoints = WaypointsWidget()
        progress_state = QFrame()
        task_manager = QGroupBox("Task Manager")
        log_robot_movement = QGroupBox("Robot Movement Log")
        log_batch_completion = QGroupBox("Batch Completion Log")

        # 제일 밑 로그 2개를 위한 수평 레이아웃
        logs_layout = QHBoxLayout()
        logs_layout.addWidget(log_robot_movement)
        logs_layout.addWidget(log_batch_completion)


        progress_state.setStyleSheet("color: black; border: 1px solid black;")
        task_manager.setStyleSheet("color: black; border: 1px solid green;")
        log_robot_movement.setStyleSheet("color: black; border: 1px solid yellow;")
        log_batch_completion.setStyleSheet("color: black; border: 1px solid yellow;")


        # 위젯 & 레이아웃 추가
        layout.addWidget(waypoints,  10)
        layout.addWidget(progress_state,    1)
        layout.addWidget(task_manager,      2)
        layout.addLayout(logs_layout,       7)


