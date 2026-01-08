# ui/widgets/waypoints_widget.py

from typing import Any, List, Dict, Optional, TYPE_CHECKING
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtWidgets import (
    QApplication,
    QVBoxLayout, 
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
        self._proxy_label = QLabel()
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
        #    주의: Property 변경 후 반드시 unpolish -> polish 과정을 거쳐야 QSS가 재계산됨
        self._proxy_label.setProperty("status", qss_status)
        style = self._proxy_label.style()
        style.unpolish(self._proxy_label)
        style.polish(self._proxy_label)
        
        # 5. QSS가 적용된 라벨에서 배경색 및 글자색 추출
        bg_color = self._proxy_label.palette().color(QPalette.ColorRole.Window)
        text_color = self._proxy_label.palette().color(QPalette.ColorRole.WindowText)
        
        # 6. 배경 칠하기 (선택된 행이 아닐 때만 커스텀 배경 적용)
        #    선택된 행은 QSS의 selection-background-color가 우선순위를 가짐
        if not (option.state & QStyle.StateFlag.State_Selected):
            painter.fillRect(option.rect, bg_color)

        # 7. 옵션의 팔레트 교체 (글자색 적용)
        option.palette.setColor(QPalette.ColorRole.Text, text_color)
        
        super().paint(painter, option, index)


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

        # --- 스프레드시트 --- #
        # 테이블 뷰 생성
        self.table_view = QTableView()
        # 모델 생성 및 연결
        self.model = WaypointsTableModel()
        self.table_view.setModel(self.model)
        # 스타일 설정
        self._setup_table_style()
        
        # 델리게이트 설정 (Result 컬럼 스타일링)
        # 주의: Result 컬럼이 항상 0번이라고 가정 (모델에서 insert(0) 했음)
        self.delegate = WaypointsDelegate(self.table_view)
        self.table_view.setItemDelegateForColumn(0, self.delegate)

        # 조립
        group_layout.addWidget(self.table_view) # 테이블 -> 그룹박스
        main_layout.addWidget(self.group_box)   # 그룹박스 -> 메인 위젯

        # 사용자의 행 선택이 바뀌면(마우스, 키보드) 실행된다
        #   := (왈러스 연산자): 변수에 selectionModel()의 반환값을 할당함과 동시에
        #       그 값을 if 조건문에서 바로 사용할 수 있게 해준다
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
        """테이블 스타일 및 동작 설정(한 번만 설정하면 되는 것들)"""

        # 수정 불가 / 행 단위 선택 / 단일 선택
        self.table_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table_view.setAlternatingRowColors(True)
        
        self.table_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded) # 가로 스크롤바 활성화

        # 헤더 설정
        if (h_header := self.table_view.horizontalHeader()) is not None:
            # ResizeMode.Stretch: 모든 컬럼을 화면 너비에 억지로 맞춤 (스크롤바 안 생김)
            # ResizeMode.Interactive: 사용자가 조절 가능 + 내용물 많으면 스크롤바 생김
            h_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive) 
            h_header.setStretchLastSection(True) # 마지막 컬럼은 남은 공간 채우기
        
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

        # UI 갱신을 위해 잠시 대기 (다이얼로그가 뜨자마자 멈추는 것 방지)
        QApplication.processEvents()

        try:
            # --- [대용량 데이터 처리: 이 구간에서 UI 메인 스레드 멈춤 발생] ---
            # 모델에게 데이터 전달 (여기서 beginResetModel이 호출되며 화면 갱신됨)
            # 수천 건의 데이터를 QTableView에 그리는 작업은 메인 스레드에서만 가능하므로 어쩔 수 없이 블로킹됨
            self.model.set_data(data)

            # [Delegate 재설정] 데이터 로드 후 컬럼 순서가 바뀔 수 있으므로, Status 컬럼을 찾아 Delegate를 다시 걸어준다.
            # 모델의 headerData를 사용하여 Status 컬럼의 인덱스를 찾는다.
            status_col_idx = -1
            col_count = self.model.columnCount()
            for col in range(col_count):
                header_text = self.model.headerData(col, Qt.Orientation.Horizontal).lower()
                if header_text == KEY_STATUS:
                    status_col_idx = col
                    break
            
            if status_col_idx != -1:
                # 찾았으면 해당 컬럼에만 Delegate 적용
                self.table_view.setItemDelegateForColumn(status_col_idx, self.delegate)
            else:
                # 못 찾았으면 (혹시 모르니) 1번 컬럼에 적용 (기본값)
                self.table_view.setItemDelegateForColumn(1, self.delegate)


            self.group_box.setTitle(f"Waypoints (Total: {len(data)})")
            
        except Exception as e:
            EVENT_BUS.log.message.emit(f"{self.log_prefix} 데이터 렌더링 중 에러: {e}", "ERROR")
            
        finally:
            # 로딩 완료 방송 ('파일 읽는 중...' 다이얼로그 닫기)
            EVENT_BUS.system.loading_finished.emit()
            
            # 완료 메시지
            EVENT_BUS.log.message.emit(f"{self.log_prefix} 데이터 렌더링 완료 {len(data)}건", "INFO")


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

    @pyqtSlot(int, int, str)
    def _on_progress_updated(self, step: int, total: int, status: str):
        """
        [실시간 시각화] 로봇이 이동 중일 때 호출됨
        
        Args:
            step (int): 현재 스텝 (1부터 시작)
            total (int): 전체 스텝 수
            status (str): 진행 상태 ('processed', 'processing', 'unprocessed')
        """
        
        # 1. UI용 Row Index 변환 (1-based -> 0-based)
        row = step - 1
        
        # 2. 모델 상태 업데이트 (글자색 변경 등)
        self.model.update_status(row, status)

        # 3. [UX] 현재 실행 중인 행 강조 및 자동 스크롤
        #    '처리 중'이거나 '처리 완료' 되었을 때 해당 행을 보여준다
        if row >= 0:
            # 해당 행 선택 (파란색 하이라이트)
            self.table_view.selectRow(row)
            
            # 해당 행이 화면 중앙에 오도록 자동 스크롤
            # (매번 하면 어지러울 수 있으니 필요할 때만 하거나 부드럽게 하는게 좋음)
            # 여기서는 즉시 스크롤 적용
            index = self.model.index(row, 0)
            if index.isValid():
                self.table_view.scrollTo(index, QAbstractItemView.ScrollHint.PositionAtCenter)





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
