# ui/widgets/waypoints_widget.py

from typing import Any, List, Dict
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QVBoxLayout, 
    QVBoxLayout, 
    QTableWidget, 
    QTableWidgetItem, 
    QHeaderView, 
    QGroupBox,
    QAbstractItemView
)

from ui.widgets.base_widget import BaseWidget
from core.event_bus import EVENT_BUS


class WaypointsWidget(BaseWidget):
    """
    로봇과 턴테이블의 이동 경로(Sequence)를 스프레드시트 형태로 보여주는 위젯
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.log_prefix = f"[{self.__class__.__name__}]"
        EVENT_BUS.log.message.emit(f"{self.log_prefix} 초기화", "DEBUG")

        # Waypoints 에서 보여줄 키(key)들의 순서를 저장할 리스트
        self.column_keys: List[str] = []

        # 이벤트 연결
        self._bind_events()


    def _init_ui(self):
        """
        부모 클래스의 메서드(BaseWidget._init_ui) 오버라이드
        """
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
        # 테이블 위젯 생성
        self.table = QTableWidget()
        self._setup_table_style()

        # 조립
        group_layout.addWidget(self.table)      # 테이블 -> 그룹박스
        main_layout.addWidget(self.group_box)   # 그룹박스 -> 메인 위젯

    def _setup_table_columns(self, data_keys: List[str]):
        """
        테이블 컬럼 정의 및 헤더 설정
            데이터에 포함된 키들을 분석하여 테이블 컬럼을 만든다. (동적으로 생성)
            보기 좋은 순서(ID -> CMD -> 좌표 -> 기타)로 정렬
        """
        # 보기 좋은 순서 정의 (우선순위 리스트)
        priority_order = [
            'id', 'cmd',                # 식별자
            'x', 'y', 'z', 'w', 'p', 'r', # 로봇 좌표
            'angle', 'velocity',        # 턴테이블
            'f'                         # 속도
        ]
        final_columns = []

        # 우선순위 리스트에 있는 키부터 먼저 담기
        for key in priority_order:
            if key in data_keys:
                final_columns.append(key)

        # 우선순위에 없는 나머지 키들(새로운 데이터 등)을 뒤에 추가
        for key in data_keys:
            if key not in final_columns:
                final_columns.append(key)

        # 멤버 변수에 저장 (나중에 데이터 채울 때 이 순서대로 채워야 함)
        self.column_keys = final_columns

        # 테이블 헤더 설정 (대문자로 변환해서 표시)
        self.table.setColumnCount(len(final_columns))
        headers = [k.upper() for k in final_columns]
        self.table.setHorizontalHeaderLabels(headers)

        # 컬럼 넓이 꽉 채우기 (Stretch)
        #   컬럼 개수가 확정된 이후에 실행해야
        header = self.table.horizontalHeader()
        if header:
            header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

    def _setup_table_style(self):
        """테이블 스타일 및 동작 설정(한 번만 설정하면 되는 것들)"""

        # 수정 불가 / 행 단위 선택
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        
        # 기타 스타일
        v_header = self.table.verticalHeader()
        if v_header:
            v_header.setVisible(False)              # 행 번호 숨김
        self.table.setAlternatingRowColors(True)    # 줄무늬 배경



    def _bind_events(self):
        # safe_update_data를 연결하면 에러 처리(try-except)까지 BaseWidget이 알아서 해준다
        EVENT_BUS.data.sequence_data_loaded.connect(self.safe_update_data)


    def update_data(self, data: List[Dict[str, Any]]):
        """
        로봇과 턴테이블이 이동해야 될 경로점들의 데이터를 받아와서 UI를 업데이트한다.
        """
        if not data:
            return

        # (BaseWidget의 log_prefix 사용)
        EVENT_BUS.log.message.emit(f"{self.log_prefix} 데이터 로드: {len(data)}건", "DEBUG")

        self.table.setRowCount(0)
        self.column_keys = [] # 초기화

        # 1. [동적 컬럼 생성] 첫 번째 데이터의 키를 기준으로 컬럼 구성
        # (모든 행의 키가 동일하다고 가정)
        first_row_keys = list(data[0].keys())
        self._setup_table_columns(first_row_keys)

        # 2. 데이터 채우기
        self.table.setSortingEnabled(False)
        
        for row_idx, row_data in enumerate(data):
            self.table.insertRow(row_idx)
            
            # [핵심] 저장해둔 컬럼 순서(self.column_keys)대로 데이터를 뽑아서 셀에 넣음
            # 더 이상 col_idx를 하드코딩하지 않음!
            for col_idx, key in enumerate(self.column_keys):

                # 데이터가 없으면 빈 문자열 ("-")
                val = row_data.get(key, "-")
                
                self._set_item(row_idx, col_idx, val)

        self.table.setSortingEnabled(True)
        self.group_box.setTitle(f"Waypoints (Total: {len(data)})")


    def clear_widget(self):
        """화면을 깨끗하게 지우고 초기화"""
        EVENT_BUS.log.message.emit(f"{self.log_prefix} 위젯 초기화", "DEBUG")

        self.table.setRowCount(0)
        self.table.setColumnCount(0) # 컬럼도 날림
        self.column_keys = []
        self.group_box.setTitle("Waypoints")
        super().clear_widget()


    def _set_item(self, row, col, value):
        """헬퍼: 값 포맷팅"""
        if isinstance(value, float):
            text = f"{value:.3f}"
        else:
            text = str(value)
            
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(row, col, item)




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
        STYLESHEET_PATH = Path("styles/stylesheet.qss")
        # 경로 문제로 임포트 실패 시 더미 함수 정의 (테스트 중단 방지)
        def load_and_apply_stylesheet(target, path):
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


