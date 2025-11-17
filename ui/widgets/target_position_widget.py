# ui/widgets/target_position_widget.py
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QVBoxLayout, 
    QGroupBox, 
    QLabel, 
    QFrame, 
    QHBoxLayout, 
    QFormLayout, 
    QLineEdit, 
    QDoubleSpinBox,
    QGridLayout,
    QPushButton
)
from typing import Dict

from ui.widgets.base_widget import BaseWidget



class TargetPositionWidget(BaseWidget):
    """
     로봇팔, 턴테이블의 이동 명령과 매크로를 관리하는 위젯

     기능:
        - 좌표 입력(X,Y,Z,W,P,R)
        - 'Edit Macro' 버튼으로 매크로 설정 모달(MacroSettingsDialog) 열기
        - 매크로 버튼(사용자가 입력한 매크로 제목)을 누르면 저장된 값 불러오기
        - 'GoTo' 버튼 클릭 시 `goto_requested` 시그널 발생
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        self.setObjectName("target_position_widget")
        self._configure_base_layout()


    def _configure_base_layout(self):
        """
        전체 레이아웃 구성
        """
        ##########################
        # --- 기본 형태 설정 --- #
        ##########################

        # 모든 부속 위젯을 담을 그룹박스 생성
        base_group_box = QGroupBox("Target Position")
        base_group_box.setStyleSheet("QGroupBox { background-color: grey; }") # 개발용 임시 배경 스타일

        # 메인 레이아웃(세로 정렬)
        # 이 레이아웃이 전체 위젯의 크기를 관리한다
        main_layout = QVBoxLayout(self)  # 부모위젯(TargetPositionWidget)에 QVBoxLayout을 붙인다
        main_layout.addWidget(base_group_box)
        main_layout.setContentsMargins(0, 0, 0, 0)      # 레이아웃 내부 여백 제거


        ############################
        # --- 부속 위젯들 배치 --- #
        ############################
        # --- 상단 --- #
        # --- Edit Macro 영역 --- #
        section_edit_macro = QFrame()
        section_edit_macro.setObjectName("section_edit_macro")
        section_edit_macro.setStyleSheet("QFrame { background-color: blue; }")  # 개발용 임시 배경

        layout_edit_macro = QHBoxLayout(section_edit_macro)
        layout_edit_macro.setContentsMargins(0, 0, 0, 0)
        layout_edit_macro.setSpacing(0)
        layout_edit_macro.addStretch(1)


        # --- 중단 --- #
        # --- 사용자 입력 영역 --- #
        section_line_edit = QFrame()
        section_line_edit.setObjectName("section_line_edit")
        section_line_edit.setStyleSheet("QFrame { background-color: green; }")  # 개발용 임시 배경

        layout_line_edit = QHBoxLayout(section_line_edit)
        layout_line_edit.setContentsMargins(0, 0, 0, 0)
        layout_line_edit.setSpacing(0)
        layout_line_edit.addStretch(1)

        # --- 매크로 버튼 영역 --- #
        section_macro_buttons = QFrame()
        section_macro_buttons.setObjectName("section_macro_buttons")
        section_macro_buttons.setStyleSheet("QFrame { background-color: yellow; }")  # 개발용 임시 배경

        laytou_macro_buttons = QGridLayout(section_macro_buttons)
        laytou_macro_buttons.setContentsMargins(0, 0, 0, 0)
        laytou_macro_buttons.setSpacing(0)


        # --- 하단 --- #
        # --- Go To 영역 --- #
        section_go_to = QFrame()
        section_go_to.setObjectName("section_go_to")
        section_go_to.setStyleSheet("QFrame { background-color: orange; }")  # 개발용 임시 배경

        layout_go_to = QHBoxLayout(section_go_to)
        layout_go_to.setContentsMargins(0, 0, 0, 0)
        layout_go_to.setSpacing(0)
        layout_go_to.addStretch(1)        


        ############################
        # --- 부속 위젯들 합체 --- #
        ############################
        widgets_layout = QVBoxLayout(base_group_box)
        widgets_layout.addWidget(section_edit_macro)
        widgets_layout.addWidget(section_line_edit)
        widgets_layout.addWidget(section_macro_buttons)
        widgets_layout.addWidget(section_go_to)

        base_group_box.setLayout(widgets_layout)


    ##############################
    # --- 부속 위젯들 만들기 --- #
    ##############################
    
    # --- 버튼 만들기 --- #
    def _create_button(self, title: str, type: str) -> QPushButton:
        button = QPushButton(title.upper())
        button.setObjectName(title)
        button.setProperty("type", type)
        return button

    def _create_edit_macro_button(self) -> QPushButton:
        """ Edit Macro 버튼 생성 """
        return self._create_button(title="Edit Macro", type="special")
    
    def _create_macro_button(self, title: str) -> QPushButton:
        """ 
        매크로 버튼 생성

        버튼에 표시되는 제목은 사용자가 지정한 이름
        """
        return self._create_button(title=title, type="general")
    
    def _create_goto_button(self) -> QPushButton:
        """ GoTo 버튼 생성 """
        return self._create_button(title="Go To", type="special")







    ###########################
    # --- 시그널 ➡️ 슬릿 --- #
    ###########################

    def _bind_edit_macro_button_event():
        """
        'Edit Macro' 버튼이 눌리면 어떤 일을 할 지 정의

        시그널 연결
        """

    def _handle_edit_macro_button_clicked():
        """
        'Edit Macro' 버튼이 클릭되었을 때 실행할 함수

        MacroSettingsDialog 열기
        """



    def _create_line_edit():
        """
        사용자 입력 위젯 반환

        로봇(X,Y,Z) -> mm
        턴테이블(W,P,R) -> deg
        """

        # 레이아웃을 담는다
        layout_container = QFrame()

        # 레이아웃 설정
        layout = QHBoxLayout(layout_container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 좌표 입력 레이아웃(이름표-입력 형식)
        form_layout = QFormLayout()

        # 이름표 명칭
        for title in ["X", "Y", "Z"]:
            form_layout.addRow(QLabel(title), QLineEdit(title))
        for title in ["W", "P", "R"]:
            form_layout.addRow(QLabel(title), QLineEdit(title))

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

        # 레이아웃에 폼과 버튼 쌓기
        layout.addLayout(form_layout)
        layout.addStretch(1)    # 폼과 버튼 사이 공간





    def _bind_macro_button_events():
        """
        매크로 버튼이 눌리면 어떤 일을 할 지 정의

        모든 매크로 버튼에 클릭 시그널을 연결
        """


    def _handle_macro_button_clicked():
        """
        매크로 버튼이 클릭되었을 때 실행할 함수
        """


    def _bind_goto_button_clicked():
        """
        'GoTo' 버튼이 눌리면 어떤 일을 할 지 정의

        시그널 연결
        """









# ==========================================================
# 2. 단독 실행 (테스트용)
"""
python -m ui.widgets.target_position_widget
"""
# ==========================================================
if __name__ == '__main__':
    import sys
    from PyQt6.QtWidgets import QApplication, QMainWindow
    from pathlib import Path


    app = QApplication(sys.argv)
    
    # 배경 확인을 위한 메인 윈도우
    main_win = QMainWindow()
    widget = TargetPositionWidget()
    main_win.setCentralWidget(widget)
    main_win.setWindowTitle("TargetPositionWidget 테스트")
    main_win.resize(400, 300)
    main_win.show()


    # ────────────────────────────────────────
    def apply_style_to(widget):
        """
        QSS 파일을 읽어서 지정한 위젯에 스타일을 적용한다.
        이 함수는 단독 실행(테스트) 모드에서만 사용된다.
        """
        qss_path = Path("styles/stylesheet.qss")
        if qss_path.exists():
            try:
                with open(qss_path, "r", encoding="utf-8") as f:
                    widget.setStyleSheet(f.read())
                print("✅ 스타일시트 로드 성공")
            except Exception as e:
                print(f"❌ 스타일시트 로드 실패: {e}")
        else:
            print(f"⚠️ 스타일시트 파일 없음: {qss_path}")

    # 정의한 함수를 바로 호출
    apply_style_to(widget)
    # ────────────────────────────────────────


    sys.exit(app.exec())

