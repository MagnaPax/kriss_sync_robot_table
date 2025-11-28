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
    Service/ViewModel → EVENT_BUS.ui_log_message.emit()
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
    EVENT_BUS.ui_log_message.emit("작업 완료", "INFO")
"""

from utils.logger import get_logger
from core.event_bus import EVENT_BUS


class LogListener:
    """
    EventBus의 UI 로그 메시지를 Logger로 전달하는 중재자
    
    역할:
    - EVENT_BUS.ui_log_message 시그널 구독
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
        
        # EventBus의 ui_log_message 시그널 구독
        EVENT_BUS.ui_log_message.connect(self.on_log_message)
        
        self.logger.info("LogListener 초기화 완료 - EventBus와 Logger 연결됨")
    
    
    def on_log_message(self, message: str, level: str):
        """
        EventBus에서 발행된 로그 메시지 처리
        
        Args:
            message: 로그 메시지
            level: 로그 레벨 ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
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
    
    EVENT_BUS.ui_log_message.emit("디버그 메시지 테스트", "DEBUG")
    EVENT_BUS.ui_log_message.emit("정보 메시지 테스트", "INFO")
    EVENT_BUS.ui_log_message.emit("경고 메시지 테스트", "WARNING")
    EVENT_BUS.ui_log_message.emit("에러 메시지 테스트", "ERROR")
    EVENT_BUS.ui_log_message.emit("치명적 에러 테스트", "CRITICAL")
    
    # 3. 알 수 없는 레벨 테스트
    print("\n3️⃣  알 수 없는 로그 레벨 테스트:")
    EVENT_BUS.ui_log_message.emit("알 수 없는 레벨", "UNKNOWN")
    
    # 4. 로그 파일 확인
    from utils.logger import LoggerConfig
    print(f"\n4️⃣  로그 파일 위치:")
    print(f"   INFO 로그: {LoggerConfig.INFO_LOG}")
    print(f"   ERROR 로그: {LoggerConfig.ERROR_LOG}")
    
    print("\n" + "="*70)
    print("테스트 완료 - 로그 파일을 확인하세요")
    print("="*70 + "\n")
    
    sys.exit(0)