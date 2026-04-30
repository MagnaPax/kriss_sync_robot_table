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


# 공통 데이터 포맷 상수 사용
# Model 계층에서 도메인 정의(Keys)를 아는 것은 의존성 주입 위반이 아니라 올바른 참조
from config.data_formats import (
    KEY_ID, 
    KEY_STATUS, 
    KEY_ROBOT_X, KEY_ROBOT_Y, KEY_ROBOT_Z, 
    KEY_ROBOT_W, KEY_ROBOT_P, KEY_ROBOT_R, 
    KEY_ROBOT_FEED_RATE
)


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
        """
        if not data:
            self.beginResetModel()
            self._data = []
            self._headers = []
            self.endResetModel()
            return

        # 1. 모델 리셋 시작 알림
        self.beginResetModel()

        self._data = data
        
        # 2. 컬럼 키 설정
        #    사용자 데이터에 'status'가 이미 있는지 확인 (대소문자 구분 없이)
        self._status_key = KEY_STATUS
        available_keys = list(data[0].keys())
        
        # 이미 존재하는 status 키 찾기 (예: 'STATUS', 'Status' ...)
        found_status_key = next((k for k in available_keys if k.lower() == KEY_STATUS), None)
        if found_status_key:
            self._status_key = found_status_key
        else:
            # 없으면 'status' 키로 초기화
            for row_data in self._data:
                row_data[self._status_key] = '-'
            available_keys.append(self._status_key)

        # 3. 헤더 순서 결정
        #    [Refactor] ID가 가장 먼저 보이도록 수정 (User Request)
        #    상수 사용: KEY_ID, KEY_STATUS...
        priority_keys = [
            KEY_ID, 
            self._status_key, 
            'cmd', # 'cmd'는 data_formats에 없으므로 유지
            KEY_ROBOT_X, KEY_ROBOT_Y, KEY_ROBOT_Z, 
            KEY_ROBOT_W, KEY_ROBOT_P, KEY_ROBOT_R, 
            'angle', 'velocity', # Legacy keys
            KEY_ROBOT_FEED_RATE
        ]
        
        self._headers = [k for k in priority_keys if k in available_keys]
        for k in available_keys:
            if k not in self._headers:
                self._headers.append(k)

        # [UX] ID가 0번(맨 앞)에 오도록 강력하게 보장
        if self._headers[0] != KEY_ID:
            if KEY_ID in self._headers:
                self._headers.remove(KEY_ID)
                self._headers.insert(0, KEY_ID)
                
        # [UX] 그 다음은 Status가 오도록 보장 (ID 뒷자리)
        if len(self._headers) > 1 and self._headers[1] != self._status_key:
            if self._status_key in self._headers:
                self._headers.remove(self._status_key)
                # ID가 0번에 있다면 1번에 삽입
                target_idx = 1 if self._headers[0] == KEY_ID else 0
                self._headers.insert(target_idx, self._status_key)

        # 3. 모델 리셋 종료 알림
        self.endResetModel()

    def update_status(self, row_idx: int, status: str):
        """
        [부분 갱신] 특정 행의 상태만 빠르게 업데이트
        """
        if 0 <= row_idx < len(self._data):
            # 동적으로 찾은 status key 사용
            key = getattr(self, '_status_key', KEY_STATUS)
            self._data[row_idx][key] = status
            
            # 컬럼 위치 찾기
            try:
                col_idx = self._headers.index(key)
                index = self.index(row_idx, col_idx)
                self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ForegroundRole])
            except ValueError:
                pass

    # --- 필수 오버라이드 메서드 ---

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._data)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._headers)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None

        row = index.row()
        col = index.column()
        key = self._headers[col]
        value = self._data[row].get(key)

        # 1. 화면에 글자로 보여줄 때 (DisplayRole)
        if role == Qt.ItemDataRole.DisplayRole:
            if isinstance(value, float):
                return f"{value:.3f}"
            return str(value)

        # 2. 정렬 방식 (TextAlignmentRole)
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignCenter

        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self._headers[section].upper()
        return None
    
    def get_row_data(self, row_idx: int) -> Dict[str, Any]:
        if 0 <= row_idx < len(self._data):
            return self._data[row_idx]
        return {}
