# utils/file_handler.py
"""
파일 입출력 유틸리티(단순 도구)

예외 발생 시 FileOperationError로 감싸서 호출부에 던진다

호출부는 try-except로 처리한다
"""

import json, csv
from pathlib import Path
from typing import Dict, Any, List

from utils.file_exceptions import FileOperationError


def load_json(path: Path) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        raise FileOperationError("JSON 로드 실패", e, path) from e


def save_json(path: Path, data: Dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        raise FileOperationError("JSON 저장 실패", e, path) from e


def load_text(path: Path) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        raise FileOperationError("텍스트 로드 실패", e, path) from e


def save_text(path: Path, data: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(data)
    except Exception as e:
        raise FileOperationError("텍스트 저장 실패", e, path) from e


def load_csv(path: Path) -> List[List[str]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return [row for row in csv.reader(f)]
    except Exception as e:
        raise FileOperationError("CSV 로드 실패", e, path) from e


def save_csv(path: Path, data: List[List[str]]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="") as f:
            csv.writer(f).writerows(data)
    except Exception as e:
        raise FileOperationError("CSV 저장 실패", e, path) from e
