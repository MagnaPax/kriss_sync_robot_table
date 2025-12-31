# core/exceptions.py

class AppError(Exception):
    """
    이 애플리케이션에서 발생하는 모든 커스텀 예외의 기본 클래스.
    이 클래스를 상속받으면 '시스템 버그'가 아니라 '비즈니스 로직 상의 에러'로 간주할 수 있다
    exception_handler.py 에서 이 타입을 보고 로깅 레벨을 결정
    """
    pass


class ServoBusyError(AppError):  # AppError 상속
    """서보가 바쁨 상태일 때 발생하는 예외"""
    pass


class ServoFaultError(AppError): # AppError 상속
    """서보에 에러(bError)가 있을 때 발생하는 예외"""
    def __init__(self, axis_name: str, error_id: int, msg: str):
        self.axis_name = axis_name
        self.error_id = error_id
        self.message = msg
        # 부모 클래스 초기화 (로그 메시지로 쓰임)
        super().__init__(f"[{axis_name}] Hardware Fault (Code {error_id}): {msg}")


class RobotFaultError(AppError): # AppError 상속
    """로봇에 에러(Fault)가 있을 때 발생하는 예외"""
    def __init__(self, msg: str):
        super().__init__(f"[FANUC] Robot Fault: {msg}")