# core/event_bus.py
"""
Event Bus (이벤트 허브)
----------------------
"전역(앱 전체)"의 이벤트(시그널)를 관리하는 싱글톤 허브


설계 원칙:
1. 단일 책임: 오직 이벤트 허브로만 동작
2. Logger 독립: Logger에 의존하지 않음 (결합 제거)
3. 이벤트 네임스페이스: 계층화된 시그널 명명
4. 느슨한 결합: Publish-Subscribe 패턴


아키텍처:
    View → ViewModel → Service → Worker
                ↓
           EVENT_BUS (emit)
                ↓
         LogListener (subscribe)
                ↓
            Logger (record)

용도:
    여러 계층 / 여러 객체에 전달될 이벤트만 EventBus를 사용한다

    - 데이터 변경 이벤트
    - 시스템 상태 변경
    - 백그라운드 작업 완료 알림
    - 로봇 이동 완료
    - 파일 저장 성공/실패
    - 로그 메시지 발생

비유:
    Event Bus : 라디오 방송국(대한민국 전체에 뿌려진다)
    Signals:    라디오 주파수
    emits:      해당 주파수로 방송 송출
    connect:    청취자가 특정 주파수를 청취하는 것


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
    from core.event_bus import EVENT_BUS

    # 발행자 (Publisher)
    EVENT_BUS.ui_log_message.emit("작업 완료", "INFO")
    EVENT_BUS.robot_position_changed.emit(position_data)

    # 구독자 (Subscriber)
    EVENT_BUS.ui_log_message.connect(self.on_log_message)
"""

# core/event_bus.py
"""
Event Bus (이벤트 허브)
---------------------
애플리케이션 전역 이벤트 관리 싱글톤

설계 원칙:
1. 단일 책임: 오직 이벤트 허브로만 동작
2. Logger 독립: Logger에 의존하지 않음 (결합 제거)
3. 이벤트 네임스페이스: 계층화된 시그널 명명
4. 느슨한 결합: Publish-Subscribe 패턴

아키텍처:
    View → ViewModel → Service → Worker
                ↓
           EVENT_BUS (emit)
                ↓
         LogListener (subscribe)
                ↓
            Logger (record)

사용법:
    from core.event_bus import EVENT_BUS
    
    # 이벤트 발행
    EVENT_BUS.ui_log_message.emit("작업 완료", "INFO")
    EVENT_BUS.robot_position_changed.emit(position_data)
    
    # 이벤트 구독
    EVENT_BUS.ui_log_message.connect(self.on_log_message)
"""

from PyQt6.QtCore import QObject, pyqtSignal, QMetaObject, QMetaMethod
from typing import Optional, Literal
from dataclasses import dataclass


# =============================================================================
# 데이터 구조 정의
# 휴먼에러 발생하면 IDE, 타입검사기에 의해 경고 나타내도록 하기 위해
# =============================================================================
@dataclass
class RobotState:
    """로봇 상태 데이터 구조"""
    x: float
    y: float
    z: float
    w: float
    p: float
    r: float
    state: Literal['idle', 'moving', 'error']


@dataclass
class TurntableState:
    """턴테이블 상태 데이터 구조"""
    angle: float
    rounds: int
    state: Literal['idle', 'rotating', 'error']


# =============================================================================
# EventBus (단일 책임: 이벤트 허브)
# =============================================================================
class EventBus(QObject):
    """
    애플리케이션 전역 이벤트 허브 (싱글톤)
    
    책임:
    - 이벤트 발행/구독 중재
    - 모듈 간 느슨한 결합 제공
    
    설계:
    - Logger에 의존하지 않음
    - 로깅은 LogListener가 담당
    - EventBus는 도메인 이벤트만 관리
    """
    
    # =========================================================================
    # System Events (시스템 레벨)
    # =========================================================================
    system_error = pyqtSignal(str)
    """
    시스템 에러 발생 시그널
    
    Args:
        str: 에러 메시지
    
    Example:
        EVENT_BUS.system_error.emit("PLC 연결 실패")
    """
    
    system_info = pyqtSignal(str)
    """
    시스템 정보 시그널
    
    Args:
        str: 정보 메시지
    """
    
    app_shutting_down = pyqtSignal()
    """
    앱 종료 시그널
    
    Example:
        EVENT_BUS.app_shutting_down.emit()
    """
    
    
    # =========================================================================
    # UI Events (UI 레벨 - 로그 전용)
    # =========================================================================
    ui_log_message = pyqtSignal(str, str)
    """
    UI 로그 메시지 시그널 (LogListener가 구독)
    
    Args:
        str: 메시지 내용
        str: 로그 레벨 ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
    
    Example:
        EVENT_BUS.ui_log_message.emit("매크로 로드 완료", "INFO")
        EVENT_BUS.ui_log_message.emit("파일 파싱 실패", "ERROR")
    
    Note:
        이 시그널은 Logger와 독립적입니다.
        LogListener가 이 시그널을 구독하여 Logger에 전달합니다.
    """
    
    
    # =========================================================================
    # Connection Events (통신 레벨)
    # =========================================================================
    connection_status_changed = pyqtSignal(bool)
    """
    통신 연결 상태 변경 시그널
    
    Args:
        bool: True=연결됨, False=연결 끊김
    
    Example:
        EVENT_BUS.connection_status_changed.emit(True)
        EVENT_BUS.connection_status_changed.connect(self.on_connection_changed)
    """
    
    
    # =========================================================================
    # Robot Events (로봇 도메인)
    # =========================================================================
    robot_position_changed = pyqtSignal(RobotState)
    """
    로봇 위치 변경 시그널
    
    Args:
        RobotState: 로봇 상태 데이터
    
    Example:
        state = RobotState(x=100.0, y=200.0, z=50.0,
                        w=0.0, p=0.0, r=0.0, state='moving')
        EVENT_BUS.robot_position_changed.emit(state)
    """
    
    robot_state_updated = pyqtSignal(RobotState)
    """
    로봇 상태 업데이트 시그널 (robot_position_changed의 별칭)
    
    Note:
        하위 호환성을 위해 유지
    """
    
    turntable_state_updated = pyqtSignal(TurntableState)
    """
    턴테이블 상태 업데이트 시그널
    
    Args:
        TurntableState: 턴테이블 상태 데이터
    """
    
    current_state_updated = pyqtSignal(dict)
    """
    현재 시스템 상태 업데이트 시그널
    
    Args:
        dict: {
            'm1_rpm': float,
            'm2_rpm': float,
            'robot_speed': float,
            'pressure': float,
            ...
        }
    """
    
    
    # =========================================================================
    # UI Interaction Events (UI 상호작용)
    # =========================================================================
    goto_requested = pyqtSignal(dict)
    """
    로봇 이동 요청 시그널
    
    Args:
        dict: {'x': float, 'y': float, 'z': float,
            'w': float, 'p': float, 'r': float}
    
    Example:
        # 발행자 (TargetPositionWidget)
        position = {'x': 100.0, 'y': 200.0, ...}
        EVENT_BUS.goto_requested.emit(position)
        
        # 구독자 (RobotController)
        EVENT_BUS.goto_requested.connect(self.move_to_position)
    """
    
    macro_updated = pyqtSignal(dict)
    """
    매크로 업데이트 시그널
    
    Args:
        dict: 매크로 데이터
    """
    
    macro_settings_changed = pyqtSignal()
    """
    매크로 설정 변경 시그널 (MacroSettingsDialog에서 저장 시)
    
    Example:
        # 발행자 (MacroSettingsDialog)
        EVENT_BUS.macro_settings_changed.emit()
        
        # 구독자 (TargetPositionWidget)
        EVENT_BUS.macro_settings_changed.connect(self._reload_macros)
    """
    
    
    # =========================================================================
    # 싱글톤 구현
    # =========================================================================
    _instance: Optional['EventBus'] = None
    
    
    def __new__(cls) -> 'EventBus':
        """
        싱글톤 인스턴스 생성
        
        클래스(cls)를 받아 새로운 객체(인스턴스)를 생성하고 반환하는 메서드

        __new__가 성공적으로 객체를 생성하여 반환하면, 그 객체가 self가 되어 __init__ 메서드로 전달
        """

        # 최초 요청할때만 객체 생성, 그 뒤로는 같은 인스턴스 리턴
        if cls._instance is None:

            # 클래스 변수 _instance가 비어있으면 새로운 인스턴스를 생성
            # 여기서 에러 발생 시 Logger의 전역 예외 후크가 동작            
            cls._instance = super().__new__(cls)

        # 생성된 인스턴스 반환
        return cls._instance
    
    
    def __init__(self):
        """
        EventBus 초기화 (최초 1회만 실행)
        
        - EventBus는 로깅하지 않음
        - 로깅은 LogListener가 담당
        """

        # QObject의 생성자를 먼저 호출해야 된다 (RuntimeError 방지)
        super().__init__()        

        # _initialized 플래그를 확인하여 초기화가 이미 완료되었다면 즉시 리턴
        # _initialized는 QObject 생성자 호출 이후에만 사용
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        # 초기화 완료 표시(flag)
        self._initialized = True
    
    
    # =========================================================================
    # 유틸리티 메서드
    # =========================================================================
    def disconnect_all(self, signal_name: Optional[str] = None):
        """
        시그널 연결 해제 (주로 테스트용)
        
        Args:
            signal_name: 특정 시그널 이름 (None이면 모든 시그널)
        
        Example:
            EVENT_BUS.disconnect_all('robot_position_changed')
            EVENT_BUS.disconnect_all()  # 모든 시그널
        """
        if signal_name:
            # 특정 시그널만 해제
            if not hasattr(self, signal_name):
                return
            
            # 시그널을 가져와서 해제
            signal = getattr(self, signal_name)

            try:
                signal.disconnect()
            except TypeError:
                # 연결된 슬롯이 없음
                pass
        else:
            # 모든 시그널 연결 해제 (QMetaObject를 사용하여 정확하게 식별)
            meta_obj: Optional[QMetaObject] = self.metaObject()

            if meta_obj is None:
                return
            
            for i in range(meta_obj.methodCount()):
                method = meta_obj.method(i)

                # 메서드 타입이 시그널인 경우에만 처리
                if method.methodType() == QMetaMethod.MethodType.Signal:
                    try:
                        # 시그널 이름(bytes)을 str으로 디코딩
                        signal_name_bytes = method.name()
                        signal_name_str = signal_name_bytes.data().decode()
                        
                        # QObject의 기본 시그널(예: destroyed, objectNameChanged)은 제외
                        if signal_name_str in ['destroyed', 'objectNameChanged']:
                            continue
                        
                        signal = getattr(self, signal_name_str, None)
                        if signal:
                            signal.disconnect()

                    except (TypeError, AttributeError):
                        # 연결된 슬롯이 없는 경우 발생하는 예외는 무시
                        pass
    
    
    def get_signal_info(self) -> dict:
        """
        정의된 모든 시그널 정보 반환 (디버깅용)
        
        Returns:
            dict: {signal_name: docstring}
        """
        signals = {}
        meta_obj = self.metaObject()
        
        if meta_obj is None:
            return signals
        
        # QMetaObject를 순회하며 시그널 타입의 메서드를 찾는다
        for i in range(meta_obj.methodCount()):
            method = meta_obj.method(i)

            if method.methodType() == QMetaMethod.MethodType.Signal:
                try:
                    # 시그널 이름을 바이트에서 문자열로 디코딩
                    signal_name = method.name().data().decode('utf-8')
                    
                    # QObject 기본 시그널 제외
                    if signal_name in ['destroyed', 'objectNameChanged']:
                        continue
                    
                    # Docstring 가져오기
                    # __doc__ (설명)은 pyqtSignal 객체 자체에서 가져온다
                    signal_attr = getattr(EventBus, signal_name, None)
                    doc = 'No documentation'    # 기본값
                    
                    # 'signal_attr.__doc__'가 None이나 빈 문자열이 아닌지 확인
                    if hasattr(signal_attr, '__doc__') and signal_attr.__doc__:
                        doc = signal_attr.__doc__.strip()
                    
                    signals[signal_name] = doc
                except Exception:
                    pass
        
        return signals


# =============================================================================
# 전역 인스턴스
# =============================================================================
EVENT_BUS = EventBus()
"""
전역 EventBus 인스턴스

Example:
    from core.event_bus import EVENT_BUS
    
    # 이벤트 발행
    EVENT_BUS.ui_log_message.emit("작업 완료", "INFO")
    EVENT_BUS.robot_position_changed.emit(state_data)
    
    # 이벤트 구독
    EVENT_BUS.ui_log_message.connect(self.on_log_message)
    EVENT_BUS.robot_position_changed.connect(self.on_robot_moved)
"""










"""
=============================================================================
-- Smoke Test --

python -m core.event_bus
=============================================================================
"""
if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication
    
    # QApplication 필요 (QObject 사용 시)
    app = QApplication(sys.argv)
    
    print("=" * 70)
    print("EventBus 테스트 (Logger 독립)")
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
    
    # 네임스페이스별 그룹화
    categories = {
        'System': ['system_', 'app_'],
        'UI': ['ui_'],
        'Connection': ['connection_'],
        'Robot': ['robot_', 'turntable_', 'current_'],
        'Interaction': ['goto_', 'macro_']
    }
    
    for category, prefixes in categories.items():
        print(f"\n   [{category} Events]")
        for name, doc in signals.items():
            if any(name.startswith(p) for p in prefixes):
                doc_line = doc.split('\n')[0].strip()
                print(f"   • {name}")
                print(f"     {doc_line[:60]}...")
    
    # 3. 이벤트 발행/구독 테스트
    print("\n3️⃣  이벤트 발행/구독 테스트:")
    
    # 콜백 함수 정의
    def robot_callback(data: RobotState):
        print(f"   ✅ [Robot] 콜백 실행됨: state={data.state}")
    
    def log_callback(message: str, level: str):
        print(f"   ✅ [Log] 콜백 실행됨: [{level}] {message}")
    
    def macro_callback():
        print(f"   ✅ [Macro] 콜백 실행됨")
    
    # 시그널 연결
    EVENT_BUS.robot_position_changed.connect(robot_callback)
    EVENT_BUS.ui_log_message.connect(log_callback)
    EVENT_BUS.macro_settings_changed.connect(macro_callback)
    
    # 이벤트 발행
    print("\n   [이벤트 발행]")
    
    test_state = RobotState(
        x=100.0, y=200.0, z=0.0,
        w=0.0, p=0.0, r=0.0,
        state='moving'
    )
    EVENT_BUS.robot_position_changed.emit(test_state)
    EVENT_BUS.ui_log_message.emit("테스트 메시지", "INFO")
    EVENT_BUS.macro_settings_changed.emit()
    
    # 4. 연결 해제 테스트
    print("\n4️⃣  시그널 연결 해제:")
    EVENT_BUS.disconnect_all('robot_position_changed')
    print("   🔌 'robot_position_changed' 연결 해제 완료")
    
    test_state_idle = RobotState(
        x=300.0, y=400.0, z=0.0,
        w=0.0, p=0.0, r=0.0,
        state='idle'
    )
    EVENT_BUS.robot_position_changed.emit(test_state_idle)
    print("   (콜백이 실행되지 않아야 함)")
    
    print("\n" + "=" * 70)
    print("테스트 완료")
    print("=" * 70)
    
    sys.exit(0)
