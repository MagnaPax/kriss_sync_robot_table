# ui/widgets/waypoints_widget.py

from typing import Any, List, Dict, Optional, TYPE_CHECKING
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtWidgets import (
    QApplication,
    QVBoxLayout, 
    QHBoxLayout,
    QHeaderView, 
    QGroupBox,
    QAbstractItemView,
    QTableView,
    QWidget,
    QLabel,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QStyle
)
from PyQt6.QtGui import QPainter, QPalette
from config.data_formats import TaskStatus, KEY_STATUS  # Status 상수 임포트
if TYPE_CHECKING:
    from view_models.waypoints_viewmodel import WaypointsViewModel

from core.event_bus import EVENT_BUS
from ui.widgets.base_widget import BaseWidget
from models.waypoints_table_model import WaypointsTableModel


class WaypointsDelegate(QStyledItemDelegate):
    """
    [QSS 스타일링을 위한 델리게이트]
    모델(Python Code)에 하드코딩된 색상을 제거하고, stylesheet.qss의 정의를 따르기 위해 사용
    
    Proxy Widget 기법:
        실제로는 보이지 않는 QLabel을 하나 만들어서 QSS 속성(Property)을 먹인 뒤,
        그 라벨의 Palette 색상을 훔쳐와서 테이블 셀을 그립니다.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        # 스타일 추출용 Proxy Widget
        # 부모를 지정해야 앱 전체 스타일시트(QSS)를 상속받을 수 있다
        self._proxy_label = QLabel(parent)
        self._proxy_label.setVisible(False)
        self._proxy_label.setAutoFillBackground(True) # Palette에 배경색이 반영되도록 설정
        self._proxy_label.setProperty("usage", "waypoint_result") # QSS 선택자용

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        # 1. 원본 데이터 가져오기 (DisplayRole)
        text = index.data(Qt.ItemDataRole.DisplayRole)
        
        # 2. 'status' 컬럼 데이터 정규화
        status_str = str(text).lower().strip()

        # 3. 상태 정규화 (QSS 속성값 결정을 위해 매핑)
        qss_status = TaskStatus.PENDING
        
        # 동의어 처리 및 매핑
        if status_str in [TaskStatus.PROCESSING, "process", "running"]:
            qss_status = TaskStatus.PROCESSING
        elif status_str in [TaskStatus.COMPLETED, "processed", "success", "done"]:
            qss_status = TaskStatus.COMPLETED
        elif status_str in [TaskStatus.FAILED, "fail", "error", "alarm"]:
            qss_status = TaskStatus.FAILED
        elif status_str in [TaskStatus.PENDING, "wait", "unprocessed", "-"]:
            qss_status = TaskStatus.PENDING

        # 4. Proxy Widget에 속성 설정 및 스타일 폴리싱(Polishing)
        #    Property 변경 후 반드시 unpolish -> polish 과정을 거쳐야 QSS가 재계산된다
        self._proxy_label.setProperty("status", qss_status)
        style = self._proxy_label.style()
        style.unpolish(self._proxy_label)
        style.polish(self._proxy_label)
        
        # 5. QSS가 적용된 라벨에서 배경색 및 글자색 추출
        bg_color = self._proxy_label.palette().color(QPalette.ColorRole.Window)
        text_color = self._proxy_label.palette().color(QPalette.ColorRole.WindowText)
        
        # 6. 그리기 (Drawing)
        #    선택된 행(Selected): 기본 스타일(super)에 위임하여 하이라이트 처리 유지
        #    일반 행(Normal): QSS가 적용된 배경색과 글자색으로 직접 그림 (super 호출 시 QSS 배경색 덮어쓰기 방지)
        if option.state & QStyle.StateFlag.State_Selected:
            # 선택된 상태일 때는 그냥 기본 동작 (선택색 #C7DBF8 사용)
            super().paint(painter, option, index)
        else:
            # 1) 배경 그리기
            painter.fillRect(option.rect, bg_color)
            
            # 2) 글자 그리기
            painter.save()
            painter.setPen(text_color)
            # 텍스트 중앙 정렬
            painter.drawText(option.rect, Qt.AlignmentFlag.AlignCenter, status_str)
            painter.restore()


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
        self.vm: Optional["WaypointsViewModel"] = None

    def set_view_model(self, view_model: "WaypointsViewModel"):
        """외부에서 뷰모델을 주입"""
        self.vm = view_model
        
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

        # --- 스프레드시트 컨테이너 (좌우 분할) --- #
        table_container = QWidget()
        table_container.setObjectName("waypoints_container") # 스타일링용 ID 부여
        table_layout = QHBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(0) # 두 테이블 사이 간격 제거

        # 1. 고정 테이블 (좌측: ID 보여주기용)
        self.frozen_table_view = QTableView()
        self.frozen_table_view.setObjectName("frozen_table")
        
        # 2. 메인 테이블 (우측: 나머지 데이터)
        self.table_view = QTableView()
        
        # 모델 생성 및 연결 (하나의 모델을 공유!)
        self.model = WaypointsTableModel()
        self.frozen_table_view.setModel(self.model)
        self.table_view.setModel(self.model)
        
        # 선택 모델 공유 (Row 선택 시 같이 선택됨)
        self.frozen_table_view.setSelectionModel(self.table_view.selectionModel())

        # 스타일 및 동작 설정
        self._setup_table_style()
        
        # 스크롤바 동기화
        # 메인 테이블의 스크롤바가 움직이면 -> 고정 테이블도 같이 움직임
        self.table_view.verticalScrollBar().valueChanged.connect(
            self.frozen_table_view.verticalScrollBar().setValue
        )
        self.frozen_table_view.verticalScrollBar().valueChanged.connect(
            self.table_view.verticalScrollBar().setValue
        )

        # 델리게이트 설정 (Result 컬럼 스타일링)
        # 주의: Result 컬럼이 항상 0번이라고 가정 (모델에서 insert(0) 했음)
        self.delegate = WaypointsDelegate(self.table_view)
        # 메인 테이블에만 적용하면 됨 (ID 컬럼엔 스타일 필요 없으므로)
        # 하지만 update_data에서 동적으로 적용하므로 여기서는 패스

        # 조립
        table_layout.addWidget(self.frozen_table_view)
        table_layout.addWidget(self.table_view)
        
        group_layout.addWidget(table_container) # 컨테이너 -> 그룹박스
        main_layout.addWidget(self.group_box)   # 그룹박스 -> 메인 위젯

        # 사용자의 행 선택이 바뀌면(마우스, 키보드) 실행된다
        if (selection_model := self.table_view.selectionModel()) is not None:
            selection_model.selectionChanged.connect(self._on_row_selected)

    def _bind_events(self):
        if not self.vm: return

        # VM의 데이터 갱신 시그널 구독
        self.vm.waypoints_data_changed.connect(self.safe_update_data)
        
        # VM의 초기화 요청 시그널 구독
        self.vm.clear_waypoints.connect(self.clear_widget)

        # VM의 진행률 업데이트 시그널 구독
        self.vm.progress_changed.connect(self._on_progress_updated)

    # =========================================
    # UI 구성 및 동적 스타일 
    #   - 테이블 컬럼/헤더 설정, 폰트 크기 조절
    # =========================================
    def _setup_table_style(self):
        """테이블 스타일 및 동작 설정"""

        for tv in [self.frozen_table_view, self.table_view]:
            # 공통 설정
            tv.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            tv.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            tv.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
            tv.setAlternatingRowColors(False) # 모든 행의 배경색 통일
            
            # 수직 헤더(행 번호) 숨김
            if (v_header := tv.verticalHeader()) is not None:
                v_header.setVisible(False)

        # --- 고정 테이블 전용 설정 ---
        self.frozen_table_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff) # 가로 스크롤바 제거
        self.frozen_table_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)   # 세로 스크롤바 제거 (메인에 의존)
        self.frozen_table_view.setFixedWidth(60) # ID 컬럼 너비만큼 고정 (나중에 동적으로 조절 가능)
        self.frozen_table_view.setFocusPolicy(Qt.FocusPolicy.NoFocus) # 포커스 뺏어가지 않도록

        # --- 메인 테이블 전용 설정 ---
        self.table_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # 헤더 설정
        if (h_header := self.table_view.horizontalHeader()) is not None:
            h_header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents) 
            h_header.setStretchLastSection(True)
            
        if (fh_header := self.frozen_table_view.horizontalHeader()) is not None:
            fh_header.setSectionResizeMode(QHeaderView.ResizeMode.Fixed) # 고정 너비


    # ===============================================
    # 데이터 처리 (Core Logic)
    #   - 외부 데이터를 받아와 UI에 반영하거나 초기화
    # ===============================================
    def update_data(self, data: List[Dict[str, Any]]):
        """
        로봇과 턴테이블이 이동해야 될 경로점들의 데이터를 받아와서 UI를 업데이트한다.
        """
        if not data: return

        # UI 갱신을 위해 잠시 대기
        QApplication.processEvents()

        try:
            # 모델에게 데이터 전달
            self.model.set_data(data)

            # --- 컬럼 숨김/보임 처리 (핵심) ---
            # 1. 고정 테이블: 0번 컬럼(ID) 빼고 다 숨김
            for col in range(1, self.model.columnCount()):
                self.frozen_table_view.setColumnHidden(col, True)
            self.frozen_table_view.setColumnWidth(0, 60) # ID 컬럼 너비

            # 2. 메인 테이블: 0번 컬럼(ID) 숨김
            self.table_view.setColumnHidden(0, True)

            # [Delegate 재설정] Status 컬럼 찾기
            status_col_idx = -1
            col_count = self.model.columnCount()
            for col in range(col_count):
                header_text = self.model.headerData(col, Qt.Orientation.Horizontal).lower()
                if header_text == KEY_STATUS:
                    status_col_idx = col
                    break
            
            if status_col_idx != -1:
                # 메인 테이블의 해당 컬럼에만 Delegate 적용
                self.table_view.setItemDelegateForColumn(status_col_idx, self.delegate)
            else:
                self.table_view.setItemDelegateForColumn(1, self.delegate)


            self.group_box.setTitle(f"Waypoints (Total: {len(data)})")
            
        except Exception as e:
            EVENT_BUS.log.message.emit(f"{self.log_prefix} 데이터 렌더링 중 에러: {e}", "ERROR")
            
        finally:
            EVENT_BUS.system.loading_finished.emit()
            EVENT_BUS.log.message.emit(f"{self.log_prefix} 데이터 렌더링 완료 {len(data)}건", "INFO")


    def clear_widget(self):
        """화면을 깨끗하게 지우고 초기화"""
        EVENT_BUS.log.message.emit(f"{self.log_prefix} 위젯 초기화", "DEBUG")

        self.model.set_data([]) 
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

        idx = indexes[0]
        row = idx.row()
        row_data = self.model.get_row_data(row)

        if row_data:
            EVENT_BUS.data.waypoints_selected.emit(row_data)
            EVENT_BUS.log.message.emit(f"{self.log_prefix} 사용자가 선택한 행({row}): {row_data['id']}", "DEBUG")

    @pyqtSlot(int, int, str)
    def _on_progress_updated(self, step: int, total: int, status: str):
        """
        [실시간 시각화] 로봇이 이동 중일 때 호출됨
        """
        
        # 1. UI용 Row Index 변환 (1-based -> 0-based)
        row = step - 1
        
        # 2. 모델 상태 업데이트
        self.model.update_status(row, status)

        # 3. [UX] 현재 실행 중인 행 강조 및 자동 스크롤
        #    '처리 중'이거나 '처리 완료' 되었을 때 해당 행을 보여준다
        if row >= 0:
            # 해당 행 선택 (파란색 하이라이트)
            self.table_view.selectRow(row)
            
            # 해당 행이 화면 중앙에 오도록 자동 스크롤
            index = self.model.index(row, 0)
            if index.isValid():
                # 두 테이블 모두 스크롤 (시그널로 연결되어 있음)
                self.table_view.scrollTo(index, QAbstractItemView.ScrollHint.PositionAtCenter)
                
                # 강제로 중앙 정렬 보정 (가끔 PositionAtCenter가 밀리는 현상 방지)
                # 특히 데이터가 추가되거나 빠르게 변할 때 유용함
                self.frozen_table_view.scrollTo(index, QAbstractItemView.ScrollHint.PositionAtCenter)





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
