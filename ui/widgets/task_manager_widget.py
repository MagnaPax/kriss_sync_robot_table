# ui/widgets/task_manager_widget.py
from pathlib import Path
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtWidgets import (
    QVBoxLayout, 
    QGroupBox, 
    QLabel, 
    QHBoxLayout, 
    QPushButton,
    QFileDialog
)
from ui.widgets.base_widget import BaseWidget
from core.event_bus import EVENT_BUS
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from view_models.task_manager_viewmodel import TaskManagerViewModel




class TaskManagerWidget(BaseWidget):
    """Sequence 파일 불러오기"""

    def __init__(self, view_model: "TaskManagerViewModel", parent=None):
        """Sequence 파일 로드 및 실행 제어 위젯"""

        # UI 요소 참조 변수 초기화
        self.lbl_feed_val = None
        self.lbl_runtime_val = None
        self.btn_load = None
        self.lbl_filename = None
        self.btn_start = None
        self.btn_stop = None

        self.vm = view_model

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
        group_layout.setContentsMargins(15, 10, 15, 15)


        # --- 정보 표시 (Feed Rate, Runtime) --- #
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
        
        # 그룹 레이아웃의 맨 위에 추가
        group_layout.addLayout(info_layout)

        # 상단과 하단을 벌려주는 스프링
        # info_layout은 위로, bottom_layout은 아래로
        group_layout.addStretch(1)

        # 1. file_layout와 control_layout를 좌우로 나란히 놓기 위한 부모 레이아웃
        bottom_layout = QHBoxLayout()


        # --- 2. 왼쪽: 파일 로드 (LOAD 버튼 + 파일명) --- #
        file_layout = QHBoxLayout()
        
        # LOAD 버튼
        self.btn_load = QPushButton("LOAD")
        self.btn_load.setFixedSize(60, 30)
        self.btn_load.setProperty("type", "general") # 공통 보라색 버튼 스타일 적용

        # 파일명 레이블
        self.lbl_filename = QLabel("FileName...")
        self.lbl_filename.setObjectName("filename_label")
        
        # 배치: LOAD버튼 - (간격) - 파일명 - (스프링)
        file_layout.addWidget(self.btn_load)
        file_layout.addSpacing(15)
        file_layout.addWidget(self.lbl_filename)
        file_layout.addStretch(1) # 왼쪽 정렬 유지


        # --- 3. 오른쪽: 제어 버튼 (START, STOP) --- #
        control_layout = QHBoxLayout()
        
        # START 버튼
        self.btn_start = QPushButton("START")
        self.btn_start.setFixedSize(70, 30)
        self.btn_start.setProperty("type", "general")

        # STOP 버튼
        self.btn_stop = QPushButton("STOP")
        self.btn_stop.setFixedSize(70, 30)
        self.btn_stop.setProperty("type", "general")

        # 배치: (스프링) - START - (간격) - STOP
        control_layout.addStretch(1) # 우측 정렬 효과
        control_layout.addWidget(self.btn_start)
        control_layout.addSpacing(10)
        control_layout.addWidget(self.btn_stop)

        # 4. bottom_layout 안에 file_layout과 control_layout을 좌우로 배치
        bottom_layout.addLayout(file_layout)
        bottom_layout.addLayout(control_layout)

        # bottom_layout를 그룹 레이아웃에 추가
        group_layout.addLayout(bottom_layout)

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

        # Pylance 경고 해결 위해 if문 추가
        """

        if self.btn_load: self.btn_load.clicked.connect(self._on_load_clicked)      # LOAD 연결
        if self.btn_start: self.btn_start.clicked.connect(self._on_start_clicked)   # START 연결
        if self.btn_stop: self.btn_stop.clicked.connect(self._on_stop_clicked)      # STOP 연결




    # --- 슬롯 메서드 [반응] 이벤트 발생했다는 신호 수신 -> _handle 메서드에 일 시키자 ---
    @pyqtSlot()
    def _on_load_clicked(self):
        self._handle_load_file_button_clicked()

    @pyqtSlot()
    def _on_start_clicked(self):
        self._handle_start_button_clicked()

    @pyqtSlot()
    def _on_stop_clicked(self):
        print("STOP 버튼 클릭됨")


    # --- [처리] UI 차원에서 해야 할 일 --- #
    @pyqtSlot()
    def _handle_load_file_button_clicked(self):
        """ 
        'LOAD' 버튼이 클릭되면 
            1. 파일을 선택 다이얼로그 표시
            2. 선택된 파일이름 표시
            3. 선택된 파일 VM에 전달
        """
        # QFileDialog를 사용하여 문자열 경로 획득
        file_path_str, _ = QFileDialog.getOpenFileName(
            self,                   # 부모 위젯
            "시퀀스 파일 선택",     # 다이얼로그 제목
            "/",                    # 다이얼로그 창에서 처음 열어볼 디렉토리
            "시퀀스 파일 (*.csv)"   # 파일 필터
        )
        
        if file_path_str:
            # 문자열 경로를 pathlib.Path 객체로 변환
            file_path_obj = Path(file_path_str)

            if self.lbl_filename:
                self.lbl_filename.setText(file_path_obj.name)

            EVENT_BUS.log.message.emit(f"파일 선택됨: {file_path_obj}", "INFO")
            
            # Path 객체를 VM의 슬롯으로 전달
            self.vm.load_sequence_data(file_path_obj)

        else:
            EVENT_BUS.log.message.emit("파일 선택이 취소되었습니다.", "INFO")

    def _handle_start_button_clicked(self):
        """
        START 버튼 클릭 시: 파일이 로드되었는지 확인하고 VM에 시퀀스 시작을 요청
        """
        # 방어 코드 - 읽은 파일이 없으면 뷰모델 호출 안 함
        if self.lbl_filename is None or self.lbl_filename.text() == "FileName..." or not self.lbl_filename.text(): return

        EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] START 버튼 클릭됨 - 작업 시작 요청", "INFO")

        self.vm.start_sequence()







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
    from core.log_listener import LogListener

        # [중요] DLL 로드
    from utils.dll_loader import load_pyads_dll
    try:
        load_pyads_dll()
        print("✅ DLL 로드 완료")
    except Exception as e:
        print(f"⚠️ DLL 로드 실패: {e}")

    from view_models.task_manager_viewmodel import TaskManagerViewModel
    from services.sequence_service import SequenceService


    app = QApplication(sys.argv)

    listener = LogListener()

    service = SequenceService()
    vm = TaskManagerViewModel(service)


    # 스타일시트 파일 로드 및 적용
    load_and_apply_stylesheet(app, STYLESHEET_PATH)

    # 윈도우 생성 및 테스트
    window = TaskManagerWidget(vm)
    window.resize(450, 200) # 요청하신 비율을 확인하기 적당한 크기
    window.show()

    sys.exit(app.exec())