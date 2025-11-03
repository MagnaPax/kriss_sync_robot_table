# utils/file_handler.py
import json, os



def save_json(path: str, data: dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)       # 디렉토리가 존재하지 않으면 생성
    with open(path, "w", encoding="utf-8") as f:            # 쓰기 모드로 파일 열기
        json.dump(data, f, indent=4, ensure_ascii=False)    # 딕셔너리를 json 형식으로 변환


def load_json(path: str, default=None):
    if not os.path.exists(path):
        return default or {}
    
    # 깨진파일, 포맷 잘못된 json 예외처리
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"[WARN] JSON 파일 손상: {path}, 빈 데이터로 초기화합니다.")
        return default or {}






# ==========================================================
# 단독 실행 (테스트용)
"""
실행 명령어
python -m utils.file_handler
"""
# ==========================================================
if __name__ == '__main__':

    from config.paths import CONFIG_MACRO_PATH as path_macro_settings

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
    save_json(path_macro_settings, data_macro)
    print(f"✅ 저장 완료: {path_macro_settings}")

    # 불러오기 테스트
    print("\n🔹 저장된 데이터 읽기...")
    loaded = load_json(path_macro_settings)
    print("✅ 로드된 데이터:", loaded)
