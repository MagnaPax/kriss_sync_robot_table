# core/log_listener.py
"""
Log Listener (EventBus ↔ Logger 중재자)
--------------------------------------
EventBus와 Logger를 느슨하게 연결하는 중재자

설계 원칙:
- EventBus와 Logger의 강결합 제거
- 단방향 의존성: LogListener → EventBus, Logger
- EventBus는 LogListener를 모름
- Logger는 LogListener를 모름

아키텍처:
    Service/ViewModel → EVENT_BUS.log.message.emit()
                              ↓
                        LogListener (subscribe)
                              ↓
                        Logger.info/error()

사용법:
    # main.py에서 앱 시작 시 한 번만 생성
    from core.log_listener import LogListener
    
    log_listener = LogListener()
    
    # 이후 어디서든 로그 발행 가능
    from core.event_bus import EVENT_BUS
    EVENT_BUS.log.message.emit("작업 완료", "INFO")
"""

from utils.logger import get_logger
from core.event_bus import EVENT_BUS


class LogListener:
    """
    EventBus의 UI 로그 메시지를 Logger로 전달하는 중재자
    
    역할:
    - EVENT_BUS.log.message 시그널 구독
    - 로그 레벨에 따라 Logger의 적절한 메서드 호출
    - EventBus와 Logger의 결합 제거
    
    Note:
        앱 시작 시 한 번만 생성하면 자동으로 동작
    """
    
    def __init__(self):
        """
        LogListener 초기화 및 시그널 연결
        """
        # Logger 인스턴스 생성
        self.logger = get_logger(__name__)
        
        # EventBus의 log.message 시그널 구독
        EVENT_BUS.log.message.connect(self.on_log_message)
        
        self.logger.info("LogListener 초기화 완료 - EventBus와 Logger 연결됨")
    
    
    def on_log_message(self, message: str, level: str):
        """
        EventBus에서 발행된 로그 메시지 처리
        
        Args:
            message: 로그 메시지
            level: 로그 레벨 ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')

        -----------------------------------------------------------------------
        [로그 레벨별 사용 가이드]
        
        1. DEBUG (디버그)
        - 개발 및 문제 해결을 위한 상세 정보
        - 변수의 값, 내부 동작 흐름, 함수 진입/종료 등
        - 운영 환경에서는 보통 꺼둠
        - 예:   함수 A 진입함
                현재 변수 x의 값은 10.5
                반복문 5번째 실행 중

        2. INFO (정보)
        - 시스템의 정상적인 작동 흐름 및 중요 이벤트
        - 사용자 행동(버튼 클릭), 상태 변경(연결됨), 주요 프로세스 완료
        - 예:   PLC 연결 성공
                매크로 데이터 로드 완료 (4개 항목)
                사용자 이동 명령(GoTo) 요청: {'x': 10.5 ...}

        3. WARNING (경고)
        - 에러는 아니지만 주의가 필요한 상황
        - 예상치 못한 입력값, 자동 복구된 가벼운 문제, 리소스 부족 임박
        - 예:   이동 명령 실패: 좌표값 입력 오류 (문자 포함됨)
                이전 작업이 아직 진행 중입니다 (중복 요청 무시됨)

        4. ERROR (에러)
        - 기능 수행 실패, 예외 발생 (시스템은 계속 동작 가능)
        - API 호출 실패, 파일 읽기/쓰기 실패, 로직 오류
        - 예:   TwinCAT 접속 시도(1) 실패: Timeout
                매크로 파일 로드 실패
                작업 중 오류 발생: ConnectionError

        5. CRITICAL (치명적)
        - 시스템이 더 이상 동작할 수 없는 심각한 오류
        - 필수 하드웨어 고장, 데이터 손실, 앱 크래시 직전
        - 예:   TwinCAT 연결 완전 끊김 (복구 불가)
                메모리 부족으로 강제 종료
        -----------------------------------------------------------------------
        """
        level_upper = level.upper()
        
        if level_upper == "DEBUG":
            self.logger.debug(message)
        elif level_upper == "INFO":
            self.logger.info(message)
        elif level_upper == "WARNING":
            self.logger.warning(message)
        elif level_upper == "ERROR":
            self.logger.error(message)
        elif level_upper == "CRITICAL":
            self.logger.critical(message)
        else:
            # 알 수 없는 레벨은 INFO로 처리
            self.logger.info(f"[{level}] {message}")








# =============================================================================
# Smoke Test
# python -m core.log_listener
# =============================================================================
if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication
    
    print("\n" + "="*70)
    print("LogListener 테스트")
    print("="*70 + "\n")
    
    # QApplication 필요
    app = QApplication(sys.argv)
    
    # 1. LogListener 생성 (자동으로 EventBus 구독)
    print("1️⃣  LogListener 초기화:")
    listener = LogListener()
    
    # 2. EventBus를 통한 로그 발행 테스트
    print("\n2️⃣  EventBus를 통한 로그 발행:")
    print("   (콘솔과 파일에 로그가 기록되어야 함)\n")
    
    EVENT_BUS.log.message.emit("디버그 메시지 테스트", "DEBUG")
    EVENT_BUS.log.message.emit("정보 메시지 테스트", "INFO")
    EVENT_BUS.log.message.emit("경고 메시지 테스트", "WARNING")
    EVENT_BUS.log.message.emit("에러 메시지 테스트", "ERROR")
    EVENT_BUS.log.message.emit("치명적 에러 테스트", "CRITICAL")
    
    # 3. 알 수 없는 레벨 테스트
    print("\n3️⃣  알 수 없는 로그 레벨 테스트:")
    EVENT_BUS.log.message.emit("알 수 없는 레벨", "UNKNOWN")
    
    # 4. 로그 파일 확인
    from utils.logger import LoggerConfig
    print(f"\n4️⃣  로그 파일 위치:")
    print(f"   INFO 로그: {LoggerConfig.INFO_LOG}")
    print(f"   ERROR 로그: {LoggerConfig.ERROR_LOG}")
    
    print("\n" + "="*70)
    print("테스트 완료 - 로그 파일을 확인하세요")
    print("="*70 + "\n")
    
    sys.exit(0)