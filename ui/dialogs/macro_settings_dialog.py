# ui/dialogs/macro_settings_dialog.py
import sys
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QGroupBox,
    QFormLayout,
    QLineEdit,
    QDoubleSpinBox,
    QPushButton,
    QLabel,
    QVBoxLayout,
    QGroupBox,
    QWidget
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from typing import Dict, Any, Tuple



class MacroSettingsDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        # 각 매크로의 UI 위젯들을 저장할 딕셔너리
        self.macro_widgets: Dict[str, Dict[str, QWidget]] = {}

        self._init_ui()


    def _init_ui(self):
        self.setWindowTitle("Macro Settings")
        self.setWindowIcon(QIcon("resources/icons/kriss.gif"))
        self.setModal(True)             # Dialog 를 닫을 때까지 부모 윈도우의 조작을 막는다
        self.setMinimumWidth(1200)

        # --- 메인 레이아웃(가로 정렬) --- #
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        # --- 매크로 그룹 박스 만들기 --- #
        group_box_macro_1, widget_1 = self._create_macro_groupbox("Macro 1")
        group_box_macro_2, widget_2 = self._create_macro_groupbox("Macro 2")
        group_box_macro_3, widget_3 = self._create_macro_groupbox("Macro 3")
        group_box_macro_4, widget_4 = self._create_macro_groupbox("Macro 4")

        # --- 메인 레이아웃에 매크로 그룹 박스 추가 --- #
        main_layout.addWidget(group_box_macro_1)
        main_layout.addWidget(group_box_macro_2)
        main_layout.addWidget(group_box_macro_3)
        main_layout.addWidget(group_box_macro_4)

        # --- 그룹 박스의 내부 위젯들 저장 --- #
        self.macro_widgets["Macro_1"] = widget_1
        self.macro_widgets["Macro_2"] = widget_2
        self.macro_widgets["Macro_3"] = widget_3
        self.macro_widgets["Macro_4"] = widget_4


    def _create_macro_groupbox(self, macro_id: str) -> Tuple[QGroupBox, Dict[str, QWidget]]:
            """
            하나의 매크로 편집용 QGroupBox를 생성합니다.
            (요구사항: QGroupBox, 이름 입력, X-R 좌표, 저장 버튼)
            """
            
            # 1. QGroupBox 생성 (요구사항: "매크로 이름이 QGroupBox로 표시")
            group_box = QGroupBox(macro_id)
            
            # 2. GroupBox 내부의 메인 수직 레이아웃
            # (QFormLayout + Save Button을 수직으로 쌓기 위함)
            group_v_layout = QVBoxLayout(group_box)

            # 3. 좌표 입력을 위한 폼 레이아웃
            form_layout = QFormLayout()

            # 4. 매크로 이름 입력 (요구사항: "키보드 입력")
            name_input = QLineEdit()
            form_layout.addRow(QLabel("Name:"), name_input)

            # 5. X, Y, Z, W, P, R 값 입력 (요구사항: "음수 양수 숫자")
            coord_inputs: Dict[str, QDoubleSpinBox] = {}
            
            # X, Y, Z (mm)
            for axis in ['X', 'Y', 'Z']:
                spin_box = QDoubleSpinBox()
                spin_box.setRange(-99999.0, 99999.0)
                spin_box.setDecimals(3)
                spin_box.setSuffix(" mm")
                coord_inputs[axis] = spin_box
                form_layout.addRow(QLabel(f"{axis}:"), spin_box)

            # W, P, R (deg)
            for axis in ['W', 'P', 'R']:
                spin_box = QDoubleSpinBox()
                spin_box.setRange(-360.0, 360.0)
                spin_box.setDecimals(3)
                spin_box.setSuffix(" °")
                coord_inputs[axis] = spin_box
                form_layout.addRow(QLabel(f"{axis}:"), spin_box)

            # 6. 저장 버튼 (요구사항: "저장 버튼이 있다.")
            save_btn = QPushButton("Save")
            
            # 7. GroupBox 레이아웃에 폼과 버튼 추가
            group_v_layout.addLayout(form_layout)
            group_v_layout.addStretch(1) # 폼과 버튼 사이 공간
            group_v_layout.addWidget(save_btn, 0, Qt.AlignmentFlag.AlignRight) # 오른쪽 정렬

            # 나중에 접근할 수 있도록 위젯들을 딕셔너리로 묶음
            widgets = {
                'name_input': name_input,
                'save_btn': save_btn,
                **coord_inputs # X, Y, Z... SpinBox들을 딕셔너리에 병합
            }
            
            return group_box, widgets





if __name__ == '__main__':
    import sys
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    dialog = MacroSettingsDialog()
    dialog.exec()   # Modal로 실행
    sys.exit(0)
    