from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel


class CenterPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("center_panel")
        layout = QVBoxLayout(self)
        layout.addWidget(self)