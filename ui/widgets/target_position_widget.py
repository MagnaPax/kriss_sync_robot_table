# ui/widgets/target_position_widget.py
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QVBoxLayout, QGroupBox, QLabel

from ui.widgets.base_widget import BaseWidget



    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
