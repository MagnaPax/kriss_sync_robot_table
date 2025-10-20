from PyQt6.QtWidgets import QFrame, QVBoxLayout, QLabel


class LeftPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("left_panel")
        self.setFrameShape(QFrame.Shape.StyledPanel)    # 프레임의 기본 형태 설정
        self.setFrameShadow(QFrame.Shadow.Sunken)       # 프레임의 입체감(빛, 음영) 설정

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Left Panel", self))
