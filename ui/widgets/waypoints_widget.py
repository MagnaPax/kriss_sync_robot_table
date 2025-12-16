# ui/widgets/waypoints_widget.py

from typing import Any
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
        self._setup_table_columns()
        self._setup_table_style()

        # 조립
        group_layout.addWidget(self.table)      # 테이블 -> 그룹박스
        main_layout.addWidget(self.group_box)   # 그룹박스 -> 메인 위젯

    def _setup_table_columns(self):
        """테이블 컬럼 정의 및 헤더 설정"""
        columns = [
            "ID", "CMD", 
            "X", "Y", "Z", "W", "P", "R", 
            "T_Angle", "T_Vel", "Feed"
        ]
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)        

    def _setup_table_style(self):
        """테이블 스타일 및 동작 설정"""
        # 헤더가 남는 공간을 꽉 채움
        header = self.table.horizontalHeader()
        if header:
            header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        # 수정 불가 / 행 단위 선택
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        
        # 기타 스타일
        v_header = self.table.verticalHeader()
        if v_header:
            v_header.setVisible(False) # 행 번호 숨김
        self.table.setAlternatingRowColors(True)      # 줄무늬 배경



    def update_data(self, data: Any):
        """
        로봇과 턴테이블이 이동해야 될 경로점들의 데이터를 받아와서 UI를 업데이트한다.
        """
        # (BaseWidget의 log_prefix 사용)
        EVENT_BUS.log.message.emit(f"{self.log_prefix} 데이터 업데이트: {data}", "DEBUG")
        # TODO: 실제 웨이포인트 데이터를 받아와서 UI를 업데이트하는 로직 구현
        pass


    def clear_widget(self):
        """화면을 깨끗하게 지우고 초기화"""

        EVENT_BUS.log.message.emit(f"{self.log_prefix} 위젯 초기화", "DEBUG")
        # TODO: 웨이포인트 목록을 지우는 로직 구현
        super().clear_widget()







"""
==========================================================
Smoke Test (단독 실행용)
python -m ui.widgets.waypoints_widget
==========================================================
"""
if __name__ == '__main__':
    import sys
    from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QHBoxLayout, QPushButton
    from core.log_listener import LogListener # 로그 출력을 위해 필요

    app = QApplication(sys.argv)
    
    # 1. 로그 리스너 연결 (콘솔에 로그 찍히게)
    log_listener = LogListener()

    # 2. 메인 윈도우 생성
    win = QMainWindow()
    win.setWindowTitle("WaypointsWidget Smoke Test")
    win.resize(1000, 600) # 넉넉한 사이즈

    # 3. 레이아웃 구성
    central_widget = QWidget()
    main_layout = QVBoxLayout(central_widget)
    
    # -- 테스트할 위젯 --
    widget = WaypointsWidget()
    main_layout.addWidget(widget)

    # -- 제어 버튼들 --
    btn_layout = QHBoxLayout()
    
    btn_load = QPushButton("Load Dummy Data")
    btn_clear = QPushButton("Clear Data")
    
    btn_layout.addWidget(btn_load)
    btn_layout.addWidget(btn_clear)
    main_layout.addLayout(btn_layout)

    win.setCentralWidget(central_widget)
    win.show()

    # 4. 더미 데이터 생성
    dummy_data = [
        {'id': 1, 'cmd': 'MOVE', 'x': 100.5, 'y': 200.0, 'z': 50.0, 'w': 0, 'p': -90, 'r': 0, 'f': 100},
        {'id': 2, 'cmd': 'MOVE', 'x': 110.0, 'y': 200.0, 'z': 50.0, 'w': 0, 'p': -90, 'r': 0, 'f': 500},
        {'id': 3, 'cmd': 'MOVE', 'x': 120.0, 'y': 200.0, 'z': 60.0, 'w': 0, 'p': -90, 'r': 0, 'f': 1500},
        {'id': 4, 'cmd': 'TURN', 'angle': 45.0, 'velocity': 10.0, 'f': 0}, # 턴테이블 명령 예시
        {'id': 5, 'cmd': 'SYNC', 'x': 130.0, 'y': 210.0, 'z': 60.0, 'w': 0, 'p': -90, 'r': 0, 'angle': 90.0, 'velocity': 5.0, 'f': 200},
    ]

    # 5. 버튼 이벤트 연결 (BaseWidget 메서드 테스트)
    # safe_update_data를 사용해서 에러 처리까지 확인
    btn_load.clicked.connect(lambda: widget.safe_update_data(dummy_data))
    btn_clear.clicked.connect(widget.clear_widget)

    sys.exit(app.exec())
