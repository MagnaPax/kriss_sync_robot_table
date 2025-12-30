# ui/widgets/waypoints_widget.py

from typing import Any, List, Dict, Optional
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtWidgets import (
    QApplication,
    QVBoxLayout, 
    QHeaderView, 
    QGroupBox,
    QAbstractItemView,
    QTableView,
    QWidget
)

from core.event_bus import EVENT_BUS
from ui.widgets.base_widget import BaseWidget
from models.waypoints_table_model import WaypointsTableModel


class WaypointsWidget(BaseWidget):
    """
    로봇과 턴테이블의 이동 경로(Sequence)를 스프레드시트 형태로 보여주는 위젯
    """

    # ========================================
    # 초기화 및 설정 (Initialization)
    #   - 위젯 생성, UI 기본 설정, 이벤트 연결
    # ========================================
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        # 이벤트 연결
        self._bind_events()

    def _init_ui(self):
        """부모 클래스의 메서드(BaseWidget._init_ui) 오버라이드"""

        self.setObjectName("waypoints_widget")

        # 메인 레이아웃 (위젯 전체)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)  # 패널에 딱 붙게 하기 위해 외부 여백 제거

        # --- 그룹박스 --- #
        self.group_box = QGroupBox("Waypoints")
        self.group_box.setObjectName("waypoints_groupbox") # QSS 스타일링용 ID
        # 그룹박스 내부 레이아웃
        group_layout = QVBoxLayout(self.group_box)
        group_layout.setContentsMargins(5, 15, 5, 5) # 상단 여백은 제목 공간 확보

        # --- 스프레드시트 --- #
        # 테이블 뷰 생성
        self.table_view = QTableView()
        # 모델 생성 및 연결
        self.model = WaypointsTableModel()
        self.table_view.setModel(self.model)
        # 스타일 설정
        self._setup_table_style()

        # 조립
        group_layout.addWidget(self.table_view) # 테이블 -> 그룹박스
        main_layout.addWidget(self.group_box)   # 그룹박스 -> 메인 위젯

        # 사용자의 행 선택이 바뀌면(마우스, 키보드) 실행된다
        #   := (왈러스 연산자): 변수에 selectionModel()의 반환값을 할당함과 동시에
        #       그 값을 if 조건문에서 바로 사용할 수 있게 해준다
        if (selection_model := self.table_view.selectionModel()) is not None:
            selection_model.selectionChanged.connect(self._on_row_selected)

    def _bind_events(self):
        # safe_update_data를 연결하면 에러 처리(try-except)까지 BaseWidget이 알아서 해준다
        EVENT_BUS.data.sequence_data_loaded.connect(self.safe_update_data)



    # =========================================
    # UI 구성 및 동적 스타일 
    #   - 테이블 컬럼/헤더 설정, 폰트 크기 조절
    # =========================================
    def _setup_table_style(self):
        """테이블 스타일 및 동작 설정(한 번만 설정하면 되는 것들)"""

        # 수정 불가 / 행 단위 선택 / 단일 선택
        self.table_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table_view.setAlternatingRowColors(True)
        
        # 헤더 설정
        if (h_header := self.table_view.horizontalHeader()) is not None:
            h_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch) # 컬럼 너비 꽉 채우기
        
        if (v_header := self.table_view.verticalHeader()) is not None:
            v_header.setVisible(False) # 행 번호 숨김



    # ===============================================
    # 데이터 처리 (Core Logic)
    #   - 외부 데이터를 받아와 UI에 반영하거나 초기화
    # ===============================================
    def update_data(self, data: List[Dict[str, Any]]):
        """
        로봇과 턴테이블이 이동해야 될 경로점들의 데이터를 받아와서 UI를 업데이트한다.
        """
        if not data: return

        # EVENT_BUS.log.message.emit(f"{self.log_prefix} 데이터 로드: {len(data)}건\n받은데이터\n{data}", "DEBUG")

        # 마우스 커서를 '대기 상태(모래시계)'로 변경
        #   앱이 멈춘 동안에 OS가 알아서 뺑뺑이 돌려줌
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

        try:
            # --- [대용량 데이터 처리 시 이 구간에서 0.x초 멈춤 발생] ---
            # 모델에게 데이터 전달 (여기서 beginResetModel이 호출되며 화면 갱신됨)
            self.model.set_data(data)

            self.group_box.setTitle(f"Waypoints (Total: {len(data)})")
        finally:
            # 작업이 끝나면(성공하든 실패하든) 커서를 원래대로 복구
            QApplication.restoreOverrideCursor()
            
            # 완료 메시지
            EVENT_BUS.log.message.emit(f"{self.log_prefix} 데이터 렌더링 완료", "INFO")

    def clear_widget(self):
        """화면을 깨끗하게 지우고 초기화"""
        EVENT_BUS.log.message.emit(f"{self.log_prefix} 위젯 초기화", "DEBUG")

        self.model.set_data([]) # 빈 리스트 전달 -> 초기화
        self.group_box.setTitle("Waypoints")
        super().clear_widget()


    # ===============================================
    # 이벤트 핸들러 (Slots)
    #   - 사용자 입력(클릭, 선택)에 대한 반응 처리
    # ===============================================
    @pyqtSlot()
    def _on_row_selected(self):
        """사용자가 스프레드시트의 행을 선택 했을 때 실행"""

        # 현재 선택된 인덱스 가져오기
        if (selection_model := self.table_view.selectionModel()) is None: return
        indexes = selection_model.selectedRows()
        if not indexes: return

        # 첫 번째 선택된 행의 인덱스
        idx = indexes[0]
        row = idx.row()

        # Model에게 해당 행의 '진짜 데이터'를 달라고 요청
        row_data = self.model.get_row_data(row)

        if row_data:
            # 이벤트 버스에 실어서 방송 송출
            EVENT_BUS.data.waypoints_selected.emit(row_data)
            EVENT_BUS.log.message.emit(f"{self.log_prefix} 사용자가 선택한 행({row}): {row_data['id']}", "DEBUG")





"""
==========================================================
Smoke Test (단독 실행용)
python -m ui.widgets.waypoints_widget
==========================================================
"""
if __name__ == '__main__':
    import sys
    from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QPushButton, QVBoxLayout
    from core.log_listener import LogListener
    from core.event_bus import EVENT_BUS
    
    # [추가] 스타일 매니저 임포트
    # (주의: 프로젝트 루트에서 실행해야 경로를 찾을 수 있음: python -m ui.widgets.waypoints_widget)
    try:
        from config.paths import STYLESHEET_PATH
        from styles.style_manager import load_and_apply_stylesheet
    except ImportError:
        from pathlib import Path
        STYLESHEET_PATH = Path("styles/stylesheet.qss") # type: ignore
        # 경로 문제로 임포트 실패 시 더미 함수 정의 (테스트 중단 방지)
        def load_and_apply_stylesheet(target: Any, path: Any):
            print("⚠️ 스타일 매니저를 찾을 수 없어 스타일이 적용되지 않았습니다.")


    app = QApplication(sys.argv)
    load_and_apply_stylesheet(app, STYLESHEET_PATH)
    log_listener = LogListener()

    win = QMainWindow()
    win.setWindowTitle("WaypointsWidget Signal Test")
    win.resize(1000, 600)

    central_widget = QWidget()
    main_layout = QVBoxLayout(central_widget)
    main_layout.setContentsMargins(20, 20, 20, 20)
    
    # 위젯 생성 (내부에서 _bind_events()가 실행되어 리스닝 상태가 됨)
    widget = WaypointsWidget()
    main_layout.addWidget(widget)

    # 테스트 버튼들
    btn_layout = QVBoxLayout()
    
    # 버튼 1: 기존 방식 (직접 주입)
    btn_direct = QPushButton("1. 직접 주입 (Direct Call)")
    btn_direct.setProperty("type", "general")
    
    # 버튼 2: 시그널 방식 (방송 송출)
    btn_signal = QPushButton("2. 시그널 방송 (Emit Signal)")
    btn_signal.setProperty("type", "special")  # 파란색 강조
    
    btn_clear = QPushButton("Clear")

    btn_layout.addWidget(btn_direct)
    btn_layout.addWidget(btn_signal)
    btn_layout.addWidget(btn_clear)
    main_layout.addLayout(btn_layout)

    win.setCentralWidget(central_widget)
    win.show()

    # 더미 데이터
    dummy_data = [
        {'id': 1, 'cmd': 'MOVE', 'x': 100.123, 'y': 200.0, 'z': 50.0, 'f': 100},
        {'id': 2, 'cmd': 'TURN', 'angle': 45.0, 'velocity': 10.0},
        {'id': 3, 'cmd': 'SYNC', 'x': 150.0, 'angle': 90.0, 'f': 200},
    ]

    # --- [핵심] 이벤트 연결 ---
    
    # 1. 직접 주입 버튼: 위젯의 메서드를 직접 호출
    btn_direct.clicked.connect(lambda: widget.safe_update_data(dummy_data))
    
    # 2. 시그널 버튼: 이벤트 버스에 방송만 함 (위젯을 직접 건드리지 않음)
    #    위젯이 _bind_events에서 잘 연결했다면, 이 버튼을 눌렀을 때 표가 채워져야 함
    btn_signal.clicked.connect(
        lambda: EVENT_BUS.data.sequence_data_loaded.emit(dummy_data)
    )

    btn_clear.clicked.connect(widget.clear_widget)

    sys.exit(app.exec())
