from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel


class LeftPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("left_panel")
        layout = QVBoxLayout(self)
        layout.addWidget(self)