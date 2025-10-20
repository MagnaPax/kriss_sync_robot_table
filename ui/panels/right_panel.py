from PyQt6.QtWidgets import QFrame, QVBoxLayout, QLabel


class RightPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("right_panel")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Sunken)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Right Panel", self))
