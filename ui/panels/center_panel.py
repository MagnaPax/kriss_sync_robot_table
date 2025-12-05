from PyQt6.QtWidgets import QFrame, QVBoxLayout, QGroupBox

from ui.widgets.robot_position_widget import RobotPositionWidget
from ui.widgets.target_position_widget import TargetPositionWidget
from typing import TYPE_CHECKING


# 순환 참조 방지용
if TYPE_CHECKING:
    from view_models.main_window_viewmodel import MainViewModel




class CenterPanel(QFrame):
    def __init__(self, viewmodel: "MainViewModel", parent=None):
        super().__init__(parent)

        self.vm = viewmodel  # 메인 뷰모델 저장 (필요 시 사용)

        self.setObjectName("center_panel")
        self.setFrameShape(QFrame.Shape.StyledPanel)    # OS/Qt 테마 스타일을 따라감
        self.setFrameShadow(QFrame.Shadow.Sunken)       # 음영이 아래쪽에 있어, 패널이 눌려 보임

        layout = QVBoxLayout(self)

        connection_status = QGroupBox("Connection Status")
        robot_position = RobotPositionWidget()
        # MainViewModel에서 TargetPositionViewModel을 꺼내서 주입
        target_position = TargetPositionWidget(self.vm.target_position_vm)
        user_position = QGroupBox("User Position")



        # 위젯 배치를 위한 임시 스타일 표시
        # TODO: 모든 위젯들 완성 후 삭제해야 된다
        #       styles/stylesheet.qss 보다 아래 코드가 우선순위가 더 높다
        connection_status.setStyleSheet("color: black; border: 1px solid red;")
        robot_position.setStyleSheet("color: black; border: 1px solid black;")
        user_position.setStyleSheet("color: black; border: 1px solid green;")

        layout.addWidget(connection_status, stretch=1)
        layout.addWidget(robot_position,    stretch=2)
        layout.addWidget(target_position,   stretch=1)
        layout.addWidget(user_position,     stretch=1)


