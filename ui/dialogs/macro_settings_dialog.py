# ui/dialogs/macro_settings_dialog.py
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QGroupBox,
    QFormLayout,
    QLineEdit,
    QDoubleSpinBox,
    QPushButton
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon




class MacroSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Macro Settings")
        self.setWindowIcon(QIcon("resources/icons/kriss.gif"))
        self.setModal(True)
        self.resize(900, 400)  # 넓은 화면

        self.show()





if __name__ == '__main__':
    import sys
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    dialog = MacroSettingsDialog()
    sys.exit(app.exec())
    