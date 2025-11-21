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

    def __init__(self, service: Service):
        super().__init__()

        # Service 인스턴스를 소유 (직접 호출 위해)
        self.service = service

        # Service 에서 송출한 시그널 청취
        EVENT_BUS.macro_save_result.connect(self._handle_macro_save_status_received)



    @pyqtSlot(str, Dict[str, Any])
    def _save_macro(self, path: Path, new_macro_data: Dict[str, Any]):
        """View의 'Save 버튼 클릭' 시그널을 처리한다 - Service 에게 작업 위임"""
        self.service.save_or_update_macro(path, new_macro_data)

    @pyqtSlot(bool, str)
    def _handle_macro_save_status_received(self, save_result: bool, message_or_id: str):
        """
        MacroService가 송출한 매크로 저장 결과의 이벤트(완료/실패) 처리

        Service의 결과를 받아서 
            성공: 로깅만 하기 (성공했다고 귀찮게 사용자에게 알리지 않음)
            실패: 로깅 후 View에게 알리기 (macro_save_failed 시그널 emit)
        
        인자값:
            save_result: 성공/실패 여부
            message: 성공 시 매크로 ID, 실패 시 에러 메시지
        """

        if save_result:
            # 로깅 (성공)
            log_message = f"[매크로 저장 완료] 매크로 ID: {message_or_id}"
            EVENT_BUS.ui_log_message.emit(log_message, "INFO")

        else:
            # 로깅 (실패)
            log_message = f"  ⚠ [매크로 저장 실패] {message_or_id}"
            EVENT_BUS.ui_log_message.emit(log_message, "ERROR")

            # 시그널 송출 (실패) -> View가 구독
            EVENT_BUS.macro_save_failed.emit(save_result, message_or_id)
