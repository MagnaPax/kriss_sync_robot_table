# utils/file_handler.py
import json, os
from pathlib import Path
from typing import Any, Dict, Optional

from utils.logger import Logger



def save_json(file_path: Path, data: Dict[str, Any]) -> bool:
    """
    Python 딕셔너리를 JSON 파일로 저장

    Args:
        file_path (Path): 저장할 JSON 파일의 경로
        data (Dict[str, Any]): 저장할 데이터

    Returns:
        bool: 저장 성공 여부
    """

    # 파일에 접근할 수 없는(다른 앱에 의해 열려 있는 등) 문제 발생 시 에러처리
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)     # 디렉토리가 존재하지 않으면 생성
        with open(file_path, "w", encoding="utf-8") as f:       # 쓰기 모드로 파일 열기
            json.dump(data, f, indent=4, ensure_ascii=False)    # 딕셔너리를 json 형식으로 변환
        return True
    except (IOError) as e:
        Logger().logger.warning(f"JSON 저장 실패: {file_path} - {e}")
        return False
        

def load_json(file_path: Path) -> Optional[Dict[str, Any]]:
    """
    JSON 파일을 읽어 Python 딕셔너리로 반환

    Args:
        file_path (Path): 읽어올 JSON 파일의 경로

    Returns:
        파일이 존재하고 유효한 경우 딕셔너리를, 그렇지 않은 경우 None을 반환
        Optional <- None도 반환될 수 있음을 나타낸다
    """

    if not os.path.exists(file_path):
        return None
    
    # 포맷이 잘못됐거나 못 읽는 파일 예외처리
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError, FileNotFoundError) as e:
        Logger().logger.warning(f"JSON 읽기 실패: {file_path} - {e}")
        return None






# ==========================================================
# 단독 실행 (테스트용)
"""
실행 명령어
python -m utils.file_handler
"""
# ==========================================================
if __name__ == '__main__':

    from config.paths import CONFIG_MACRO_PATH as file_path_macro_settings



    # 샘플 매크로 데이터
    data_macro = {
        "Macro_1": {
            "name": "안녕하세요",
            "x": 1672.173, "y": -868.69, "z": 73.2,
            "w": 0, "p": 0, "r": 0
        },
        "Macro_2": {
            "name": "Measure",
            "x": 2154, "y": -321, "z": -50,
            "w": 0, "p": 0, "r": 0
        }
    }

    # 저장 테스트
    print("🔹 매크로 데이터 저장 중...")
    save_json(file_path_macro_settings, data_macro)
    print(f"✅ 저장 완료: {file_path_macro_settings}")

    # 불러오기 테스트
    print("\n🔹 저장된 데이터 읽기...")
    loaded = load_json(file_path_macro_settings)
    print("✅ 로드된 데이터:", loaded)
