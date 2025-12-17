from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QGroupBox, QFrame
from ui.widgets.waypoints_widget import WaypointsWidget
from ui.widgets.task_manager_widget import TaskManagerWidget
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from view_models.main_window_viewmodel import MainViewModel


class RightPanel(QFrame):
    def __init__(self, view_model: "MainViewModel", parent=None):
        super().__init__(parent)

        # 뷰모델 저장 (나중에 자식 위젯들이 데이터 필요할 때 여기서 꺼내 줌)
        self.vm = view_model

        self.setObjectName("right_panel")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Sunken)

        # 수직 레이아웃
        layout = QVBoxLayout(self)

        # 위젯들
        waypoints = WaypointsWidget()
        progress_state = QFrame()
        task_manager = TaskManagerWidget()
        log_robot_movement = QGroupBox("Robot Movement Log")
        log_batch_completion = QGroupBox("Batch Completion Log")

        # MainViewModel 안에 있는 'task_manager_vm'만 꺼내서 전달
        task_manager.set_view_model(view_model.task_manager_vm)

        # 제일 밑 로그 2개를 위한 수평 레이아웃
        logs_layout = QHBoxLayout()
        logs_layout.addWidget(log_robot_movement)
        logs_layout.addWidget(log_batch_completion)


        progress_state.setStyleSheet("color: black; border: 1px solid black;")
        log_robot_movement.setStyleSheet("color: black; border: 1px solid yellow;")
        log_batch_completion.setStyleSheet("color: black; border: 1px solid yellow;")


        # 위젯 & 레이아웃 추가
        layout.addWidget(waypoints,  10)
        layout.addWidget(progress_state,    1)
        layout.addWidget(task_manager,      2)
        layout.addLayout(logs_layout,       7)


