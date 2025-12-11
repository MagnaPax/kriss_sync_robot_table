# core/event_bus.py
"""
EventBus

    앱 전체에서 사용되는 전역 Publish/Subscribe 이벤트 허브

    1:N 혹은 Asyncronize(비동기)작업에 사용

    (여러!!!) 계층 / (여러!!!) 객체에 전달될 이벤트만 EventBus를 사용


비유:
    Event Bus : 라디오 방송국(대한민국 전체에 뿌려진다)
    Signals:    라디오 주파수
    emits:      해당 주파수로 방송 송출
    connect:    청취자가 특정 주파수를 청취하는 것



용도:
- 사용자(UI)에 표시할 로그 메시지
- Worker / Service → ViewModel / View 로 전달되는 비동기 이벤트
- 여러 UI가 동시에 수신해야 하는 Domain Event
- 시스템 상태 변화 이벤트
- 데이터 변경 이벤트
- 백그라운드 작업 완료 알림
- 로봇 이동 완료
- 파일 저장 성공/실패

Worker ----┐
           |
Service ---┤----> EventBus ----> View(UI)
           |
ViewModel -┘



사용하면 안 되는 경우 ❌:
- View → ViewModel (직접 호출)
- ViewModel → Service (직접 호출)
- Service → Worker (직접 호출)
- Model 객체 간 상호작용 (모델은 순수 비즈니스 로직)
- 내부 디버그용 이벤트 (Logger.debug 사용)

[직접 호출]
View → ViewModel → Service → Worker





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
    EVENT_BUS.시그널이름.emit("작업 완료", "INFO")

    # 구독자 (Subscriber)
    EVENT_BUS.시그널이름.connect(self.on_log_message)
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




class EventBus(QObject):
    """전역 이벤트 버스"""
    
    # =========================================================================
    # System-level Events (전역 시스템 이벤트)
    # =========================================================================
    system_error = pyqtSignal(str)
    """
    시스템 에러 발생 시그널 - 시스템의 치명적 오류

    시스템의 치명적 오류는 여러 UI/뷰모델/서비스가 동시에 반응해야 한다.
        예: PLC 연결 실패 → 상태 UI, 콘솔 UI, 팝업 UI 등이 동시에 반응 필요.
    
    Args:
        str: 에러 메시지
    
    Example:
        EVENT_BUS.system_error.emit("PLC 연결 실패")
    """
    
    system_info = pyqtSignal(str)
    """
    시스템 정보 메시지
        예: “로봇 초기화 완료”
    
    Args:
        str: 정보 메시지
    """

    app_shutting_down = pyqtSignal()
    """
    애플리케이션 종료 시작 시그널
    
    역할:
        - 앱이 종료되기 직전에 모든 모듈에게 알림
        - 리소스 정리, 파일 저장, 스레드 종료 등의 기회를 제공
        
    청취 대상:
        - PLCService (연결 해제)
        - LogListener (로그 파일 닫기)
        - ConfigManager (설정 저장)
    """


    # =========================================================================
    # UI Log Events (UI + Logger 출력)
    # =========================================================================
    # TODO: 다음 프로젝트때는 아래처럼 개선하기
    # pyqtSignal(str, str, str) -> 메시지, 레벨, 로그 발생 장소
    ui_log_message = pyqtSignal(str, str)
    """
    사용자에게 전달(=UI에 표시)해야 하거나 관리자에게 알려야 하는(=로그 파일 기록) 모든 로그 메시지
        -> ∴ LogListener가 청취해서 로그 기록에 사용한다
        -> ViewModel, Service, Worker 모두가 emit 할 수 있다
    

    Args:
        str: 메시지 내용
        str: 로그 레벨 ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
    """
    
    
    # =========================================================================
    # Connection Events (통신 레벨)
    # =========================================================================
    connection_status_changed = pyqtSignal(bool)
    """
    통신 연결 상태 변경 시그널 - 장치 연결/해제

        청취 대상 :
            상단 상태바
            로그창
            연결 관리 화면
            자동실행 스레드
    
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
        여러 UI가 듣고 갱신해야 함 (robot_position_widget 등)
    
    Args:
        RobotState: 로봇 상태 데이터
    
    Example:
        state = RobotState(x=100.0, y=200.0, z=50.0,
                        w=0.0, p=0.0, r=0.0, state='moving')
        EVENT_BUS.robot_position_changed.emit(state)
    """
    
    turntable_state_updated = pyqtSignal(TurntableState)
    """
    턴테이블 상태 변경
    
    Args:
        TurntableState: 턴테이블 상태 데이터
    """
    
    current_state_updated = pyqtSignal(dict)
    """
    현재 시스템 상태 업데이트 시그널 - 로봇 or 장치 종합 상태
    
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
    macro_settings_changed = pyqtSignal(dict)
    """
    매크로 설정 변경

    여러 화면/뷰모델에서 동시에 반응할 수 있는 전역 이벤트

        예:
            매크로 편집 다이얼로그
            타겟 위치 위젯
            사이드바 매크로 리스트
            그 외 다른 모듈들도 구독 가능
    """


    # =========================================================================
    # Data Events (데이터 변경)
    # =========================================================================
    sequence_data_updated = pyqtSignal(dict)
    """
    시퀀스 데이터가 새로 로드되거나 변경되었을 때 발행
    
    구독 대상:
        - TaskManagerViewModel (파일 정보 표시)
        - BatchProcessingViewModel (일괄 처리 준비)
        - ProgressBarViewModel (총 단계 수 계산)

    Args:
        dict: 원본 파일에서 파싱이 끝난 시퀀스 데이터 
        예 :
            {
                '1': {'turntable_feed_rate': 10.0, 'polar_coord_theta': 0.0, ...},
                '2': {'turntable_feed_rate': 10.0, 'polar_coord_theta': 51.42857142857143, ...}
            }
    """


    # =========================================================================
    # Execution Status Events (작업 실행 상태)
    # =========================================================================
    sequence_progress_updated = pyqtSignal(int, int, dict, str)
    """
    시퀀스 진행 상태 변경 알림

    용도:
        - 현재 실행 중인 시퀀스 ID를 UI에 표시
        - 프로그래스 바 갱신 (current / total * 100)
        - 작업 완료/실패 여부 UI 갱신
        - 로봇 애니메이션 갱신 등

    Args:
        int: 시퀀스 ID (또는 현재 순번)
        int: 전체 시퀀스 개수
        dict: 시퀀스 데이터
        str: 상태값 ('processing', 'processed', 'failed', 'unprocessed')

    Example:
        # 3번 시퀀스 실행 시작 (총 10개 중)
        EVENT_BUS.task_status_changed.emit(3, 10, 'processing')
    """        





    # ------------------------------------------------------------------------ #
    # ------------------------------------------------------------------------ #
    # ------------------------------------------------------------------------ #


    # =========================================================================
    # 싱글톤 구현
    # =========================================================================

    _instance: Optional['EventBus'] = None      # 이 클래스의 유일한 인스턴스를 담을 공간
    
    
    def __new__(cls) -> 'EventBus':
        """인스턴스 중복 생성 방지"""

        # 이 클래스의 인스턴스가 있으면 다시 만들지 말고 있는거 다시 써라
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize() # 여기서 딱 1번만 호출함!
        return cls._instance
    
    
    def __init__(self):
        """
        파이썬은 __new__ 로 객체를 생성하면 초기화를 위해 항상 __init__ 을 호출한다
        하지만 실제 초기화는 _initialize에서 끝났으므로
        여기서는 아무것도 하지 않는다

        하는 일도 없는데 지우지 않는 이유:
            이 클래스가 상속받은 부모(QObject)의 __init__ 는 하는일이 많다.
            만약 __init__ 를 아예 안 만들면 파이썬이 자동으로 QObject.__init__ 를 호출한다
            그럼 기존에 연결된 시그널들이 다 끊기고 초기화 된다 -> 망함
            그래서 __init__ 를 만든 뒤 pass 로 아무일도 안 시키는 것 
        """        
        pass
    

    def _initialize(self):
        """초기화 (최초 1회만 실행)"""
        # QObject C++ 초기화는 여기서 딱 한 번 수행
        super().__init__()



    def disconnect_all(self, signal_name: str | None = None):
        """
        EventBus의 모든 시그널 또는 특정 시그널의 연결을 해제
        
        Args:
            signal_name (str, optional): 연결을 해제할 특정 시그널의 이름.
                                        None이면 모든 시그널을 해제
        """
        meta_obj = self.metaObject()
        
        # metaObject()가 None을 반환하는 예외적인 경우를 처리 (Pylance 경고 해결)
        if meta_obj is None:
            return
            
        for i in range(meta_obj.methodCount()):
            method = meta_obj.method(i)
            
            # 시그널인 메서드만 필터링
            if method.methodType() == QMetaMethod.MethodType.Signal:
                current_signal_name = method.name().data().decode('utf-8')
                
                # 특정 시그널만 해제하거나 모든 시그널을 해제
                if signal_name is None or current_signal_name == signal_name:
                    signal_instance = getattr(self, current_signal_name)
                    try:
                        signal_instance.disconnect()
                    except TypeError:
                        # 이미 연결이 없는 시그널에 disconnect()를 호출하면 TypeError 발생
                        pass



# =============================================================================
# 전역 인스턴스
# =============================================================================
EVENT_BUS = EventBus()


