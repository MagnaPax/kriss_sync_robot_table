# services/macro_service.py
"""
매크로 데이터(JSON 파일)을 처리하는 Service

자료형태:
    딕셔너리
    키: x,y,z,w,p,r
    값: 실수(float)
"""
from pathlib import Path
from typing import Callable, Any
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
        """
        매크로 데이터를 JSON 파일에서 로드
        실제 로드 로직은 _load_data 헬퍼 메서드에 위임
        """
        return self._load_data(path, load_json)


    def save_macro(self, path: Path, data):
        """
        매크로 데이터를 JSON 파일에 저장
        실제 저장 로직은 _save_data 헬퍼 메서드에 위임
        """
        return self._save_data(path, save_json, data)



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
if __name__ == "__main__":
    import sys
    import os
    import time

    # EventBus는 QObject를 상속하므로, 시그널을 처리하려면 QApplication 인스턴스가 필요합니다.
    try:
        from PyQt6.QtWidgets import QApplication
        app = QApplication(sys.argv)
    except ImportError:
        print("경고: PyQt6가 설치되지 않아 EventBus 시그널이 처리되지 않습니다.")
        app = None

    print("\n" + "="*70)
    print("MacroService Smoke Test")
    print("="*70 + "\n")

    # 1. 서비스 인스턴스 및 테스트 파일 경로 설정
    service = MacroService()
    # 현재 폴더에 테스트 파일 생성
    test_file_path = Path(__file__).parent / "test_macro_settings.json"
    print(f"🧪 테스트 파일 경로: {test_file_path}\n")

    # --- 테스트 시작 전, 혹시 남아있을 수 있는 테스트 파일 삭제 ---
    if test_file_path.exists():
        test_file_path.unlink()

    # 2. 파일이 없을 때 load_macro 테스트
    print("1️⃣  파일이 없을 때 로드 테스트:")
    loaded_data_nonexistent = service.load_macro(test_file_path)
    if loaded_data_nonexistent == service.DEFAULT_MACRO_DATA:
        print("   ✅ 성공: 기본 데이터를 반환했습니다.")
    else:
        print(f"   ❌ 실패: 예상과 다른 데이터 반환 - {loaded_data_nonexistent}")

    # 3. 파일 저장 테스트
    print("\n2️⃣  파일 저장 테스트:")
    sample_data_to_save = {
        "Macro_1": {"name": "테스트 매크로 1", "x": 10.0, "y": 20.0},
        "Macro_2": {"name": "테스트 매크로 2", "x": 30.0, "y": 40.0},
    }
    save_success = service.save_macro(test_file_path, sample_data_to_save)
    if save_success and test_file_path.exists():
        print("   ✅ 성공: 파일이 정상적으로 생성되었습니다.")
    else:
        print("   ❌ 실패: 파일 저장에 실패했거나 파일이 생성되지 않았습니다.")

    # 4. 파일이 있을 때 load_macro 테스트
    print("\n3️⃣  파일이 있을 때 로드 테스트:")
    loaded_data_existent = service.load_macro(test_file_path)
    if loaded_data_existent == sample_data_to_save:
        print("   ✅ 성공: 저장된 데이터를 정확히 읽어왔습니다.")
    else:
        print(f"   ❌ 실패: 저장된 데이터와 일치하지 않습니다. - {loaded_data_existent}")

    # 5. 테스트 종료 후 파일 정리
    print("\n4️⃣  테스트 파일 정리:")
    if test_file_path.exists():
        test_file_path.unlink()
        print(f"   ✅ 성공: '{test_file_path.name}' 파일을 삭제했습니다.")

    print("\n" + "="*70)
    print("테스트 완료")
    print("="*70)
