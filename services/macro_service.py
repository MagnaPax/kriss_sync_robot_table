# services/macro_service.py
"""
매크로 데이터(JSON 파일)을 처리하는 Service

자료형태:
    딕셔너리
    키: x,y,z,w,p,r
    값: 실수(float)
"""
from pathlib import Path
from utils.file_handler import load_json, save_json
from utils.file_exceptions import FileOperationError
from core.event_bus import EVENT_BUS


class MacroService:

    # 매크로 데이터 파일이 존재하지 않거나 로드에 실패했을 때 사용되는 표준 초기값
    DEFAULT_MACRO_DATA = {

        # 파일이 없는 경우에도 빈 딕셔너리 데이터 이용할 수 있게
        "macro_list": [],

        # 마이그래이션 대비
        #   미래에 매크로 데이터의 구조가 변경됐을 때 구분하기 위함
        "version": 1
    }

    def load_macro(self, path: Path):
        try:
            return load_json(path)

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
                f"[매크로 로드 오류] {e} — 원인:{type(e.original).__name__}, 파일:{e.path}",
                "ERROR",
            )
            return None


    def save_macro(self, path: Path, data):
        try:
            save_json(path, data)
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
