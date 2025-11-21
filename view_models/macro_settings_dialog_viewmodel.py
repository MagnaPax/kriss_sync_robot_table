# ui/widgets/macro_settings_dialog_viewmodel.py
"""
MacroSettingsDialog 의 뷰모델

    1. View의 요청 처리
        하지만 View의 '존재'는 모른다.

    2. Service 호출(직접 호출)

    3. Service 로부터 결과 받음(EVENT BUS)

    4. View에 결과 보고 (EVENT BUS)
"""

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from services.macro_service import MacroService as Service
from core.event_bus import EVENT_BUS
from typing import Dict, Any
from pathlib import Path




class MacroSettingsDialogViewModel(QObject):

    # 노출할 시그널 (View 의 메서드가 구독)
    state_changed = pyqtSignal(str)


    def __init__(self, service: Service):
        super().__init__()

        # Service 인스턴스를 소유 (직접 호출 위해)
        self.service = service


    @pyqtSlot(str, Dict[str, Any])
    def _save_macro(self, path: Path, new_macro_data: Dict[str, Any]):
        """View의 'Save 버튼 클릭' 시그널을 처리한다 - Service 에게 작업 위임"""
        self.service.save_or_update_macro(path, new_macro_data)

"""