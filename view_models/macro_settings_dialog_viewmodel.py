# ui/widgets/macro_settings_dialog_viewmodel.py
"""
VM 의 역할
    - UI의 상태 관리
    - UI 이벤트 처리
    - 명령(Command) 및 로직 요청


MacroSettingsDialog 의 뷰모델

    1. View의 요청 처리
        하지만 View의 '존재'는 모른다.

    2. Service 호출(직접 호출)

    3. Service 의 결과를 알기 위해 구독(EVENT BUS)

    4. Service 의 작업 결과에 따라 UI를 어떻게 할지(창을 닫을지, 에러를 띄울지) 결정
"""

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from services.macro_service import MacroService as Service
from core.event_bus import EVENT_BUS
from typing import Dict, Any
from pathlib import Path




class MacroSettingsDialogViewModel(QObject):

    # View에 알리기 위한 로컬 시그널 (View가 구독)
    # ViewModel → View 는 1:1 관계이기 때문에 EventBus(방송국) 대신 로컬 시그널/바인딩(전화)이 더 적절
    save_macro_failed = pyqtSignal(str)     # 저장 실패 알리미
    save_macro_complete = pyqtSignal(str)   # 저장 완료 알리미


    def __init__(self, service: Service):
        super().__init__()

        # Service 인스턴스를 소유 (직접 호출 위해)
        self.service = service


    @pyqtSlot(str, dict)
    def _save_macro(self, path: Path, new_macro_data: Dict[str, Any]):
        """View의 'Save 버튼 클릭' 시그널을 처리"""

        macro_id = new_macro_data.get('macro_id', 'Unknown')

        # Service 에게 작업 위임 (결과는 bool)
        #   작업 결과에 대한 로깅은 뷰모델이 아닌 Service 내부에서 이미 수행됨
        is_success = self.service.save_or_update_macro(path, new_macro_data)


        if is_success:
            # 성공 시: 뷰에게 "성공했다"고 알려줌 (버튼 깜빡임 등을 위해)
            self.save_macro_complete.emit(macro_id)

        else:
            # 사용자 입력 저장 실패
            # 뷰는 MacroService 가 '방송'한 ui_log_message와 아래의 save_macro_failed 중에서 적절한 것을 골라서 사용자에게 보여줄 수 있다
            error_message = "매크로 저장 실패. 다시 시도해 주세요. 계속 실패한다면 관리자에게 문의하세요."
            self.save_macro_failed.emit(error_message)  # View에 알림 전송
