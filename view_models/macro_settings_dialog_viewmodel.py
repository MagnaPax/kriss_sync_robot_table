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

    # View에 알리기 위한 로컬 시그널 (View가 구독)
    # ViewModel → View 는 1:1 관계이기 때문에 EventBus(방송국) 대신 로컬 시그널/바인딩이 더 적절
    save_macro_failed = pyqtSignal(str)


    def __init__(self, service: Service):
        super().__init__()

        # Service 인스턴스를 소유 (직접 호출 위해)
        self.service = service



    @pyqtSlot(str, Dict[str, Any])
    def _save_macro(self, path: Path, new_macro_data: Dict[str, Any]):
        """View의 'Save 버튼 클릭' 시그널을 처리한다"""

        # Service 에게 작업 위임
        result = self.service.save_or_update_macro(path, new_macro_data)

        if result:
            # 로깅 (성공)
            log_message = f"[매크로 저장 완료] 매크로 ID: {new_macro_data.get('macro_id')}"
            EVENT_BUS.ui_log_message.emit(log_message, "INFO")

        else:
            # 실패
            # 로깅은 이미 Service가 ui_log_message 로 남김
            # View에 실패 알림 전송
            error_message = "매크로 저장 실패"
            self.save_macro_failed.emit(error_message)
