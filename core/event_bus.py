# core/event_bus.py
from PyQt6.QtCore import QObject, pyqtSignal


class EventBus(QObject):
    """
    애플리케이션 전역의 이벤트(시그널)를 관리하는 싱글톤 허브.

    위젯이나 모듈 간의 직접적인 참조 없이, 이 클래스를 통해
    이벤트를 발행(emit)하고 구독(connect)하여 통신한다
    """

    # 싱글톤 디자인 패턴
    _instance = None

    # --- 시그널 정의 ---
    # 각 시그널은 전달할 데이터의 타입을 명시합니다.

    # 통신 상태 변경 시그널
    connection_status_changed = pyqtSignal(bool)  # True: connected, False: disconnected

    # 로봇/턴테이블 데이터 업데이트 시그널
    robot_state_updated = pyqtSignal(dict)      # 예: {'x': 1.0, 'height': 0.5, 'state': 'running'}
    turntable_state_updated = pyqtSignal(dict)  # 예: {'angle': 90.0, 'rounds': 1, 'state': 'waiting'}
    current_state_updated = pyqtSignal(dict)    # 예: {'m1_rpm': 100, 'robot_speed': 50, ...}

    # UI 상호작용 시그널
    goto_requested = pyqtSignal(dict)           # TargetPositionWidget에서 'GoTo' 버튼 클릭 시
    macro_settings_changed = pyqtSignal()       # MacroSettingsDialog에서 설정 저장 시

    # 시스템/로그 메시지 시그널
    log_message_generated = pyqtSignal(str, str) # (message, level)

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

# 다른 모듈에서 쉽게 접근할 수 있도록 싱글톤 인스턴스를 export 합니다.
EVENT_BUS = EventBus()
