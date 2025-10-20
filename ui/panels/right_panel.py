from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel


class RightPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("right_panel")
        layout = QVBoxLayout(self)
        layout.addWidget(self)