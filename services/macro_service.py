# services/macro_service.py
"""
매크로 데이터(JSON 파일)을 처리하는 Service

자료형태:
    딕셔너리
    키: x,y,z,w,p,r
    값: 실수(float)
"""
from pathlib import Path
from typing import Callable, Any, Dict
from utils.file_handler import load_json, save_json
from utils.file_exceptions import FileOperationError
from core.event_bus import EVENT_BUS


class MacroService:

    # 매크로 데이터 파일이 없을 때 사용되는 표준 초기값(빈 딕셔너리)
    DEFAULT_MACRO_DATA = {}


    def load_macro(self, path: Path):
        """
        매크로 데이터를 JSON 파일에서 로드
        실제 로드 로직은 _load_data 헬퍼 메서드에 위임
        """
        return self._load_data(path, load_json)


    def save_or_update_macro(self, path: Path, new_macro_data: Dict[str, Any]) -> bool:
        """
        사용자가 입력한 새로운 매크로 데이터를 파일에 저장

        파라미터 값:
            new_macro_data:
            {
                'macro_id': 문자열(str),
                'name': 문자열(str),
                'x':실수(float),
                'y':실수(float),
                'z':실수(float),
                'w':실수(float),
                'p':실수(float),
                'r':실수(float)
            }
        """

        try:
            # 기존에 있는 매크로 설정 파일을 전부 읽는다
            existing_macro_data = self.load_macro(path)

            # 빈 딕셔너리가 아닌 None이 반환됐다면 에러가 난 것이기 때문에 중단하고 False 반환
            if existing_macro_data is None:
                # 에러 로그는 _load_data에서 이미 남겼음
                return False

            # 파일에서 읽어온 값 중에서 macro_id에 해당하는 부분만 업데이트
            macro_id = new_macro_data["macro_id"]
            existing_macro_data[macro_id] = new_macro_data

            # 수정된 전체 데이터를 파일에 다시 저장
            self._save_data(path, save_json, existing_macro_data)
            EVENT_BUS.ui_log_message.emit(
                f"[매크로 저장 완료] {macro_id}",
                "INFO"
            )
            return True
        
        except FileOperationError as e:
            EVENT_BUS.ui_log_message.emit(
                f"[매크로 저장 오류] 파일: {path}, 이유: {type(e.original).__name__}",
                "ERROR"
            )
            return False



    # --- 헬퍼 메서드 --- #
    def _load_data(self, path: Path, file_handler: Callable[[Path], Any]) -> Any | None:
        """파일 로드 로직을 처리하는 범용 헬퍼 메서드"""
        try:
            return file_handler(path)

        except FileOperationError as e:
            # FileNotFoundError → 정상 작동(첫 실행 시 파일이 없는 것이 정상)
            if isinstance(e.original, FileNotFoundError):
                EVENT_BUS.ui_log_message.emit(
                    f"[매크로 파일 없음] 새 파일 생성 예정: {path}",
                    "INFO"
                )
                # 파일이 없는 경우에도 None 이 아닌 빈 딕셔너리를 리턴
                return self.DEFAULT_MACRO_DATA.copy()

            # 진짜 에러만 로그 발생
            EVENT_BUS.ui_log_message.emit(
                f"[파일 로드 오류] {e} — 원인:{type(e.original).__name__}, 파일:{e.path}",
                "ERROR",
            )
            return None

    def _save_data(self, path: Path, file_handler: Callable[[Path, Any], None], data: Any) -> bool:
        """파일 저장 로직을 처리하는 범용 헬퍼 메서드"""
        try:
            # 매개변수로 받은 file_handler 함수를 사용하여 파일 저장
            file_handler(path, data)
            EVENT_BUS.ui_log_message.emit(
                f"[매크로 저장 완료] {path}", 
                "INFO"
            )
        except FileOperationError as e:
            EVENT_BUS.ui_log_message.emit(
                f"[매크로 저장 오류] {e} — 원인:{type(e.original).__name__}, 파일:{e.path}",
                "ERROR",
            )
            return False
        return True









"""
=============================================================================
-- Smoke Test --

실행 명령어:
    python -m services.macro_service
=============================================================================
"""
