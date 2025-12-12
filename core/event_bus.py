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
from typing import Optional, TYPE_CHECKING


# =============================================================================
# 1. 내부 백엔드 (실제 QObject) - 외부에는 숨깁니다.
# =============================================================================
class _EventBusBackend(QObject):
    """
    실제 시그널을 정의하는 Qt 객체입니다.
    이 클래스는 앱(QApplication)이 준비된 후에 생성됩니다.
    """
    
    # --- System Events ---
    system_error = pyqtSignal(str)
    system_info = pyqtSignal(str)
    app_shutting_down = pyqtSignal()

    # --- Log Events ---
    ui_log_message = pyqtSignal(str, str)

    # --- Connection Events ---
    connection_status_changed = pyqtSignal(bool)

    # --- Data Events ---
    sequence_data_updated = pyqtSignal(dict)
    sequence_progress_updated = pyqtSignal(int, int, str)

    # --- Robot/Turntable Events ---
    robot_target_updated = pyqtSignal(object)
    turntable_target_updated = pyqtSignal(object)

    def __init__(self):
        super().__init__()

    def disconnect_all(self, signal_name: str | None = None):
        meta_obj = self.metaObject()
        if meta_obj is None: return
        for i in range(meta_obj.methodCount()):
            method = meta_obj.method(i)
            if method.methodType() == QMetaMethod.MethodType.Signal:
                current_signal_name = method.name().data().decode('utf-8')
                if signal_name is None or current_signal_name == signal_name:
                    try: getattr(self, current_signal_name).disconnect()
                    except TypeError: pass




# =============================================================================
# 2. 공개 EventBus (안전한 껍데기)
# =============================================================================
class EventBus:
    """
    외부에서 사용하는 EventBus 클래스입니다.
    QObject를 상속받지 않았기 때문에 Import 시점에 충돌이 절대 발생하지 않습니다.
    """
    
    def __init__(self):
        # 내부적으로 진짜 QObject를 담을 변수 (초기엔 None)
        self._backend: Optional[_EventBusBackend] = None

    @property
    def _qobject(self) -> _EventBusBackend:
        """
        진짜 객체가 필요할 때(사용 시점) 생성하는 '게으른 로더'입니다.
        """
        if self._backend is None:
            # 이 코드가 실행될 때는 이미 main.py에서 AppEngine이 생성된 후입니다.
            self._backend = _EventBusBackend()
        return self._backend

    def __getattr__(self, name):
        """
        사용자가 EVENT_BUS.system_info 를 찾으면 이 함수가 호출됩니다.
        내부 백엔드(_EventBusBackend)에게 그 요청을 토스합니다.
        """
        return getattr(self._qobject, name)

    # (편의 기능) disconnect_all 같은 메서드도 백엔드로 연결
    def disconnect_all(self, signal_name: str | None = None):
        self._qobject.disconnect_all(signal_name)

# =============================================================================
# 전역 인스턴스
# =============================================================================
# IDE(VS Code)에게는 "이거 _EventBusBackend 야"라고 거짓말을 해서 자동완성을 돕습니다.
if TYPE_CHECKING:
    EVENT_BUS = _EventBusBackend()
else:
    # 실제 런타임에는 안전한 껍데기(EventBus)가 나갑니다.
    EVENT_BUS = EventBus()









class OLDEventBus(QObject):
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
    sequence_progress_updated = pyqtSignal(int, int, str)
    """
    시퀀스 진행 상태 변경 알림

    용도:
        - 현재 실행 중인 시퀀스 ID를 UI에 표시
        - 프로그래스 바 갱신 (current / total * 100)
        - 작업 완료/실패 여부 UI 갱신

    Args:
        int: 시퀀스 ID (또는 현재 순번)
        int: 전체 시퀀스 개수
        str: 상태값 ('processing', 'processed', 'failed', 'unprocessed')

    Example:
        # 3번 시퀀스 실행 시작 (총 10개 중)
        EVENT_BUS.sequence_progress_updated.emit(3, 10, 'processing')
    """        


    # =========================================================================
    # 기기들의 위치 정보
    # =========================================================================
    robot_target_updated = pyqtSignal(object)
    """
    로봇 위치 정보
        Args: FANUCPose 객체
    """

    turntable_target_updated = pyqtSignal(object)
    """
    턴테이블 목표 위치 업데이트 (UI: 턴테이블 패널용)
        Args: TurntablePose 객체
    """



    # ------------------------------------------------------------------------ #
    # ------------------------------------------------------------------------ #
    # ------------------------------------------------------------------------ #



    def __init__(self):
        super().__init__()

        # 안전장치: 이미 만들어진 적이 있다면 에러 발생
        if EventBus._is_created:
            raise RuntimeError("EventBus는 이미 생성되었습니다! 전역 변수 EVENT_BUS를 사용하세요.")
            
        EventBus._is_created = True



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


