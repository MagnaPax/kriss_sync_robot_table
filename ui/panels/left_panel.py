from PyQt6.QtWidgets import QFrame, QVBoxLayout, QGroupBox


class LeftPanel(QFrame):
    def __init__(self, parent=None):    # 부모가 없을 수도 있다(독립적 테스트 가능)
        super().__init__(parent)
        self.setObjectName("left_panel")
        self.setFrameShape(QFrame.Shape.StyledPanel)    # 프레임의 기본 형태 설정
        self.setFrameShadow(QFrame.Shadow.Sunken)       # 프레임의 입체감(빛, 음영) 설정

        layout = QVBoxLayout(self)

        ci_panel = QFrame()
        turntable_group = QGroupBox("Turntable")
        currnet_state = QGroupBox("Current State")
        world_position = QGroupBox("World Position")

        turntable_group.setStyleSheet("color: black; border: 1px solid red;")
        currnet_state.setStyleSheet("color: black; border: 1px solid black;")
        world_position.setStyleSheet("color: black; border: 1px solid green;")

        layout.addWidget(ci_panel,          stretch=1)  # 1/5 -> 20%
        layout.addWidget(turntable_group,   stretch=2)  # 2/5 -> 40%
        layout.addWidget(currnet_state,     stretch=1)  # 1/5 -> 20%
        layout.addWidget(world_position,    stretch=1)  # 1/5 -> 20%
