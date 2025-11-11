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

from PyQt6.QtCore import QObject, pyqtSignal, QMetaObject, QMetaMethod
from typing import Optional, Literal
from dataclasses import dataclass
from utils.logger import Logger


# =========================================================================
# 데이터 구조 정의 (TypedDict)
# IDE, 타입검사기에 의해 휴먼에러가 경고된다
# =========================================================================
@dataclass
class RobotState:
    x: float
    y: float
    z: float
    w: float
    p: float
    r: float
    state: Literal['idle', 'moving', 'error']

@dataclass
class TurntableState:
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
        dict (RobotState): {
            'x': float - X 좌표 (mm)
            'y': float - Y 좌표 (mm)
            'z': float - Z 좌표 (mm)
            'w': float - W 각도 (deg)
            'p': float - P 각도 (deg)
            'r': float - R 각도 (deg)
            'state': str - 로봇 상태 ('idle', 'moving', 'working', 'error')
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
        dict (TurntableState): {
            'angle': float - 현재 각도 (deg)
            'rounds': int - 회전 횟수
            'state': str - 턴테이블 상태 ('idle', 'rotating', 'error')
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
    # def disconnect_all(self, signal_name: str):
        """
        시그널 연결 해제 (주로 테스트용)
        
        Args:
            signal_name: 특정 시그널 이름 (None이면 모든 시그널)
        
        사용 예:
            EVENT_BUS.disconnect_all('robot_state_updated')
            EVENT_BUS.disconnect_all()  # 모든 시그널
        """

        # 에러 처리


        if signal_name:

            if not hasattr(self, signal_name):
                self.logger.warning(f"시그널 없음: {signal_name}")
                return
            
            # 시그널을 가져와서 해제
            signal = getattr(self, signal_name, None)
            if signal:
                try:
                    signal.disconnect()
                    self.logger.debug(f"시그널 연결 해제: {signal_name}")
                except TypeError:
                    # 연결된 슬롯이 없음
                    pass
        else:
            # 모든 시그널 연결 해제 (QMetaObject를 사용하여 정확하게 식별)
            meta_obj: Optional[QMetaObject] = self.metaObject()

            if meta_obj is None:
                self.logger.warning("EventBus: metaObject()가 None을 반환했습니다. "
                                    "모든 시그널을 해제할 수 없습니다.")
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

                    except TypeError:
                        # 연결된 슬롯이 없는 경우 발생하는 예외는 무시
                        pass
                    except Exception as e:
                        # 디코딩 오류 등 예기치 않은 문제 로깅
                        self.logger.warning(f"시그널 해제 중 오류 발생: {e}")
                        
            self.logger.debug("모든 시그널 연결 해제 완료")


    def get_signal_info(self) -> dict:
        """
        정의된 모든 시그널 정보 반환 (디버깅용)
        
        Returns:
            dict: 시그널 이름과 설명 딕셔너리
        """
        signals = {}
        meta_obj = self.metaObject()
        
        if meta_obj is None:
            return signals

        # QMetaObject를 순회하며 시그널 타입의 메서드를 찾습니다.
        for i in range(meta_obj.methodCount()):
            method = meta_obj.method(i)
            if method.methodType() == QMetaMethod.MethodType.Signal:
                try:
                    # 시그널 이름을 바이트에서 문자열로 디코딩
                    signal_name = method.name().data().decode('utf-8')
                    
                    # QObject의 기본 시그널(destroyed, objectNameChanged)은 제외
                    if signal_name in ['destroyed', 'objectNameChanged']:
                        continue
                        
                    # __doc__ (설명)은 pyqtSignal 객체 자체에서 가져온다
                    # signal_attr = getattr(self, signal_name, None)
                    signal_attr = getattr(EventBus, signal_name, None)

                    doc = 'No documentation' # 기본값

                    # if signal_attr and hasattr(signal_attr, '__doc__') and getattr(signal_attr, '__doc__'):
                    #     doc = getattr(signal_attr, '__doc__', 'No documentation').strip()
                        
                    # signals[signal_name] = doc

                    # 'signal_attr.__doc__'가 None이나 빈 문자열이 아닌지 확인
                    if hasattr(signal_attr, '__doc__') and signal_attr.__doc__:
                        doc = signal_attr.__doc__.strip()
                        
                    signals[signal_name] = doc                        
                except Exception as e:
                    self.logger.warning(f"Error processing signal: {e}")
        
        return signals


    def log_emit(self, signal_name: str, *args):
        """
        emit 시 자동 로깅 (가변 인자 *args 사용)
        
        Args:
            signal_name (str): emit할 시그널의 이름
            *args: 시그널에 전달할 0개 이상의 인자

        사용 예제:
            # 1. 인자 1개 (dict)
            EVENT_BUS.log_emit('robot_state_updated', test_state)

            # 2. 인자 2개 (str, str)
            EVENT_BUS.log_emit('log_message_generated', "작업 완료", "INFO")

            # 3. 인자 0개
            EVENT_BUS.log_emit('macro_settings_changed')
        """
        self.logger.debug(f"이벤트 발행: {signal_name} - {args}")

        try:
            signal = getattr(self, signal_name)
            signal.emit(*args)  # args로 인자를 압축 해제 해서 전달
        except AttributeError:
            self.logger.error(f"[log_emit] `{signal_name}` 라는 시그널 없음")
        except TypeError as e:
            # 인자 갯수 불일치 시 발생하는 오류
            self.logger.error(f"[log_emit] `{signal_name}` 시그널 emit 오류: {e}")








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
"""
실행 명령어
python -m core.event_bus
"""
# =============================================================================
if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication
    
    # QApplication 필요 (QObject 사용 시)
    app = QApplication(sys.argv)
    
    print("=" * 70)
    print("EventBus 테스트 (log_emit 사용)")
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
        # Docstring의 첫 줄만 간략하게 표시
        doc_line = doc.split('\n')[0].strip()
        print(f"     {doc_line[:60]}...")

    # 3. log_emit 발행/구독 테스트
    print("\n3️⃣  `log_emit` 발행/구독 테스트:")
    
    # --- 테스트용 콜백 함수 정의 ---
    def robot_callback(data: RobotState):
        print(f"   ✅ [Robot] 콜백 실행됨: {data.state}")

    def log_callback(message, level):
        print(f"   ✅ [Log] 콜백 실행됨: [{level}] {message}")

    def macro_callback():
        print(f"   ✅ [Macro] 콜백 실행됨 (인자 없음)")
    
    # --- 시그널 연결 ---
    EVENT_BUS.robot_state_updated.connect(robot_callback)
    EVENT_BUS.log_message_generated.connect(log_callback)
    EVENT_BUS.macro_settings_changed.connect(macro_callback)

    # --- 테스트용 데이터 ---
    test_state = RobotState(
        x=100.0, y=200.0, z=0.0,
        w=0.0, p=0.0, r=0.0,
        state='moving'
    )

    # --- log_emit으로 발행 ---
    
    # [테스트 1] 인자가 1개 (dict)인 시그널
    print("\n   [테스트 1: 인자 1개 (dict)]")
    # logger.debug("이벤트 발행: robot_state_updated - ({...},)")가 출력됨
    EVENT_BUS.log_emit('robot_state_updated', test_state)

    # [테스트 2] 인자가 2개 (str, str)인 시그널
    print("\n   [테스트 2: 인자 2개 (str, str)]")
    # logger.debug("이벤트 발행: log_message_generated - ('테스트 메시지', 'INFO')")가 출력됨
    EVENT_BUS.log_emit('log_message_generated', "테스트 메시지", "INFO")

    # [테스트 3] 인자가 0개인 시그널
    print("\n   [테스트 3: 인자 0개]")
    # logger.debug("이벤트 발행: macro_settings_changed - ()")가 출력됨
    EVENT_BUS.log_emit('macro_settings_changed')
    
    # [테스트 4] 존재하지 않는 시그널 (오류 처리 테스트)
    print("\n   [테스트 4: 존재하지 않는 시그널]")
    # logger.error("[log_emit] `없는_시그널` 라는 시그널 없음")이 출력됨
    EVENT_BUS.log_emit('없는_시그널', 123)


    # 4. 연결 해제 테스트
    print("\n4️⃣  시그널 연결 해제:")
    EVENT_BUS.disconnect_all('robot_state_updated')
    print("   🔌 'robot_state_updated' 연결 해제 완료")
    
    # 새 데이터
    test_state_idle = RobotState(
        x=300.0, y=400.0, z=0.0,
        w=0.0, p=0.0, r=0.0,
        state='idle'
    )
    
    # log_emit을 호출하면 "이벤트 발행:" 로그는 출력되지만,
    # 연결이 해제되었으므로 콜백은 실행되지 않아야 함
    EVENT_BUS.log_emit('robot_state_updated', test_state_idle)
    print("   (로그는 출력되지만, [Robot] 콜백은 실행되지 않아야 함)")
    
    print("\n" + "=" * 70)
    print("테스트 완료")
    print("=" * 70)
    
    sys.exit(0)
