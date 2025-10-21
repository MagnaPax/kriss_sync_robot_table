from PyQt6.QtWidgets import QFrame, QVBoxLayout, QLabel, QGroupBox


class CenterPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("center_panel")
        self.setFrameShape(QFrame.Shape.StyledPanel)    # OS/Qt 테마 스타일을 따라감
        self.setFrameShadow(QFrame.Shadow.Sunken)       # 음영이 아래쪽에 있어, 패널이 눌려 보임

        layout = QVBoxLayout(self)

        connection_status = QGroupBox("Connection Status")
        robot_position = QGroupBox("Robot Position")
        target_position = QGroupBox("Target Position")
        user_position = QGroupBox("User Position")



        connection_status.setStyleSheet("color: black; border: 1px solid red;")
        robot_position.setStyleSheet("color: black; border: 1px solid black;")
        target_position.setStyleSheet("color: black; border: 1px solid green;")
        user_position.setStyleSheet("color: black; border: 1px solid green;")

        layout.addWidget(connection_status, stretch=1)
        layout.addWidget(robot_position,    stretch=2)
        layout.addWidget(target_position,   stretch=1)
        layout.addWidget(user_position,     stretch=1)


