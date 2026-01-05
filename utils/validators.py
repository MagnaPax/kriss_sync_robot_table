# utils/validators.py
from typing import Callable, Optional
from PyQt6.QtGui import (
    QDoubleValidator, 
    QValidator, 
    QRegularExpressionValidator
)
from PyQt6.QtCore import QRegularExpression, QObject



# ==========================================================
# 1. 숫자 전용 Validator (QDoubleValidator 상속)
# ==========================================================
class NumericValidator(QDoubleValidator):
    """
    숫자 입력만 허용하고, 실패 시 에러 콜백을 호출
    """
    def __init__(self, error_callback: Optional[Callable[[str], None]] = None, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.error_callback = error_callback
        self.setNotation(QDoubleValidator.Notation.StandardNotation)

    def validate(self, input: str, pos: int):    # type: ignore[override]
        # 입력 중인 상태 허용
        if input in ["", "-", ".", "-."]:
            return QValidator.State.Intermediate, input, pos
        
        try:
            float(input)
            return super().validate(input, pos)
        except ValueError:
            if self.error_callback:
                self.error_callback("숫자만 입력 가능합니다.")
            return QValidator.State.Invalid, input, pos





# ==========================================================
# 패턴(정규식) 전용 부모 Validator
# ==========================================================
class PatternValidator(QRegularExpressionValidator):
    """
    정규표현식을 기반으로 입력값을 검증하는 기본 클래스
    """
    def __init__(self, pattern: str, error_msg: str, error_callback: Optional[Callable[[str], None]] = None, parent: Optional[QObject] = None):
        regex = QRegularExpression(pattern)
        super().__init__(regex, parent)
        self.error_msg = error_msg
        self.error_callback = error_callback

    def validate(self, input: Optional[str], pos: int):
        state, text, pos = super().validate(input, pos)
        
        # QRegularExpressionValidator는 기본적으로 Invalid를 잘 반환하지만,
        # 사용자가 완전히 엉뚱한 값을 붙여넣기 했을 때 콜백을 호출하기 위해 오버라이딩
        if state == QValidator.State.Invalid:
            if self.error_callback:
                self.error_callback(self.error_msg)
        
        return state, text, pos


# ==========================================================
# 구체적인 Validator 구현체들
# ==========================================================

class EmailValidator(PatternValidator):
    """이메일 형식 검증"""
    def __init__(self, error_callback: Optional[Callable[[str], None]] = None, parent: Optional[QObject] = None):
        # 간단한 이메일 정규식
        pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
        super().__init__(
            pattern=pattern, 
            error_msg="올바른 이메일 형식이 아닙니다.", 
            error_callback=error_callback, 
            parent=parent
        )

class IPv4Validator(PatternValidator):
    """IPv4 주소 검증 (PLC 연결 시 유용)"""
    def __init__(self, error_callback: Optional[Callable[[str], None]] = None, parent: Optional[QObject] = None):
        # 0.0.0.0 ~ 255.255.255.255
        pattern = (
            r"^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}"
            r"(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"
        )
        super().__init__(
            pattern=pattern, 
            error_msg="올바른 IP 주소 형식이 아닙니다.", 
            error_callback=error_callback, 
            parent=parent
        )
