# ui/widgets/target_position_widget.py

from PyQt6.QtCore import Qt, pyqtSlot
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
    QPushButton,
    QMessageBox
)
from typing import Dict, Any, TYPE_CHECKING
from functools import partial

from ui.widgets.base_widget import BaseWidget



# 런타임에는 import 하지 않음
if TYPE_CHECKING:
    from view_models.target_position_viewmodel import TargetPositionViewModel



class TargetPositionWidget(BaseWidget):
    """
     로봇팔, 턴테이블의 이동 명령과 매크로를 관리하는 위젯

     기능:
        - 좌표 입력(X,Y,Z,W,P,R)
        - 'Edit Macro' 버튼으로 매크로 설정 모달(MacroSettingsDialog) 열기
        - 매크로 버튼(사용자가 입력한 매크로 제목)을 누르면 저장된 값 불러오기
        - 'GoTo' 버튼 클릭 시 `goto_requested` 시그널 발생
    """

    def __init__(self, view_model: "TargetPositionViewModel", parent=None):
        # ViewModel 인스턴스를 클래스 속성으로 저장
        # super().__init__() 전에 저장
        self.vm = view_model

        # 좌표값 입력 위젯들을 저장할 보관함
        self.coord_widgets: Dict[str, QLineEdit] = {}        

        # 버튼 참조 변수 미리 초기화
        self.edit_macro_button = None
        self.goto_button = None
        self.macro_buttons = []

        # BaseWidget의 __init__()이 _init_ui() 호출 → 실제 UI 생성
        super().__init__(parent)

        # 클릭 이벤트 처리 (UI 생성 후)
        self._bind_events()


    def _init_ui(self):
        """
        BaseWidget이 호출하는 UI 초기화 메서드
        여기서 실제 UI를 구성한다
        """

        self.setObjectName("target_position_widget")

        # BaseWidget이 레이아웃을 설정했는지 확인
        # BaseWidget이 이미 layout을 설정했을 수 있으므로 가져온다
        existing_layout = self.layout()

        # BaseWidget이 레이아웃을 설정하지 않았다면 여기서 딱 1번만 생성
        if existing_layout is None:
            
            # QVBoxLayout 객체 생성
            main_layout = QVBoxLayout()

            # 위젯(self)이 레이아웃 부모가 됨 - 레이아웃 객체를 위잿의 최상위 레이아웃으로 지정
            self.setLayout(main_layout)

            main_layout.setContentsMargins(0, 0, 0, 0)
        else:
            # 이미 있으면 재사용
            main_layout = existing_layout

        # 새로운 UI 구성 - GroupBox 생성 후 레이아웃에 추가
        base_group_box = self._configure_base_layout()
        main_layout.addWidget(base_group_box)


    def update_data(self, data: Any):
        """
        BaseWidget의 추상 메서드를 구현한다
        """
        pass


    def _configure_base_layout(self) -> QGroupBox:
        """
        전체 레이아웃 구성

        최상위 레이아웃을 self에 붙이지 않고(생성하지 않고), 단순히 GroupBox를 반환한다.
        """

        ##########################
        # --- 기본 형태 설정 --- #
        ##########################

        # 모든 부속 위젯을 담을 그룹박스 생성
        base_group_box = QGroupBox("Target Position")
        base_group_box.setStyleSheet("QGroupBox { background-color: grey; }")  # 개발용 임시 배경


        widgets_layout = QVBoxLayout()

        ################
        # --- 상단 --- #
        ################

        # Edit Macro 영역
        section_edit_macro = QFrame()
        section_edit_macro.setObjectName("section_edit_macro")
        section_edit_macro.setStyleSheet("QFrame { background-color: blue; }")  # 개발용 임시 배경

        # Edit Macro 버튼 레이아웃
        layout_edit_macro = QHBoxLayout(section_edit_macro)
        layout_edit_macro.setContentsMargins(0, 0, 0, 0)
        layout_edit_macro.setSpacing(0)
        layout_edit_macro.addStretch(1)

        # 레이아웃에 Edit Macro 버튼 영역 넣기
        layout_edit_macro.addWidget(self._create_edit_macro_button())


        ################
        # --- 중단 --- #
        ################

        # 좌표 입력 영역
        section_coordinate = QFrame()
        section_coordinate.setObjectName("section_coordinate")
        section_coordinate.setStyleSheet("QFrame { background-color: green; }")  # 개발용 임시 배경

        # 좌표 입력 레이아웃 (좌우로 나뉨)
        layout_coordinate = QHBoxLayout(section_coordinate)
        layout_coordinate.setContentsMargins(5, 5, 5, 5)
        layout_coordinate.setSpacing(10)

        # 로봇팔(X, Y, Z) 입력 영역
        section_robot_coordinate = QFrame()
        section_robot_coordinate.setObjectName("section_robot_coordinate")
        section_robot_coordinate.setStyleSheet("QFrame { background-color: Aquamarine; }")  # 개발용 임시 배경
        # 로봇팔 좌표 입력 영역에 X, Y, Z 폼 레이아웃 생성하여 추가
        section_robot_coordinate.setLayout(self._create_coordinate_input_fields(["X", "Y", "Z"]))

        # 턴테이블(W, P, R) 입력 영역
        section_turtable_coordinate = QFrame()
        section_turtable_coordinate.setStyleSheet("QFrame { background-color: Darkseagreen; }")  # 개발용 임시 배경
        # 턴테이블 좌표 입력 섹션에 W, P, R 폼 레이아웃 생성하여 추가
        section_turtable_coordinate.setLayout(self._create_coordinate_input_fields(["W", "P", "R"]))

        # 좌표 입력 레이아웃에 로봇팔, 턴테이블 입력 영역 넣기
        layout_coordinate.addWidget(section_robot_coordinate)
        layout_coordinate.addWidget(section_turtable_coordinate)

        # 매크로 버튼 영역
        section_macro_buttons = QFrame()
        section_macro_buttons.setObjectName("section_macro_buttons")
        section_macro_buttons.setStyleSheet("QFrame { background-color: yellow; }")  # 개발용 임시 배경

        # 매크로 버튼 레이아웃
        laytout_macro_buttons = QGridLayout(section_macro_buttons)
        laytout_macro_buttons.setContentsMargins(5, 5, 5, 5)
        laytout_macro_buttons.setSpacing(5)

        # 매크로 버튼 추가
        laytout_macro_buttons.addWidget(self._create_macro_button("매크로 1"), 0, 0)
        laytout_macro_buttons.addWidget(self._create_macro_button("매크로 2"), 0, 1)
        laytout_macro_buttons.addWidget(self._create_macro_button("매크로 3"), 1, 0)
        laytout_macro_buttons.addWidget(self._create_macro_button("매크로 4"), 1, 1)


        ################
        # --- 하단 --- #
        ################
        # Go To 버튼 영역
        section_go_to = QFrame()
        section_go_to.setObjectName("section_go_to")
        section_go_to.setStyleSheet("QFrame { background-color: orange; }")  # 개발용 임시 배경

        # Go To 버튼 레이아웃
        layout_go_to = QHBoxLayout(section_go_to)
        layout_go_to.setContentsMargins(0, 0, 0, 0)
        layout_go_to.setSpacing(0)

        # 레이아웃에 Go To 버튼 넣기
        layout_go_to.addWidget(self._create_goto_button())



        #################################
        # --- 부속 위젯 영역들 합체 --- #
        #################################
        # 그룹박스에 모두 추가
        widgets_layout.addWidget(section_edit_macro)
        widgets_layout.addWidget(section_coordinate)
        widgets_layout.addWidget(section_macro_buttons)
        widgets_layout.addWidget(section_go_to)

        base_group_box.setLayout(widgets_layout)


        return base_group_box


    ##############################
    # --- 부속 위젯들 만들기 --- #
    ##############################
    
    # --- 버튼 만들기 --- #
    def _create_button(self, title: str, type: str) -> QPushButton:
        button = QPushButton(title.upper())
        # QSS에서 찾기 쉽게 소문자와 언더스코어를 사용
        button.setObjectName(title.lower().replace(" ", "_"))
        button.setProperty("type", type)
        return button

    def _create_edit_macro_button(self) -> QPushButton:
        """ Edit Macro 버튼 생성 """
        # 인스턴스 변수에 버튼 객체 저장
        self.edit_macro_button = self._create_button(title="Edit Macro", type="special")
        return self.edit_macro_button
        # return self._create_button(title="Edit Macro", type="special")
    
    def _create_macro_button(self, title: str) -> QPushButton:
        """ 
        매크로 버튼 생성

        버튼에 표시되는 제목은 사용자가 지정한 이름
        """
        return self._create_button(title=title, type="general")
    
    def _create_goto_button(self) -> QPushButton:
        """ GoTo 버튼 생성 """
        return self._create_button(title="Go To", type="special")


    # --- 좌표 입력 만들기 --- #
    def _create_coordinate_input_fields(self, axes: list[str]) -> QFormLayout:
        """
        지정된 축(axes) 목록에 대해 '라벨-입력창' QFormLayout을 생성

        인자 값:
            axes: ["X", "Y", "Z"] 또는 ["W", "P", "R"]

        반환:
            QFormLayout: 라벨과 QLineEdit가 채워진 폼 레이아웃
        """
        form_layout = QFormLayout()
        form_layout.setContentsMargins(5, 5, 5, 5)
        form_layout.setSpacing(5)
        
        # QFormLayout은 수평/수직 간격 동시 설정이 어려우므로
        form_layout.setHorizontalSpacing(10)
        form_layout.setVerticalSpacing(5)

        for axis in axes:
            label = QLabel(f"{axis}:")
            line_edit = QLineEdit()
            line_edit.setObjectName(f"line_edit_{axis}") # QSS 적용을 위한 ID
            line_edit.setPlaceholderText(f"{axis} 값 입력...")

            # 만든 위젯을 보관함에 저장
            self.coord_widgets[axis] = line_edit
            
            form_layout.addRow(label, line_edit)

        return form_layout



    def _bind_events(self):
        """
        전선 연결하기 (아직 불 들어온것 아님)
            - 누가 누구랑 연결될 지 미리 정해주기
            - 앱이 시작될 때 딱 1번만 호출
        시그널-슬롯(_on으로 시작하는 메서드) connect를 모아놓음 - 버튼 눌리면 어떤 일을 할 지 약속
        """

        # self.edit_macro_button이 None이 아님을 명시적으로 확인 (Pylance 경고 해결 및 런타임 안정성)
        assert self.edit_macro_button is not None, "Edit Macro 버튼이 생성되지 않았습니다."

        # 'Edit Macro' 버튼 클릭 시 _on_edit_macro_clicked 슬롯 호출
        self.edit_macro_button.clicked.connect(self._on_edit_macro_button_clicked)
        

    # --- 슬롯 --- #
    @pyqtSlot()
    def _on_edit_macro_button_clicked(self):
        """
        'Edit Macro' 버튼이 클릭되었을 때 실행할 함수

        MacroSettingsDialog 열기
        """
        self.vm.open_macro_settings_dialog()






    def _create_line_edit(self):
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





    def _bind_macro_button_events(self):
        """
        매크로 버튼이 눌리면 어떤 일을 할 지 정의

        모든 매크로 버튼에 클릭 시그널을 연결
        """
        pass


    def _handle_macro_button_clicked(self):
        """
        매크로 버튼이 클릭되었을 때 실행할 함수
        """
        pass


    def _bind_goto_button_clicked(self):
        """
        'GoTo' 버튼이 눌리면 어떤 일을 할 지 정의

        시그널 연결
        """
        pass









# ==========================================================
# Smoke Test
"""
python -m ui.widgets.target_position_widget
"""
# ==========================================================
if __name__ == '__main__':
    import sys
    from PyQt6.QtWidgets import QApplication, QMainWindow
    from models.position_model import PositionModel
    from pathlib import Path
    
    # [추가 1] 로그 리스너 임포트
    from core.log_listener import LogListener

    # [중요] DLL 로드
    from utils.dll_loader import load_pyads_dll
    try:
        load_pyads_dll()
        print("✅ DLL 로드 완료")
    except Exception as e:
        print(f"⚠️ DLL 로드 실패: {e}")

    from view_models.target_position_viewmodel import TargetPositionViewModel
    from services.plc_service import PLCService

    app = QApplication(sys.argv)
    
    # [추가 2] 로그 리스너 가동 (이제 에러가 콘솔에 보입니다)
    log_listener = LogListener()

    # 1. Model 생성
    model = PositionModel()
    
    # 2. PLC Service 생성 및 연결
    plc_service = PLCService()
    
    try:
        plc_service.connect_plc() 
        print("✅ PLC Service 연결(Mock/Real) 완료")
    except Exception as e:
        print(f"❌ 연결 실패: {e}")

    # 3. ViewModel 생성
    view_model = TargetPositionViewModel(model, plc_service)

    # 4. Widget 생성
    main_win = QMainWindow()
    widget = TargetPositionWidget(view_model)
    main_win.setCentralWidget(widget)
    main_win.setWindowTitle("TargetPositionWidget 테스트")
    main_win.resize(400, 300)
    main_win.show()

    # 스타일시트 적용 (생략 가능)
    # ...

    sys.exit(app.exec())