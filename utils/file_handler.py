# utils/file_handler.py
"""
파일 입출력 유틸리티
-------------------
JSON 및 텍스트 파일 읽기/쓰기 기능 제공

의존성:
    - utils/logger.py: 에러 로깅

에러 처리 전략:
    1. FileNotFoundError: None/False 반환 (로그 안 남김 - 최초 시작 시 파일 없을 수 있음)
    2. 예상 가능한 에러: logger.warning + None/False 반환
    3. 심각한 에러: logger.error + None/False 반환
    4. 호출자가 반환값 확인하여 UI 피드백
"""
import json, os
from pathlib import Path
from typing import Any, Dict, Optional

from utils.logger import Logger

######################
# --- JSON Tools --- #
######################
def load_json(file_path: Path) -> Optional[Dict[str, Any]]:
    """
    JSON 파일을 읽어 Python 딕셔너리로 반환

    Args:
        file_path (Path): 읽어올 JSON 파일의 경로

    Returns:
        파일이 존재하고 유효한 경우 딕셔너리를, 그렇지 않은 경우 None을 반환
        Optional <- None도 반환될 수 있음을 나타낸다

    에러 처리:
        - FileNotFoundError: None 반환 (정상 - 로깅 X)
        - JSONDecodeError: logger.warning + None 반환
        - 기타: logger.error + None 반환
    """

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
        
    except FileNotFoundError:
        # 에러 아님(최초 실행 시 파일 없을 수 있다)
        return None
    
    except json.JSONDecodeError as e:
        # JSON 형식 오류 - warning 레벨
        Logger().logger.warning(
            f"JSON 파싱 실패: {file_path}\n"
            f"  라인 {e.lineno}, 열 {e.colno}: {e.msg}"
        )
        return None
    
    except PermissionError:
        # 권한 문제 - error 레벨
        Logger().logger.error(f"파일 접근 권한 없음: {file_path}")
        return None
    
    except IOError as e:
        # I/O 에러 - error 레벨
        Logger().logger.error(f"파일 읽기 실패: {file_path}\n  원인: {e}")
        return None
    
    except Exception as e:
        # 예상치 못한 에러 - error 레벨 (스택 트레이스 포함)
        Logger().logger.error(
            f"JSON 로드 중 예상치 못한 에러: {file_path}",
            exc_info=True
        )
        return None

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
        # 디렉토리가 존재하지 않으면 생성
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # 쓰기 모드로 파일 열기
        with open(file_path, "w", encoding="utf-8") as f:
            # 딕셔너리를 json 형식으로 변환
            json.dump(data, f, indent=4, ensure_ascii=False)
        return True

    except PermissionError:
        Logger().logger.error(f"파일 쓰기 권한 없음: {file_path}")
        return False

    except OSError as e:
        Logger().logger.error(
            f"파일 저장 실패: {file_path}\n"
            f"  원인: {e}\n"
            f"  힌트: 디스크 공간 또는 경로를 확인하세요"
        )
        return False

    except Exception as e:
        Logger().logger.error(
            f"JSON 저장 중 예상치 못한 에러: {file_path}",
            exc_info=True
        )
        return False




######################
# --- TEXT Tools --- #
######################
def load_text(file_path: Path) -> Optional[str]:
    """
    텍스트 파일을 읽어 문자열로 반환

    Args:
        file_path (Path): 읽어올 텍스트 파일의 경로

    Returns:
        파일이 존재하고 유효한 경우 문자열을, 그렇지 않은 경우 None을 반환
        Optional <- None도 반환될 수 있음을 나타낸다

    에러 처리:
        - FileNotFoundError: None 반환 (정상 - 로그 안 남긴다)
        - UnicodeDecodeError: logger.warning + None 반환
        - 기타: logger.error + None 반환        
    """

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    except FileNotFoundError:
        # 정상 케이스
        return None

    except PermissionError:
        Logger().logger.error(f"파일 접근 권한 없음: {file_path}")
        return None

    except IOError as e:
        Logger().logger.error(f"텍스트 파일 읽기 실패: {file_path}\n  원인: {e}")
        return None

    except UnicodeDecodeError as e:
        # 인코딩 문제 - warning
        Logger().logger.warning(
            f"텍스트 인코딩 오류: {file_path}\n"
            f"  위치: {e.start}-{e.end}\n"
            f"  힌트: UTF-8 인코딩을 확인하세요"
        )
        return None

    except Exception as e:
        Logger().logger.error(
            f"텍스트 로드 중 예상치 못한 에러: {file_path}",
            exc_info=True
        )
        return None

def save_text(file_path: Path, data: str) -> bool:
    """
    문자열을 텍스트 파일로 저장

    Args:
        file_path (Path): 저장할 텍스트 파일의 경로
        text (str): 저장할 텍스트

    Returns:
        bool: 저장 성공 여부
    """
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(data)
        return True

    except PermissionError:
        Logger().logger.error(f"텍스트 파일 쓰기 권한 없음: {file_path}")
        return False
    
    except OSError as e:
        Logger().logger.error(
            f"텍스트 파일 저장 실패: {file_path}\n"
            f"  원인: {e}\n"
            f"  힌트: 디스크 공간 또는 경로를 확인하세요"
        )
        return False

    except Exception as e:
        Logger().logger.error(
            f"텍스트 저장 중 예상치 못한 에러: {file_path}",
            exc_info=True
        )
        return False








# ==========================================================
# 단독 실행 (테스트용)
"""
실행 명령어
python -m utils.file_handler
"""
# ==========================================================
if __name__ == '__main__':

    from config.paths import CONFIG_MACRO_PATH as file_path

    # =====================
    # --- JSON 테스트 --- #
    # =====================

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
    save_json(file_path, data_macro)
    print(f"✅ 저장 완료: {file_path}")

    # 불러오기 테스트
    print("\n🔹 저장된 데이터 읽기...")
    loaded = load_json(file_path)
    print("✅ 로드된 데이터:", loaded)


    # ====================
    # --- TXT 테스트 --- #
    # ====================

    # 텍스트 테스트용 경로 (JSON과 동일한 위치에 저장)
    file_path_text = file_path.parent / "test_sequence_output.txt"

    # 샘플 텍스트 데이터 (F, T, X, Y... 데이터)
    data_text = (
        "10.000 0.000 95.625 -8.166 2.744 -0.27850 -3.26302 0.00000 -2.000 1.0\n"
        "10.000 0.000 95.784 -6.129 2.744 -0.20901 -3.26845 0.00000 -2.000 1.0\n"
        "10.000 0.000 95.899 -4.088 2.744 -0.13942 -3.27238 0.00000 -2.000 1.0\n"
        "10.000 0.000 95.971 -2.044 2.745 -0.06970 -3.27485 0.00000 -2.000 1.0\n"
        "10.000 0.000 95.971 -2.044 2.745 -0.06970 -3.27485 0.00000 0.000 0.0"
    )

    # 저장 테스트
    print("🔹 TEXT 데이터 저장 중...")
    save_text(file_path_text, data_text)
    print(f"✅ 저장 완료: {file_path_text}")

    # 불러오기 테스트
    print("\n🔹 저장된 TEXT 데이터 읽기...")
    loaded_text = load_text(file_path_text)
    print("✅ 로드된 TEXT:\n--- (시작) ---")
    print(loaded_text)
    print("--- ( 끝 ) ---")
