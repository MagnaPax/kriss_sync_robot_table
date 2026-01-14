# ui/widgets/robot_controller_widget.py
from PyQt6.QtCore import pyqtSlot, QTimer
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
    QAbstractSpinBox
)
from functools import partial
from typing import Dict, Any, TYPE_CHECKING, Union, Optional

from core.event_bus import EVENT_BUS
from ui.widgets.base_widget import BaseWidget
from models.fanuc_pose_model import FANUCPose
from models.fanuc_pose_key import FANUCPoseKey
from config.data_formats import KEY_ROBOT_FEED_RATE
from utils.validators import NumericValidator
from ui.dialogs.macro_settings_dialog import MacroSettingsDialog
from PyQt6.QtWidgets import QWidget


# 런타임에는 import 하지 않음
if TYPE_CHECKING:
    from view_models.robot_controller_viewmodel import RobotControllerViewModel



class RobotControllerWidget(BaseWidget):
    """
    로봇팔, 턴테이블의 이동 명령과 매크로를 관리하는 위젯

    기능:
        - 좌표 입력(X,Y,Z,W,P,R)
        - 'Edit Macro' 버튼으로 매크로 설정 모달(MacroSettingsDialog) 열기
        - 매크로 버튼(사용자가 입력한 매크로 제목)을 누르면 저장된 값 불러오기
        - 'GoTo' 버튼 클릭 시 `goto_requested` 시그널 발생
    """
    # ========================================
    # 초기화 및 설정 (Initialization)
    # ========================================
    def __init__(self, parent: Optional[QWidget] = None):
        # ViewModel 인스턴스를 클래스 속성으로 저장
        # super().__init__() 전에 저장
        self.vm: Optional["RobotControllerViewModel"] = None

        # 좌표값 입력 위젯들을 저장할 보관함
        self.coord_widgets: Dict[str, Union[QLineEdit, QDoubleSpinBox]] = {}

        # 매크로 버튼들을 저장할 보관함
        self.macro_btn_map: Dict[str, QPushButton] = {}

        # 매크로 데이터를 저장해둘 보관함
        self.cached_macro_data: Dict[str, Any] = {}

        # 버튼 참조 변수 미리 초기화
        self.edit_macro_button = None
        self.goto_button = None
        self.macro_buttons = []

        # BaseWidget의 __init__()이 _init_ui() 호출 → 실제 UI 생성
        super().__init__(parent)

        # 클릭 이벤트 처리 (UI 생성 후)
        self._bind_events()

    def set_view_model(self, view_model: "RobotControllerViewModel"):
        """외부에서 뷰모델을 꽂아주는 함수(Setter)"""
        self.vm = view_model
        
        # VM의 로컬 시그널 연결
        self.vm.macros_loaded.connect(self._on_macro_data_loaded)
        self.vm.robot_poses_clear.connect(self.clear_widget)
        self.vm.robot_poses_changed.connect(self.safe_update_data)
        self.vm.disable_buttons.connect(self._on_disable_buttons)
        
        # 매크로 데이터에서 버튼 제목을 읽어 와야 되기 때문에 UI가 생성된 후에 바로 호출
        self.vm.load_macro_data()

    def _bind_events(self):
        """
        전선 연결하기 (아직 불 들어온것 아님)
            - 누가 누구랑 연결될 지 미리 정해주기
            - 앱이 시작될 때 딱 1번만 호출
        시그널-슬롯(_on으로 시작하는 메서드) connect를 모아놓음 - 버튼 눌리면 어떤 일을 할 지 약속
        """

        # self.edit_macro_button이 None이 아님을 명시적으로 확인 (Pylance 경고 해결 및 런타임 안정성)
        assert self.edit_macro_button is not None, "Edit Macro 버튼이 생성되지 않았습니다."
        self.edit_macro_button.clicked.connect(self._on_edit_macro_button_clicked)

        # self.goto_button이 None이 아님을 명시적으로 확인 (Pylance 경고 해결 및 런타임 안정성)
        assert self.goto_button is not None, "GoTo 버튼이 생성되지 않았습니다."
        self.goto_button.clicked.connect(self._on_goto_btn_clicked) # type: ignore

        # 매크로 버튼 클릭 이벤트 연결
        # 보관함에 저장된 모든 매크로 버튼에 대해 연결을 수행
        for macro_id, btn in self.macro_btn_map.items():
            assert btn is not None, f"매크로 버튼 '{macro_id}'이 생성되지 않았습니다."
            # partial을 사용하여 어떤 버튼이 눌렸는지(macro_id)를 함께 넘김
            btn.clicked.connect(partial(self._on_macro_btn_clicked, macro_id)) # type: ignore

        # Feed Rate 값 변경 이벤트 연결
        feed_widget = self.coord_widgets.get('FEED RATE')
        if feed_widget and isinstance(feed_widget, QDoubleSpinBox):
            # valueChanged는 값이 변경될 때(버튼 클릭 포함) 발생합니다.
            feed_widget.valueChanged.connect(self._on_feed_rate_changed)            



    # ========================================
    # UI 구성 (Initialization)
    # ========================================
    def _init_ui(self):
        """
        BaseWidget이 호출하는 UI 초기화 메서드
        여기서 실제 UI를 구성한다
        """

        self.setObjectName("robot_controller_widget")

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

    def _configure_base_layout(self) -> QGroupBox:
        """
        전체 레이아웃 구성

        최상위 레이아웃을 self에 붙이지 않고(생성하지 않고), 단순히 GroupBox를 반환한다.
        """

        ##########################
        # --- 기본 형태 설정 --- #
        ##########################

        # 모든 부속 위젯을 담을 그룹박스 생성
        base_group_box = QGroupBox("Robot Controller")


        widgets_layout = QVBoxLayout()

        ################
        # --- 상단 --- #
        ################

        # Edit Macro 영역
        section_edit_macro = QFrame()
        section_edit_macro.setObjectName("section_edit_macro")

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

        # 좌표 입력 레이아웃 (좌우로 나뉨)
        layout_coordinate = QHBoxLayout(section_coordinate)
        layout_coordinate.setContentsMargins(5, 5, 5, 5)
        layout_coordinate.setSpacing(10)

        # 로봇팔(X, Y, Z) 입력 영역
        section_robot_coordinate = QFrame()
        section_robot_coordinate.setObjectName("section_robot_coordinate")
        # 로봇팔 좌표 입력 영역에 X, Y, Z 폼 레이아웃 생성하여 추가
        section_robot_coordinate.setLayout(self._create_coordinate_input_fields([
            FANUCPoseKey.X, FANUCPoseKey.Y, FANUCPoseKey.Z
        ]))

        # 턴테이블(W, P, R) 입력 영역
        section_turtable_coordinate = QFrame()
        # 턴테이블 좌표 입력 섹션에 W, P, R 폼 레이아웃 생성하여 추가
        section_turtable_coordinate.setLayout(self._create_coordinate_input_fields([
            FANUCPoseKey.W, FANUCPoseKey.P, FANUCPoseKey.R
        ]))

        # 좌표 입력 레이아웃에 로봇팔, 턴테이블 입력 영역 넣기
        layout_coordinate.addWidget(section_robot_coordinate)
        layout_coordinate.addWidget(section_turtable_coordinate)

        # 매크로 버튼 영역
        section_macro_buttons = QFrame()
        section_macro_buttons.setObjectName("section_macro_buttons")

        # 매크로 버튼 레이아웃
        laytout_macro_buttons = QGridLayout(section_macro_buttons)
        laytout_macro_buttons.setContentsMargins(5, 5, 5, 5)
        laytout_macro_buttons.setSpacing(5)

        # 매크로 버튼 추가
        # Arguments: 매크로ID, 기본제목
        laytout_macro_buttons.addWidget(self._create_macro_button("Macro_1"), 0, 0)
        laytout_macro_buttons.addWidget(self._create_macro_button("Macro_2"), 0, 1)
        laytout_macro_buttons.addWidget(self._create_macro_button("Macro_3"), 1, 0)
        laytout_macro_buttons.addWidget(self._create_macro_button("Macro_4"), 1, 1)


        ################
        # --- 하단 --- #
        ################
        # Feed Rate 입력 영역
        section_feed_rate = QFrame()
        section_feed_rate.setObjectName("section_feed_rate")

        # Feed 입력 레이아웃
        layout_feed = QHBoxLayout(section_feed_rate)
        layout_feed.setContentsMargins(5, 5, 5, 5)

        # 레이아웃에 Feed Rate 입력 영역 넣기
        layout_feed.addLayout(self._create_coordinate_input_fields(["FEED RATE",]))

        # Go To 버튼 영역
        section_go_to = QFrame()
        section_go_to.setObjectName("section_go_to")

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
        widgets_layout.addWidget(section_feed_rate)
        widgets_layout.addWidget(section_go_to)

        base_group_box.setLayout(widgets_layout)


        return base_group_box

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
    
    def _create_macro_button(self, macro_id: str) -> QPushButton:
        """ 
        매크로 버튼 생성

        버튼 제목은 macro_id (나중에 데이터 로드 시 변경됨)
        """
        btn = self._create_button(title=macro_id, type="general")

        # 버튼을 보관함에 등록(나중에 이름 바꾸기 위해)
        self.macro_btn_map[macro_id] = btn

        # 버튼에 id 심기
        btn.setProperty("macro_id", macro_id)

        return btn

    def _create_goto_button(self) -> QPushButton:
        """ GoTo 버튼 생성 """
        self.goto_button = self._create_button(title="Go To", type="special")
        return self.goto_button
    
    def _create_coordinate_input_fields(self, axes: list[Union[str, FANUCPoseKey]]) -> QFormLayout:
        """
        지정된 축(axes) 목록에 대해 '라벨-입력창' QFormLayout을 생성

        인자 값:
            axes: [FANUCPoseKey.X, ...] 또는 ["FEED RATE"]

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
            # Enum인 경우 value("X", "Y"...)를 사용, 문자열이면 그대로 사용
            axis_name = axis.value if isinstance(axis, FANUCPoseKey) else axis
            
            label = QLabel(f"{axis_name}:")

            if axis_name not in ["FEED RATE"]:
                # 일반 좌표는 QLineEdit 사용
                line_edit = QLineEdit()
                line_edit.setObjectName(f"line_edit_{axis_name}") # QSS 적용을 위한 ID
                line_edit.setPlaceholderText(f"{axis_name} 값 입력...")

                # 숫자만 입력 가능하도록 유효성 검사기 추가
                # 에러 발생 시 BaseWidget의 error_occurred 시그널을 통해 알림
                validator = NumericValidator(
                    error_callback=lambda msg: self.error_occurred.emit(msg), # type: ignore
                    parent=line_edit
                )
                validator.setDecimals(3) # 소수점 3자리까지 허용
                line_edit.setValidator(validator)                

                input_widget = line_edit

            else:
                # feed rate는 QDoubleSpinBox 사용
                spin_box = QDoubleSpinBox()
                spin_box.setObjectName(f"spinbox_{axis_name.lower().replace(' ', '_')}")

                # 설정 적용
                spin_box.setRange(0.0, 1000.0)      # 범위 0 ~ 1000
                spin_box.setValue(10.0)             # 기본값 10
                spin_box.setSingleStep(5.0)         # 1회 클릭 시 5씩 증감
                spin_box.setSuffix(" mm/sec")       # 단위 표시
                spin_box.setKeyboardTracking(False) # (엔터, 포커스 이동, 스핀박스 버튼 클릭)만 시그널 발생
                spin_box.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons) # Up/Down 화살표 제거
                spin_box.focusInEvent = lambda e: QTimer.singleShot(0, spin_box.selectAll)  # 전체선택(사용자 입력편의성 향상)

                input_widget = spin_box

            # 만든 위젯을 보관함에 저장 (Key: "X", "Y", "FEED RATE" 등 문자열)
            self.coord_widgets[axis_name] = input_widget
            form_layout.addRow(label, input_widget)

        return form_layout



    # ===============================================
    # 데이터 처리
    # ===============================================
    def update_data(self, pose: FANUCPose):
        """
        [Override] BaseWidget.update_data
        실제 UI 업데이트 로직 (safe_update_data에 의해 호출됨)
        """
        if not pose: return
        EVENT_BUS.log.message.emit(f"{self.log_prefix} 입력창에 넣을 데이터: {pose}", "DEBUG")

        # FANUCPoseKey를 사용한 동적 매핑
        # 1. 로봇 좌표 (X, Y, Z, W, P, R)
        for key_enum in FANUCPoseKey:
            # Data Key: 'x' (소문자) -> pose.x 접근용
            data_attr = key_enum.model_key
            
            # Widget Key: 'X' (대문자) -> self.coord_widgets 접근용
            widget_key = key_enum.value
            
            # 1) 데이터 가져오기
            val = getattr(pose, data_attr, 0.0)
            
            # 2) 위젯 가져오기
            if widget := self.coord_widgets.get(widget_key):
                # 시그널 차단 (피드백 루프 방지)
                blocker = widget.blockSignals(True)
                
                if isinstance(widget, QDoubleSpinBox):
                    widget.setValue(float(val))
                elif isinstance(widget, QLineEdit):
                    widget.setText(str(val))
                
                widget.blockSignals(blocker)

        # 2. Feed Rate (FANUCPoseKey에 없으므로 별도 처리)
        # 키는 config.data_formats.KEY_ROBOT_FEED_RATE ('f') 이지만
        # UI 위젯 키는 'FEED RATE'로 되어 있음 -> 이건 유지하거나 상수로 뺄 수 있음
        # 여기서는 기존 문자열 'FEED RATE'를 그대로 사용 (단, pose.f 로 값은 가져옴)
        if widget := self.coord_widgets.get('FEED RATE'):
            blocker = widget.blockSignals(True)
            widget.setValue(pose.f)
            widget.blockSignals(blocker)

    def clear_widget(self):
        """
        입력 데이터 모두 초기화
        - 로봇 좌표 (X,Y,Z,W,P,R)
        - Feed Rate
        """
        EVENT_BUS.log.message.emit("RobotControllerWidget 입력 필드 초기화", "DEBUG")

        # 1. 좌표 입력창 초기화
        for axis, widget in self.coord_widgets.items():
            if isinstance(widget, QLineEdit):
                widget.setText("0.000")
            elif isinstance(widget, QDoubleSpinBox):
                # FEED RATE 등 스핀박스인 경우
                if axis == "FEED RATE":
                    widget.setValue(10.0) # 기본값으로
                else:
                    widget.setValue(0.0)

    def _extract_data_from_ui(self) -> FANUCPose:
        """
        QLineEdit 객체들에서 데이터만 뽑아서 FANUCPose 객체를 만든다.
        뷰모델에게 QLineEdit 객체를 넘기지 않고 데이터 뽑아서 넘기는 이유
            - 워커가 이 객체를 들고 백그라운드 스레드에서 작업하면 스레드 충돌로 에러난다
            - 뷰모델이 뷰와 결합해서 뷰를 바꿀 때 뷰모델까지 바꿔야 된다
        """
        data = {}

        # 좌표값 읽기
        # 좌표값 읽기
        for key_enum in FANUCPoseKey:
            widget_key = key_enum.value # "X", "Y", ... (Dictionary Key)
            data_key = key_enum.model_key # "x", "y", ... (Data Attribute)
            
            widget = self.coord_widgets.get(widget_key)

            if widget:
                # QLineEdit 전용 로직
                text = widget.text().strip()
                val = float(text) if text else 0.0
                data[data_key] = val
            else:
                data[data_key] = 0.0

        # 위젯 타입에 따라 값 가져오는 방식 분기
        feed_widget = self.coord_widgets.get('FEED RATE')
        feed_val = 10.0 # 기본값

        if feed_widget:
            if isinstance(feed_widget, QDoubleSpinBox):
                # SpinBox 는 value()로 float값을 직접 가져옴
                feed_val = feed_widget.value()
            elif isinstance(feed_widget, QLineEdit):
                # LineEdit 는 text()로 문자열을 가져옴)
                text = feed_widget.text().strip()
                # 값이 비어있으면 10.0을 사용
                feed_val = float(text) if text else 10.0
        
        return FANUCPose(
            x=data['x'],
            y=data['y'],
            z=data['z'],
            w=data['w'],
            p=data['p'],
            r=data['r'],
            f=feed_val
        )



    # ===============================================
    # ViewModel 시그널 수신 (상태 업데이트)
    # =============================================== 
    @pyqtSlot(bool)
    def _on_disable_buttons(self, disable: bool):
        """버튼 비활성화 시그널 처리"""
        if self.goto_button:
            self.goto_button.setDisabled(disable)

    @pyqtSlot(dict)
    def _on_macro_data_loaded(self, data: Dict[str, Any]):
        """매크로 데이터 로드 시그널 처리"""
        EVENT_BUS.log.message.emit(
            f"매크로 데이터 로드 완료 (총 {len(data)}개 항목)", 
            "INFO"
        )

        # 나중에 쓰기 위해 보관함에 저장
        self.cached_macro_data = data


        # 딕셔너리에 있는 모든 매크로 데이터를 순회
        for macro_id, macro_data in data.items():

            # 내 UI에 해당 ID를 가진 버튼이 있다면
            if macro_id in self.macro_btn_map:
                btn = self.macro_btn_map[macro_id]

                if btn:
                    # 'name'값을 가져옴
                    saved_name = macro_data.get('name', "")

                    # 값이 비어있으면('') ID를 대신 사용
                    if saved_name and saved_name.strip():
                        new_name = saved_name
                    else:
                        new_name = macro_id # 또는 f"매크로 {macro_id[-1]}" 등 원하는 기본값

                    btn.setText(new_name)


    # ===============================================
    # 사용자 인터랙션 처리 (UI 이벤트)
    # =============================================== 
    @pyqtSlot()
    def _on_edit_macro_button_clicked(self):
        """
        'Edit Macro' 버튼이 클릭되었을 때 실행할 함수

        직접 MacroSettingsDialog 를 연다
        """
        if not self.vm: return

        EVENT_BUS.log.message.emit(f"{self.log_prefix} 매크로 편집 다이얼로그(MacroSettingsDialog) 열림", "INFO")

        dialog = MacroSettingsDialog(parent=self)

        # 다이얼로그 실행
        # Modal로 열어서 호출부 입력 막힘
        dialog.exec()

        # 다이얼로그가 닫히면 이 줄이 실행됨 -> 데이터 새로고침 기능
        self.vm.load_macro_data()

    @pyqtSlot(str)
    def _on_macro_btn_clicked(self, macro_id: str):
        """
        매크로 버튼 클릭 시: 저장된 좌표 데이터를 입력창에 채워넣음
        """
        EVENT_BUS.log.message.emit(f"매크로 버튼 클릭됨: {macro_id}", "DEBUG")

        # 1. 저장된 데이터가 있는지 확인
        if macro_id not in self.cached_macro_data:
            return

        macro_data = self.cached_macro_data[macro_id]

        # 어떤 매크로를 불러왔는지 이름과 함께 기록
        macro_name = macro_data.get('name', 'No Name')
        EVENT_BUS.log.message.emit(
            f"매크로 불러오기: {macro_id} ('{macro_name}') -> 입력창 갱신", 
            "INFO"
        )

        # 2. 데이터 -> UI 입력창으로 복사
        for key_enum in FANUCPoseKey:
            data_key = key_enum.model_key  # 'x'
            widget_key = key_enum.value    # 'X'
            
            # 데이터 가져오기 (없으면 0.0)
            val = macro_data.get(data_key, 0.0)
            
            # 위젯 가져오기
            line_edit = self.coord_widgets.get(widget_key)
            
            if isinstance(line_edit, QLineEdit):
                # QLineEdit에 값 설정 (소수점 3자리까지)
                line_edit.setText(f"{val:.3f}")

        # Feed Rate 위젯 값 업데이트(SpinBox 대응)
        feed_widget = self.coord_widgets.get('FEED RATE')
        if feed_widget and isinstance(feed_widget, QDoubleSpinBox):
            feed_val = macro_data.get('f', 10.0)
            feed_widget.setValue(feed_val)

        EVENT_BUS.log.message.emit(f"UI 업데이트 완료: 매크로 ID({macro_id})", "DEBUG")

    @pyqtSlot(float)
    def _on_feed_rate_changed(self, feed_rate: float):
        """FEED RATE 스핀박스 값 변경됐을 때"""
        if self.vm:
            self.vm.update_feed_rate(feed_rate)

    @pyqtSlot()
    def _on_goto_btn_clicked(self):
        """
        'GoTo' 버튼이 클릭되었을 때 실행할 함수
        """
        if not self.vm: return

        try:
            # QLineEdit 객체로부터 데이터 추출
            line_edit_data = self._extract_data_from_ui()

            EVENT_BUS.log.message.emit(
                f"{self.log_prefix} 사용자의 이동 명령(GoTo) 요청: {line_edit_data}", 
                "INFO"
            )

            self.vm.request_move_robot(line_edit_data)

        except ValueError as e:
            error_msg = "좌표값 입력 오류: 숫자만 입력 가능합니다."
            EVENT_BUS.log.message.emit(error_msg, "WARNING")

            # 에러 시그널 방출
            self.error_occurred.emit(error_msg)



# ==========================================================
# Smoke Test
"""
python -m ui.widgets.robot_controller_widget
"""
# ==========================================================
if __name__ == '__main__':
    import sys
    from PyQt6.QtWidgets import QApplication, QMainWindow
    from models.fanuc_pose_model import FANUCPoseModel
    
    # [추가 1] 로그 리스너 임포트
    from core.log_listener import LogListener

    # [중요] DLL 로드
    from utils.dll_loader import load_pyads_dll
    try:
        load_pyads_dll()
        print("✅ DLL 로드 완료")
    except Exception as e:
        print(f"⚠️ DLL 로드 실패: {e}")

    from view_models.robot_controller_viewmodel import RobotControllerViewModel
    from services.plc_service import PLCService

    app = QApplication(sys.argv)
    
    # 로그 리스너 가동 (에러가 콘솔에 보인다)
    log_listener = LogListener()

    # 1. Model 생성
    model = FANUCPoseModel()
    
    # 2. PLC Service 생성 및 연결
    plc_service = PLCService()
    
    try:
        plc_service.connect_plc() 
        print("✅ PLC Service 연결(Mock/Real) 완료")
    except Exception as e:
        print(f"❌ 연결 실패: {e}")

    # 3. ViewModel 생성
    view_model = RobotControllerViewModel(model, plc_service)

    # 4. Widget 생성
    main_win = QMainWindow()
    widget = RobotControllerWidget(view_model)
    main_win.setCentralWidget(widget)
    main_win.setWindowTitle("RobotControllerWidget 테스트")
    main_win.resize(400, 300)
    main_win.show()

    # 스타일시트 적용 (생략 가능)
    # ...

    sys.exit(app.exec())