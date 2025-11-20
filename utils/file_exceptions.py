# utils/file_exceptions.py

class FileOperationError(Exception):
    """
    파일 입출력 과정에서 발생하는 예외를 도메인 특화 예외로 캡슐화(Wrapping)

    일반적인 Python 예외보다 더 많은 정보를 담아서 호출부에서 오류의 원인을 정확히 파악하고 대응할 수 있게 하기 위해

    
    유용성:
        단일 처리점: 호출부 코드는 수많은 내장 예외(FileNotFoundError, IOError, PermissionError 등) 를 처리하는 대신 오직 FileOperationError 하나만 try-except로 처리하면 된다

        의도 명확화: 예외가 발생했을 때 파일 작업과 관련된 문제임을 즉시 알 수 있다

        상세 정보 제공: 예외 객체에 경로와 원본 예외가 포함되어 있어, 로깅(Logging) 및 사용자 피드백에 유용하다. (예: e.original을 확인하여 FileNotFoundError일 때만 특별 처리)


    사용 예:
        from utils.file_handler import load_json

        def load_macro(self, path: Path):
            try:
                return load_json(path)

            except FileOperationError as e:

                # 1) FileNotFoundError → 정상 작동(첫 시작일때는 파일이 없는것이 정상)
                if isinstance(e.original, FileNotFoundError):
                    EVENT_BUS.log_emit(
                        f"[매크로 파일 없음] 새 파일 생성 예정: {path}",
                        "INFO"
                    )
                    return self.DEFAULT_MACRO_DATA.copy()

                # 2) 진짜 에러만 로그 발생
                EVENT_BUS.log_emit(
                    f"[매크로 로드 오류] {e} — 원인:{type(e.original).__name__}, 파일:{e.path}",
                    "ERROR",
                )
                return None        
    """

    def __init__(self, message, original_exc, path):
        super().__init__(message)
        self.original = original_exc
        self.path = path
