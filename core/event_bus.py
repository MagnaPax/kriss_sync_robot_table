# core/event_bus.py
"""
Event Bus (이벤트 허브)
----------------------
애플리케이션 전역의 이벤트(시그널)를 관리하는 싱글톤 허브

역할:
    - 위젯/모듈 간 간접 통신 (Loose Coupling)
        - 이 클래스를 통해 이벤트를 발행(emit)하고 구독(connect)하여 통신한다    
    - Publish-Subscribe 패턴 구현
    - 전역 이벤트 중재자

사용 규칙:
    1. 전역적이고 여러 모듈이 관심 있는 이벤트만 정의
    2. 부모-자식 간 단순 통신은 직접 시그널 사용
    3. 이벤트 이름은 과거형 사용 (xxx_changed, xxx_updated)
    4. 요청 이벤트는 xxx_requested 형식 사용

사용 예시:
    # 발행자 (Publisher)
    from core.event_bus import EVENT_BUS
    EVENT_BUS.robot_state_updated.emit({'x': 100, 'y': 200})
    
    # 구독자 (Subscriber)
    EVENT_BUS.robot_state_updated.connect(self.on_robot_moved)
"""

from PyQt6.QtCore import QObject, pyqtSignal
from typing import Optional, TypedDict, Literal
from utils.logger import Logger


# =========================================================================
# 데이터 구조 정의 (TypedDict)
# =========================================================================
class RobotState(TypedDict):
    x: float
    y: float
    z: float
    w: float
    p: float
    r: float
    state: Literal['idle', 'moving', 'error']

class TurntableState(TypedDict):
    angle: float
    rounds: int
    state: Literal['idle', 'rotating', 'error']



class EventBus(QObject):
    """
    애플리케이션 전역의 이벤트(시그널)를 관리하는 허브 (싱글톤)

    Attributes:
        connection_status_changed: 통신 연결 상태 변경 시그널
        robot_state_updated: 로봇 상태 업데이트 시그널
        turntable_state_updated: 턴테이블 상태 업데이트 시그널
        current_state_updated: 현재 상태 업데이트 시그널
        goto_requested: GoTo 요청 시그널
        macro_settings_changed: 매크로 설정 변경 시그널
        log_message_generated: 로그 메시지 생성 시그널
    """
    
    # 싱글톤 패턴
    _instance: Optional['EventBus'] = None
    _initialized: bool = False
    
    # =========================================================================
    # 시그널 정의
    # =========================================================================
    
    # --- 통신 관련 시그널 ---
    connection_status_changed = pyqtSignal(bool)
    """
    통신 연결 상태 변경 시그널
    
    Args:
        bool: True=연결됨, False=연결 끊김
    
    사용 예:
        EVENT_BUS.connection_status_changed.emit(True)
        EVENT_BUS.connection_status_changed.connect(self.on_connection_changed)
    """
    
    # --- 로봇/턴테이블 상태 시그널 ---
    robot_state_updated = pyqtSignal(RobotState)
    """
    로봇 상태 업데이트 시그널
    
    Args:
        dict: {
            'x': float - X 좌표 (mm)
            'y': float - Y 좌표 (mm)
            'z': float - Z 좌표 (mm)
            'w': float - W 각도 (deg)
            'p': float - P 각도 (deg)
            'r': float - R 각도 (deg)
            'state': str - 'idle' | 'moving' | 'error'
        }
    
    사용 예:
        EVENT_BUS.robot_state_updated.emit({
            'x': 100.0, 'y': 200.0, 'z': 50.0,
            'w': 0.0, 'p': 0.0, 'r': 0.0,
            'state': 'moving'
        })
    """
    
    turntable_state_updated = pyqtSignal(TurntableState)
    """
    턴테이블 상태 업데이트 시그널
    
    Args:
        dict: {
            'angle': float - 현재 각도 (deg)
            'rounds': int - 회전 횟수
            'state': str - 'idle' | 'rotating' | 'error'
        }
    """
    
    current_state_updated = pyqtSignal(dict)
    """
    현재 시스템 상태 업데이트 시그널
    
    Args:
        dict: {
            'm1_rpm': float - 모터 1 RPM
            'm2_rpm': float - 모터 2 RPM
            'robot_speed': float - 로봇 속도
            'pressure': float - 압력
            ...
        }
    """
    
    # --- UI 상호작용 시그널 ---
    goto_requested = pyqtSignal(dict)
    """
    로봇 이동 요청 시그널 (TargetPositionWidget의 GoTo 버튼)
    
    Args:
        dict: {
            'x': float, 'y': float, 'z': float,
            'w': float, 'p': float, 'r': float
        }
    
    사용 예:
        # 발행자 (TargetPositionWidget)
        EVENT_BUS.goto_requested.emit(position)
        
        # 구독자 (RobotController)
        EVENT_BUS.goto_requested.connect(self.move_to_position)
    """
    
    macro_settings_changed = pyqtSignal()
    """
    매크로 설정 변경 시그널 (MacroSettingsDialog에서 저장 시)
    
    Args:
        없음
    
    사용 예:
        # 발행자 (MacroSettingsDialog)
        EVENT_BUS.macro_settings_changed.emit()
        
        # 구독자 (TargetPositionWidget)
        EVENT_BUS.macro_settings_changed.connect(self._reload_macros)
    """
    
    # --- 시스템/로그 시그널 ---
    log_message_generated = pyqtSignal(str, str)
    """
    로그 메시지 생성 시그널
    
    Args:
        str: 메시지 내용
        str: 로그 레벨 ('DEBUG' | 'INFO' | 'WARNING' | 'ERROR')
    
    사용 예:
        EVENT_BUS.log_message_generated.emit("작업 완료", "INFO")
    """
    
    
    # =========================================================================
    # 싱글톤 구현
    # =========================================================================
    def __new__(cls) -> 'EventBus':
        """
        싱글톤 인스턴스 생성

        클래스(cls)를 받아 새로운 객체(인스턴스)를 생성하고 반환하는 메서드
        
        __new__가 성공적으로 객체를 생성하여 반환하면, 그 객체가 self가 되어 __init__ 메서드로 전달
        """

        # 최초 요청할때만 객체 생성, 그 뒤로는 같은 인스턴스 리턴
        if cls._instance is None:
            # __new__ 내부에서 발생할 수 있는 예외를 로깅하기 위해
            # 인스턴스 생성 전에 Logger를 먼저 초기화
            # Logger는 싱글톤이므로, 호출 자체로 초기화
            Logger()
            
            # 클래스 변수 _instance가 비어있으면 새로운 인스턴스를 생성
            # 여기서 에러 발생 시 Logger의 전역 예외 후크가 동작
            cls._instance = super().__new__(cls)

        # 생성된 인스턴스를 반환
        return cls._instance


    def __init__(self):
        """EventBus 초기화 (최초 1회만 실행)"""
        # _initialized 플래그를 확인하여 초기화가 이미 완료되었다면 즉시 리턴
        if EventBus._initialized:
            return

        # QObject의 생성자를 먼저 호출해야 한다
        super().__init__()

        # Logger 인스턴스를 생성하고 EventBus의 속성으로 만든다
        self.logger = Logger().logger

        # 디버그 모드에서 시그널 연결 추적 (선택적)
        self._setup_debug_logging()
        
        self.logger.info("EventBus 초기화 완료")
        EventBus._initialized = True


    def _setup_debug_logging(self):
        """
        개발 모드에서 시그널 발생 추적 (선택적)
        
        Note:
            성능에 영향을 줄 수 있으므로 개발 시에만 활성화
        """
        import os
        debug_mode = os.getenv("DEBUG_EVENT_BUS", "0") == "1"
        
        if not debug_mode:
            return
        
        # 모든 시그널에 로깅 연결
        self.robot_state_updated.connect(
            lambda data: self.logger.debug(f"[EventBus] robot_state_updated: {data}")
        )
        self.goto_requested.connect(
            lambda pos: self.logger.debug(f"[EventBus] goto_requested: {pos}")
        )
        self.macro_settings_changed.connect(
            lambda: self.logger.debug("[EventBus] macro_settings_changed")
        )
    
    
    # =========================================================================
    # 유틸리티 메서드
    # =========================================================================
    def disconnect_all(self, signal_name: Optional[str] = None):
        """
        시그널 연결 해제 (주로 테스트용)
        
        Args:
            signal_name: 특정 시그널 이름 (None이면 모든 시그널)
        
        사용 예:
            EVENT_BUS.disconnect_all('robot_state_updated')
            EVENT_BUS.disconnect_all()  # 모든 시그널
        """
        if signal_name:
            signal = getattr(self, signal_name, None)
            if signal:
                try:
                    signal.disconnect()
                    self.logger.debug(f"시그널 연결 해제: {signal_name}")
                except TypeError:
                    # 연결된 슬롯이 없음
                    pass
        else:
            # 모든 시그널 연결 해제
            for attr_name in dir(self):
                attr = getattr(self, attr_name)
                if isinstance(attr, pyqtSignal):
                    try:
                        attr.disconnect()
                    except TypeError:
                        pass
            self.logger.debug("모든 시그널 연결 해제")
    
    
    def get_signal_info(self) -> dict:
        """
        정의된 모든 시그널 정보 반환 (디버깅용)
        
        Returns:
            dict: 시그널 이름과 설명 딕셔너리
        """
        signals = {}
        for attr_name in dir(self):
            attr = getattr(self, attr_name)
            if isinstance(attr, pyqtSignal):
                doc = getattr(attr, '__doc__', 'No documentation')
                signals[attr_name] = doc.strip() if doc else 'No documentation'
        
        return signals


# =============================================================================
# 전역 인스턴스 (모듈 레벨 싱글톤)
# =============================================================================
EVENT_BUS = EventBus()
"""
전역 EventBus 인스턴스

사용 예:
    from core.event_bus import EVENT_BUS
    
    # 이벤트 발행
    EVENT_BUS.robot_state_updated.emit(state_data)
    
    # 이벤트 구독
    EVENT_BUS.robot_state_updated.connect(self.on_robot_moved)
"""


# =============================================================================
# 단독 실행 (테스트용)
# =============================================================================
if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication
    
    # QApplication 필요 (QObject 사용 시)
    app = QApplication(sys.argv)
    
    print("=" * 70)
    print("EventBus 테스트")
    print("=" * 70)
    
    # 1. 싱글톤 확인
    print("\n1️⃣  싱글톤 패턴 확인:")
    bus1 = EventBus()
    bus2 = EventBus()
    print(f"   bus1 ID: {id(bus1)}")
    print(f"   bus2 ID: {id(bus2)}")
    print(f"   동일 인스턴스: {bus1 is bus2}")
    
    # 2. 시그널 정보 출력
    print("\n2️⃣  정의된 시그널 목록:")
    signals = EVENT_BUS.get_signal_info()
    for name, doc in signals.items():
        print(f"   • {name}")
        print(f"     {doc[:60]}...")
    
    # 3. 시그널 발행/구독 테스트
    print("\n3️⃣  시그널 발행/구독 테스트:")
    
    def test_callback(data):
        print(f"   ✅ 콜백 실행됨: {data}")
    
    EVENT_BUS.robot_state_updated.connect(test_callback)
    EVENT_BUS.robot_state_updated.emit({'x': 100, 'y': 200, 'state': 'moving'})
    
    # 4. 연결 해제 테스트
    print("\n4️⃣  시그널 연결 해제:")
    EVENT_BUS.disconnect_all('robot_state_updated')
    print("   🔌 연결 해제 완료")
    
    EVENT_BUS.robot_state_updated.emit({'x': 300, 'y': 400, 'state': 'idle'})
    print("   (콜백이 실행되지 않아야 함)")
    
    print("\n" + "=" * 70)
    print("테스트 완료")
    print("=" * 70)
    
    sys.exit(0)