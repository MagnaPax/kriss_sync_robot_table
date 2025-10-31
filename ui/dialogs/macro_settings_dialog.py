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
from typing import Dict, Any, Tuple, cast



class MacroSettingsDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        # 각 매크로의 위젯들을 저장할 딕셔너리
        self.macro_widgets: Dict[str, Dict[str, QWidget]] = {}

        self._init_ui()

        # 사용자 입력이 끝난 뒤(self._init_ui())에 저장 버튼 처리
        self._connect_save_signals()


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
        group_box_macro_1, macro_widgets_1 = self._create_macro_groupbox("Macro 1")
        group_box_macro_2, macro_widgets_2 = self._create_macro_groupbox("Macro 2")
        group_box_macro_3, macro_widgets_3 = self._create_macro_groupbox("Macro 3")
        group_box_macro_4, macro_widgets_4 = self._create_macro_groupbox("Macro 4")

        # --- 매크로 그룹 박스를 메인 레이아웃에 추가 --- #
        main_layout.addWidget(group_box_macro_1)
        main_layout.addWidget(group_box_macro_2)
        main_layout.addWidget(group_box_macro_3)
        main_layout.addWidget(group_box_macro_4)

        # --- 매크로 그룹 박스 안에 있는 위젯들 저장 --- #
        self.macro_widgets["Macro_1"] = macro_widgets_1
        self.macro_widgets["Macro_2"] = macro_widgets_2
        self.macro_widgets["Macro_3"] = macro_widgets_3
        self.macro_widgets["Macro_4"] = macro_widgets_4


    def _create_macro_groupbox(self, macro_id: str) -> Tuple[QGroupBox, Dict[str, QWidget]]:
        """
        매크로 편집용 QGroupBox 생성

        반환: 만들어진 그룹박스 객체, 그룹 박스 안에 들어있는 위젯을 담은 딕셔너리
        """
        
        # QGroupBox 컨테이너 생성
        # 메인 레이아웃을 담는다
        group_box = QGroupBox(macro_id)
        
        # 메인 레이아웃(세로 정렬)
        group_v_layout = QVBoxLayout(group_box)

        # 좌표 입력을 위한 폼 레이아웃
        # 라벨-입력 형식의 위젯
        form_layout = QFormLayout()

        # 레이블로 사용할 매크로 명칭 입력 - 사용자 키보드 입력
        name_input = QLineEdit()
        form_layout.addRow(QLabel("Name:"), name_input)

        # 좌표 입력 필드 생성
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

        # 저장 버튼
        save_btn = QPushButton("Save")
        
        # 메인 레이아웃에 폼과 버튼 쌓기
        group_v_layout.addLayout(form_layout)
        group_v_layout.addStretch(1)    # 폼과 버튼 사이 공간
        group_v_layout.addWidget(save_btn, 0, Qt.AlignmentFlag.AlignRight) # 오른쪽 정렬

        # 내부 위젯 딕셔너리 구성
        # 이 딕셔너리를 통해 코드 외부에서도 쉽게 접근 가능
        widgets = {
            'name_input': name_input,
            'save_btn': save_btn,
            **coord_inputs # X, Y, Z... SpinBox들을 딕셔너리에 병합
        }
        
        return group_box, widgets


    def _connect_save_signals(self):
        """
        모든 매크로 그룹에 있는 Save 버튼의 시그널과 슬롯 연결
        -> 저장 버튼이 눌리면 어떤 일을 할 지 정의
        """

        # 매크로 그룹의 위젯들을 저장한 macro_widgets 딕셔너리 사용
        # 1. 매크로 아이디에 해당하는 위젯 딕셔너리에서 저장 버튼 객체 꺼냄
        # 2. 버튼이 클릭될 때 실행할 함수 연결
        #   2-1. clicked: 시그널. QPushButton 객체가 클릭될 때 emit 된다
        #   2-2. connect: 슬롯 연결 - 시그널이 발생했을 때 실행할 함수(슬롯)
        for macro_id, widgets in self.macro_widgets.items():
            save_btn = cast(QPushButton, widgets['save_btn'])
            # QPushButton 가 상속받은 QAbstractButton 의 시그널 `clicked(bool checked = false)` 처리
            save_btn.clicked.connect(
                lambda checked=False: self._on_save(macro_id)
            )


    def _on_save(self, macro_id: str):
        """
        특정 매크로 그룹(파라미터 번호)의 저장 버튼이 클릭됐을 때 실행되는 함수
        """

        # 해당 매크로 그룹 박스 안에 있는 위젯들
        widgets = self.macro_widgets[macro_id]

        # 이름 추출
        name = cast(QLineEdit, widgets['name_input']).text().strip()

        # 축 별 값 추출
        x = cast(QDoubleSpinBox, widgets['X']).value()
        y = cast(QDoubleSpinBox, widgets['Y']).value()
        z = cast(QDoubleSpinBox, widgets['Z']).value()
        w = cast(QDoubleSpinBox, widgets['W']).value()
        p = cast(QDoubleSpinBox, widgets['P']).value()
        r = cast(QDoubleSpinBox, widgets['R']).value()

        # 내부 저장을 위해 딕셔너리로 합치기
        data_macro: dict[str, Any] = {
            'macro_id': macro_id,
            'name': name,
            'x': x, 'y': y, 'z': z,
            'w': w, 'p': p, 'r': r
        }

        # -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-= #
        #
        #   data_macro 을 파일로 내보내야 됨
        #
        # -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-= #


        print(f"The data of {macro_id} are saved:\n", data_macro)




if __name__ == '__main__':
    import sys
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    dialog = MacroSettingsDialog()
    dialog.exec()   # Modal로 실행
    sys.exit(0)
    