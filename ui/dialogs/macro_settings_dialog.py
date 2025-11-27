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
    QWidget,
    QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QIcon
from typing import Dict, Any, Tuple, cast
from functools import partial

from config.paths import CONFIG_MACRO_PATH

from services.macro_service import MacroService as Service
from view_models.macro_settings_dialog_viewmodel import MacroSettingsDialogViewModel as ViewModel



class MacroSettingsDialog(QDialog):

    def __init__(self, parent=None, viewmodel = ViewModel):
        super().__init__(parent)


        # 의존성 주입
        # View가 ViewModel 소유하기 위해: Service 생성 -> ViewModel에 주입
        """
        뷰가 왜 서비스를 갖고 있나?

        self.service를 가지고 있지만, 뷰는 서비스의 비즈니스 로직 함수를 직접 호출하지 않는다
        단지 self.vm을 만들기 위한 재료(생성자 인자)로만 잠깐 사용하고 끝낼 뿐
        서비스 레이어를 사용하기 위함이 아니라 뷰모델 객체를 갖기 위한 조립만 하는 역할
        """
        self.service = Service()
        self.vm = ViewModel(self.service)


        # --- 시그널 연결 (전화선 연결) --- #
        # 실패 시 팝업
        self.vm.save_macro_failed.connect(self._on_save_failed)
        # 성공 시 버튼 피드백
        self.vm.save_macro_complete.connect(self._on_save_complete)
        # 데이터 도착 시그널 연결
        self.vm.macro_data_loaded.connect(self._on_data_loaded)


        # 각 매크로의 위젯들을 저장할 딕셔너리
        self.macro_widgets: Dict[str, Dict[str, QWidget]] = {}

        self._init_ui()

        # 사용자 입력이 끝난 뒤(self._init_ui())에 저장 버튼 처리
        self._bind_save_button_events()

        # UI 구성이 끝났으니 데이터 로드 요청! (방아쇠 당김)
        self.vm.load_initial_data(CONFIG_MACRO_PATH)


    def _init_ui(self):
        self.setWindowTitle("Macro Settings")
        self.setWindowIcon(QIcon("resources/icons/kriss.gif"))
        self.setModal(True)     # 모달로 실행: Dialog 를 닫을 때까지 부모 윈도우의 조작을 막는다
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



    # 뷰모델의 신호를 처리할 슬롯 추가 (클래스 맨 아래나 적당한 곳에 추가)
    @pyqtSlot(str)
    def _on_save_failed(self, error_message: str):
        """ViewModel로부터 저장 실패 알림을 받았을 때 실행"""
        QMessageBox.critical(self, "저장 실패", error_message)



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


    ############################
    # --- 저장 버튼 눌리면 --- #
    ############################
    def _bind_save_button_events(self) -> None:
        """
        저장 버튼이 눌리면 어떤 일을 할 지 정의

        -> 모든 매크로 그룹의 Save 버튼에 클릭 시그널을 연결
        """

        # 매크로 그룹의 위젯들을 저장한 macro_widgets 딕셔너리 사용
        # 1. 매크로 아이디에 해당하는 위젯 딕셔너리에서 저장 버튼 객체 꺼냄
        # 2. 버튼이 클릭될 때 실행할 함수 연결
        #   2-1. clicked: 시그널. QPushButton 객체가 클릭될 때 emit 된다
        #   2-2. connect: 슬롯 연결 - 시그널이 발생했을 때 실행할 함수(슬롯)
        for macro_id, widgets in self.macro_widgets.items():
            save_btn = cast(QPushButton, widgets['save_btn'])
            save_btn.clicked.connect(
                partial(self._handle_save_button_clicked, macro_id)
            )
            """
            - partial: 기존 함수에 일부 인자값을 넣은 새로운 함수 생성
            
            partial(func, /, *args, **keywords)

            func : 원래 호출할 함수
            *args, **keywords : 미리 채워 넣을 인자들
            반환값 : 새로운 “부분 적용 함수”

            https://docs.python.org/3/library/functools.html#functools.partial
            """

    def _handle_save_button_clicked(self, macro_id: str) -> None:
        """
        Save 버튼 클릭 시 호출되어 사용자 입력 데이터를 수집하고 저장

        Args:
            macro_id (str): 클릭된 매크로 그룹의 식별자
        """

        # 위젯에서 현재 매크로 데이터 수집
        widgets = self.macro_widgets[macro_id]

        # 데이터 수집
        data_macro = self._gather_macro_data(macro_id, widgets)

        # ViewModel에게 토스! (Delegation)
        #    에러 처리는 VM의 시그널(_on_save_failed)이 담당
        self.vm._save_macro(CONFIG_MACRO_PATH, data_macro)
        

    def _gather_macro_data(self, macro_id: str, widgets: Dict[str, QWidget]) -> Dict[str, Any]:
        """
        위젯으로부터 매크로 설정값을 읽어 딕셔너리로 반환

        Args:
            macro_id (str): 매크로 식별자
            widgets (Dict[str, QWidget]): 해당 매크로 그룹의 위젯 맵

        Returns:
            Dict[str, Any]: JSON으로 저장할 매크로 데이터
        """
        return {
            'macro_id': macro_id,
            'name': cast(QLineEdit, widgets['name_input']).text().strip(),
            # 축 별 값 추출
            'x':cast(QDoubleSpinBox, widgets['X']).value(),
            'y':cast(QDoubleSpinBox, widgets['Y']).value(),
            'z':cast(QDoubleSpinBox, widgets['Z']).value(),
            'w':cast(QDoubleSpinBox, widgets['W']).value(),
            'p':cast(QDoubleSpinBox, widgets['P']).value(),
            'r':cast(QDoubleSpinBox, widgets['R']).value()
        }


    @pyqtSlot(str)
    def _on_save_complete(self, macro_id: str):
        """
        저장 성공 시 시각적 피드백 제공 (팝업 X, 버튼 텍스트 변경 O)
        """
        # 해당 매크로의 저장 버튼을 찾음
        if macro_id in self.macro_widgets:
            save_btn = cast(QPushButton, self.macro_widgets[macro_id]['save_btn'])
            original_text = save_btn.text()
            
            # 버튼 텍스트를 잠시 'Saved!'로 변경하고 스타일을 바꿈
            save_btn.setText("✔ Saved!")
            save_btn.setStyleSheet("color: green; font-weight: bold;")
            save_btn.setEnabled(False)  # 중복 클릭 방지

            # 1초 뒤에 원래대로 복구 (QTimer 사용)
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(1000, lambda: self._reset_button_state(save_btn, original_text))

    def _reset_button_state(self, btn, original_text):
        """버튼 상태 복구 헬퍼"""
        try:
            btn.setText(original_text)
            btn.setStyleSheet("")
            btn.setEnabled(True)
        except RuntimeError:
            # 타이머 작동 전 창이 닫히면 발생하는 에러 방지
            pass


    @pyqtSlot(dict)
    def _on_data_loaded(self, all_data: Dict[str, Any]):
        """
        ViewModel이 보내준 데이터로 UI를 채움 (Data Binding)
        """
        # self.macro_widgets에는 'Macro_1', 'Macro_2'... 키가 있음
        for macro_id, widgets in self.macro_widgets.items():
            
            # 1. 현재 매크로 ID에 해당하는 데이터 추출 (없으면 빈 딕셔너리)
            macro_data = all_data.get(macro_id, {})
            
            if not macro_data:
                continue

            # 2. 이름(Name) 채우기
            if 'name' in macro_data:
                widgets['name_input'].setText(macro_data['name'])
            
            # 3. 좌표(X, Y, Z, W, P, R) 채우기
            # 데이터는 소문자('x'), 위젯 키는 대문자('X')임에 주의
            for axis_char in ['x', 'y', 'z', 'w', 'p', 'r']:
                if axis_char in macro_data:
                    widget_key = axis_char.upper()  # 'x' -> 'X'
                    if widget_key in widgets:
                        val = float(macro_data[axis_char])
                        widgets[widget_key].setValue(val)


# ==========================================================
# 단독 실행 (테스트용)
"""
실행 명령어
python -m ui.dialogs.macro_settings_dialog
"""
# ==========================================================
if __name__ == '__main__':
    import sys
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    dialog = MacroSettingsDialog()
    dialog.exec()   # Modal로 실행
    sys.exit(0)
    