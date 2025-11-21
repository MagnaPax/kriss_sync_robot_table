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
# services/macro_service.py
# ... (중략: class MacroService 정의 및 _load_data, _save_data 메서드 정의) ...


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
    import json
    import time
    from pathlib import Path

    # EventBus는 QObject를 상속하므로, 시그널을 처리하려면 QApplication 인스턴스가 필요합니다.
    try:
        from PyQt6.QtWidgets import QApplication
        # QApplication 인스턴스를 생성하면 로깅 시스템이 초기화될 수 있습니다.
        app = QApplication(sys.argv) 
    except ImportError:
        # PyQt6가 없으면 EventBus 시그널 테스트는 불가하지만, 로직 테스트는 가능
        app = None

    print("\n" + "="*70)
    print("MacroService save_or_update_macro Smoke Test")
    print("="*70 + "\n")

    # 1. 서비스 인스턴스 및 테스트 파일 경로 설정
    service = MacroService()
    
    # 현재 폴더에 테스트 파일 경로 지정
    # 실제 파일 시스템에 영향을 주지 않도록 unique한 이름 사용 권장
    test_file_path = Path(__file__).parent / f"test_macro_config_{os.getpid()}.json"
    print(f"🧪 테스트 파일 경로: {test_file_path}\n")

    # --- 테스트 시작 전, 혹시 남아있을 수 있는 테스트 파일 삭제 ---
    if test_file_path.exists():
        test_file_path.unlink()
    
    # --- 테스트 데이터 (View에서 _gather_macro_data를 통해 들어오는 형식) ---
    MACRO_A_V1 = {
        'macro_id': 'Macro_A',
        'name': '시작위치',
        'x': 10.0, 'y': 20.0, 'z': 0.0, 'w': 0.0, 'p': 0.0, 'r': 0.0
    }
    MACRO_A_V2_UPDATE = {
        'macro_id': 'Macro_A',
        'name': '업데이트 위치',
        'x': 15.0, 'y': 25.0, 'z': 5.0, 'w': 0.0, 'p': 0.0, 'r': 0.0
    }
    MACRO_B = {
        'macro_id': 'Macro_B',
        'name': '종료위치',
        'x': 100.0, 'y': 200.0, 'z': 50.0, 'w': 0.0, 'p': 0.0, 'r': 0.0
    }

    
    # ==========================================================
    # 1️⃣ 파일 생성 및 첫 번째 저장 테스트
    # ==========================================================
    print("1️⃣ 파일 생성 및 첫 번째 매크로 저장 (Macro_A):")
    
    save_success_a = service.save_or_update_macro(test_file_path, MACRO_A_V1)
    
    if save_success_a and test_file_path.exists():
        print("   ✅ 성공: Macro_A 저장 완료. 파일이 정상적으로 생성됨.")
    else:
        print("   ❌ 실패: 파일 생성 및 첫 번째 저장 실패.")
        sys.exit(1)
        
    # 데이터 구조 확인
    loaded_data_after_a = service.load_macro(test_file_path)
    print(f"   👉 저장된 키 확인: {list(loaded_data_after_a.keys())}")
    
    # ==========================================================
    # 2️⃣ 기존 데이터에 새로운 매크로 추가 (Macro_B)
    # ==========================================================
    print("\n2️⃣ 새로운 매크로 추가 저장 (Macro_B):")
    
    save_success_b = service.save_or_update_macro(test_file_path, MACRO_B)
    
    if save_success_b:
        print("   ✅ 성공: Macro_B 추가 저장 완료.")
    else:
        print("   ❌ 실패: Macro_B 추가 저장 실패.")
        sys.exit(1)

    # 최종 데이터 확인
    with open(test_file_path, 'r', encoding='utf-8') as f:
        final_content = json.load(f)
    
    print(f"   👉 최종 키 확인: {list(final_content.keys())}")
    
    if 'Macro_A' in final_content and 'Macro_B' in final_content:
        print("   ✅ 최종 확인: Macro_A, Macro_B 모두 파일에 존재합니다.")
    else:
        print("   ❌ 최종 확인: 매크로 데이터 병합 실패.")
        sys.exit(1)

    # ==========================================================
    # 3️⃣ 기존 매크로 업데이트 테스트 (Macro_A V2)
    # ==========================================================
    print("\n3️⃣ 기존 매크로 데이터 업데이트 (Macro_A -> V2):")
    
    update_success = service.save_or_update_macro(test_file_path, MACRO_A_V2_UPDATE)
    
    if update_success:
        print("   ✅ 성공: Macro_A 업데이트 저장 완료.")
    else:
        print("   ❌ 실패: Macro_A 업데이트 저장 실패.")
        sys.exit(1)

    # 업데이트된 값 확인
    with open(test_file_path, 'r', encoding='utf-8') as f:
        updated_content = json.load(f)
        
    if updated_content['Macro_A']['x'] == 15.0:
        print(f"   ✅ 최종 확인: Macro_A의 X 좌표가 {updated_content['Macro_A']['x']}로 업데이트되었습니다.")
    else:
        print(f"   ❌ 최종 확인: Macro_A의 X 좌표 업데이트 실패. 현재 값: {updated_content['Macro_A']['x']}")
        sys.exit(1)


    # ==========================================================
    # 4️⃣ 정리 작업
    # ==========================================================
    print("\n4️⃣ 테스트 파일 정리:")
    if test_file_path.exists():
        test_file_path.unlink()
        print(f"   ✅ 성공: '{test_file_path.name}' 파일을 삭제했습니다.")
    
    print("\n" + "="*70)
    print("테스트 완료")
    print("="*70)