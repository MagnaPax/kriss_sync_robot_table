from PyQt6.QtWidgets import QFrame, QVBoxLayout, QLabel


class CenterPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("center_panel")
        self.setFrameShape(QFrame.Shape.StyledPanel)    # OS/Qt 테마 스타일을 따라감
        self.setFrameShadow(QFrame.Shadow.Sunken)       # 음영이 아래쪽에 있어, 패널이 눌려 보임

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Center Panel", self))