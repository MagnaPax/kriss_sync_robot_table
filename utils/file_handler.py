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

