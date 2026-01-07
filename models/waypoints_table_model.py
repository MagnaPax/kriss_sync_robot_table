# models/waypoints_table_model.py
"""
View(UI)  ←→  ViewModel(Model)

[이 파일의 정체]
PyQt의 Model/View 패턴에서 'Model'을 담당하는 녀석입니다.

Q: 그냥 QTableWidget 쓰면 편한데 왜 굳이 Model을 따로 만드나요?
A: 데이터가 적을 땐 QTableWidget이 편하지만, 데이터가 1,000개만 넘어가도 버벅거립니다.
    이 방식(QAbstractTableModel 상속)은 '가상화(Virtualization)' 기술을 써서
    데이터가 100만 개라도 화면에 보이는 20개만 그리기 때문에 속도가 엄청나게 빠릅니다.

    즉, "대용량 데이터를 렉 없이 보여주기 위한 필수 테크닉"입니다.
"""

from typing import List, Dict, Any, Optional
from PyQt6.QtCore import QAbstractTableModel, Qt, QModelIndex, QObject



class WaypointsTableModel(QAbstractTableModel):
    """
    [Waypoints 테이블 모델]
    
    역할:
        - 원본 데이터(List[Dict])를 들고 있음 (_data)
        - View(QTableView)가 "이 칸에 뭐 그려?" 물어보면 대답해줌 (data 메서드)
        - 데이터가 바뀌면 View에게 "다시 그려"라고 신호 보냄 (layoutChanged 등)
    """
    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._data: List[Dict[str, Any]] = [] # 실제 데이터 저장소 (5만개 리스트)
        self._headers: List[str] = []         # 컬럼 제목 리스트

    def set_data(self, data: List[Dict[str, Any]]):
        """
        [데이터 주입] 외부에서 데이터를 받아와 모델을 갱신하는 곳.
        
        Q: 그냥 self._data = data 하면 안 되는 이유
        A: 뷰(View)는 모델의 데이터가 바뀐지 모른다
            반드시 beginResetModel()과 endResetModel()로 감싸서 
            "야, 데이터 싹 갈아엎는다! 다시 그려!"라고 신호를 보내야 한다
        """
        if not data:
            self.beginResetModel()
            self._data = []
            self._headers = []
            self.endResetModel()
            return

        # 1. 모델 리셋 시작 알림 (뷰야, 잠깐 멈춰! 데이터 대공사 들어간다!)
        self.beginResetModel()

        self._data = data
        
        # 2. 컬럼 키 설정 (기존 로직 이식)
        # 우선순위: ID -> CMD -> 좌표 -> 나머지 (화면에 보여줄 순서 정하기)
        priority_keys = ['id', 'cmd', 'x', 'y', 'z', 'w', 'p', 'r', 'angle', 'velocity', 'f']
        available_keys = list(data[0].keys())
        
        self._headers = [k for k in priority_keys if k in available_keys]
        for k in available_keys:
            if k not in self._headers:
                self._headers.append(k)

        # 3. 모델 리셋 종료 알림 (공사 끝! 이제 새로 그려도 돼!)
        self.endResetModel()

    # --- 필수 오버라이드 메서드 (Qt가 이 함수들을 호출해서 화면을 그림) ---

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """
        [필수] 전체 행(Row) 개수가 몇 개인지 뷰에게 알려줍니다.
        """
        return len(self._data)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """
        [필수] 전체 열(Column) 개수가 몇 개인지 뷰에게 알려줍니다.
        """
        return len(self._headers)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        """
        [핵심] 뷰(View)가 화면을 그릴 때마다 쉴 새 없이 호출하는 함수
        
        "야, 3번째 줄 2번째 칸에 글자(DisplayRole) 뭐 써야 돼?"
        "야, 3번째 줄 2번째 칸 정렬(TextAlignmentRole)은 어떻게 해?"
        
        주의: 여기서 복잡한 계산을 하거나 DB를 조회하면 앱에 렉이 걸린다
                최대한 빨리 값을 리턴해야 한다
        """
        if not index.isValid():
            return None

        row = index.row()
        col = index.column()
        key = self._headers[col]
        value = self._data[row].get(key)

        # 1. 화면에 글자로 보여줄 때 (DisplayRole) - 엑셀 셀 내용
        if role == Qt.ItemDataRole.DisplayRole:
            if isinstance(value, float):
                return f"{value:.3f}" # 소수점 3자리 포맷팅
            return str(value)

        # 2. 정렬 방식 (TextAlignmentRole) - 가운데 정렬
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignCenter

        # 3. (옵션) 색상(BackgroundRole), 폰트(FontRole) 등도 여기서 처리 가능
        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        """
        [헤더 설정] 표의 윗부분(컬럼명)이나 왼쪽 부분(행번호)에 들어갈 텍스트를 반환합니다.
        """
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self._headers[section].upper()
        return None
    
    def get_row_data(self, row_idx: int) -> Dict[str, Any]:
        """
        [유틸] 뷰에서 특정 행을 클릭했을 때, 그 행의 '진짜 데이터(Dict)'를 통째로 가져오기 위한 함수.
        """
        if 0 <= row_idx < len(self._data):
            return self._data[row_idx]
        return {}
