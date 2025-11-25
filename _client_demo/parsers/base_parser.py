# base_parser.py
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

class BaseParser(ABC):

    @abstractmethod
    def can_parse(self, path: Path) -> bool:
        """이 파서가 이 파일을 처리할 수 있는지 여부"""
        pass

    @abstractmethod
    def parse(self, data: Any) -> Any:
        """파일 핸들러가 읽어온 data를 파싱한다"""
        pass
