# ui/widgets/task_manager_widget.py
from ui.widgets.base_widget import BaseWidget
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


class TaskManagerWidget(BaseWidget):
    """Sequence 파일 불러오기"""

    def __init__(self, parent=None):
        """Sequence 파일 로드 및 실행 제어 위젯"""

        # UI 요소 참조 변수 초기화
        self.lbl_feed_val = None
        self.lbl_runtime_val = None
        self.btn_load = None
        self.lbl_filename = None
        self.btn_start = None
        self.btn_stop = None

        # BaseWidget의 __init__()이 _init_ui() 호출 → 실제 UI 생성
        super().__init__(parent)

        # 이벤트 연결 (UI만들어진 뒤)
        self._bind_events()        

    def _init_ui(self):

        # 메인 레이아웃 및 그룹박스 설정
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        self.setObjectName("task_manager_widget")   # 전체 위젯 ID

        # 그룹박스 생성
        base_group_box = QGroupBox("Task Manager")
        # 그룹박스 내부 레이아웃 (세로 정렬)
        group_layout = QVBoxLayout(base_group_box)
        group_layout.setSpacing(10)                 # 각 구역 사이의 간격
        group_layout.setContentsMargins(15, 20, 15, 15)


        # [1분위] 공백
        # 상단에 여백을 주어 정보창과 버튼들이 아래쪽에 위치하도록 함
        group_layout.addStretch(1)


        # [2분위] 정보 표시 (Feed Rate, Runtime)
        info_layout = QHBoxLayout()
        
        # Feed Rate 레이블 
        lbl_feed_title = QLabel("Feed(mm / sec) :")
        lbl_feed_title.setObjectName("info_title")  # QSS 식별용 ID
        self.lbl_feed_val = QLabel("30")
        self.lbl_feed_val.setObjectName("info_value")
        
        # Runtime 레이블 
        lbl_runtime_title = QLabel("Runtime :")
        lbl_runtime_title.setObjectName("info_title")
        self.lbl_runtime_val = QLabel("00 : 00 : 00")
        self.lbl_runtime_val.setObjectName("info_value")

        # 배치: (공백) - Feed - (간격) - Runtime
        info_layout.addStretch(1) # 우측 정렬 효과
        info_layout.addWidget(lbl_feed_title)
        info_layout.addWidget(self.lbl_feed_val)
        info_layout.addSpacing(20)
        info_layout.addWidget(lbl_runtime_title)
        info_layout.addWidget(self.lbl_runtime_val)
        
        group_layout.addLayout(info_layout)


        # [3분위] 파일 로드 (LOAD 버튼 + 파일명)
        file_layout = QHBoxLayout()
        
        # LOAD 버튼
        self.btn_load = QPushButton("LOAD")
        self.btn_load.setFixedSize(60, 30)
        self.btn_load.setProperty("type", "general") # 공통 보라색 버튼 스타일 적용

        # 파일명 레이블
        self.lbl_filename = QLabel("FileName...")
        self.lbl_filename.setObjectName("filename_label")
        
        # 배치: LOAD버튼 - (간격) - 파일명 - (나머지 공백)
        file_layout.addWidget(self.btn_load)
        file_layout.addSpacing(15)
        file_layout.addWidget(self.lbl_filename)
        file_layout.addStretch(1) # 왼쪽 정렬 유지

        group_layout.addLayout(file_layout)


        # [4분위] 제어 버튼 (START, STOP) - 우측 정렬
        control_layout = QHBoxLayout()
        
        # START 버튼
        self.btn_start = QPushButton("START")
        self.btn_start.setFixedSize(70, 30)
        self.btn_start.setProperty("type", "general")

        # STOP 버튼
        self.btn_stop = QPushButton("STOP")
        self.btn_stop.setFixedSize(70, 30)
        self.btn_stop.setProperty("type", "general")

        # 배치: (공백) - START - (간격) - STOP
        control_layout.addStretch(1) # 우측 정렬 효과
        control_layout.addWidget(self.btn_start)
        control_layout.addSpacing(10)
        control_layout.addWidget(self.btn_stop)

        group_layout.addLayout(control_layout)


        # 전체 레이아웃에 그룹박스 추가
        main_layout.addWidget(base_group_box)

    def update_data(self, data):
        """데이터 업데이트 (BaseWidget 구현)"""
        pass


    # ==========================================================
    # 이벤트 발생 시 동작 약속
    # ==========================================================
    def _bind_events(self):
        """
        전선 연결하기 (아직 불 들어온것 아님)
            - 누가 누구랑 연결될 지 미리 정해주기
            - 앱이 시작될 때 딱 1번만 호출
        시그널-슬롯(_on으로 시작하는 메서드) connect를 모아놓음 - 버튼 눌리면 어떤 일을 할 지 약속
        """

        if self.btn_load: self.btn_load.clicked.connect(self._on_load_clicked)
        if self.btn_start: self.btn_start.clicked.connect(self._on_start_clicked)
        if self.btn_stop: self.btn_stop.clicked.connect(self._on_stop_clicked)



    # --- 슬롯 (추후 구현) ---
    @pyqtSlot()
    def _on_load_clicked(self):
        print("LOAD 버튼 클릭됨")

    @pyqtSlot()
    def _on_start_clicked(self):
        print("START 버튼 클릭됨")

    @pyqtSlot()
    def _on_stop_clicked(self):
        print("STOP 버튼 클릭됨")




# ==========================================================
# Smoke Test
"""
python -m ui.widgets.task_manager_widget
"""
# ==========================================================
if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication

    from config.paths import STYLESHEET_PATH
    from styles.style_manager import load_and_apply_stylesheet

    app = QApplication(sys.argv)

    # 스타일시트 파일 로드 및 적용
    load_and_apply_stylesheet(app, STYLESHEET_PATH)

    # 윈도우 생성 및 테스트
    window = TaskManagerWidget()
    window.resize(450, 200) # 요청하신 비율을 확인하기 적당한 크기
    window.show()

    sys.exit(app.exec())