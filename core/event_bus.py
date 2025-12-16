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
# 1. 시그널 그룹 정의 (카테고리별로 분리)
# =============================================================================
class SystemSignals(QObject):
    """
    [시스템 레벨 이벤트 그룹]
    애플리케이션의 생명주기(Lifecycle) 및 전역 상태(Health)와 관련된 시그널 모음입니다.
    """
    
    error = pyqtSignal(str)
    """
    시스템 치명적 오류 발생 (Critical Error)
    
    단순 경고가 아닌, 프로세스 중단이나 사용자의 즉각적인 개입이 필요한 에러입니다.
    이 시그널은 모든 뷰와 서비스가 '비상 정지' 또는 '에러 모드'로 진입하게 합니다.
    
    Args:
        str (message): 에러 상세 내용 (예: "PLC Heartbeat Timeout", "Database Connection Failed")
        
    Subscribers:
        - MainStatusBar: 붉은색 에러 메시지 표시
        - PopupManager: 에러 모달창 팝업
        - LogManager: CRITICAL 레벨로 로그 기록
    """

    info = pyqtSignal(str)
    """
    시스템 일반 알림 (System Notification)
    
    사용자에게 방해되지 않는 수준의 시스템 상태 변화나 완료 메시지를 전달합니다.
    
    Args:
        str (message): 사용자에게 보여줄 메시지 (예: "설정 파일 저장됨", "초기화 완료")
        
    Subscribers:
        - MainStatusBar: 하단 상태바에 3초간 메시지 표시 후 소거
    """

    shutting_down = pyqtSignal()
    """
    애플리케이션 종료 시퀀스 시작 (Graceful Shutdown)
    
    앱이 완전히 꺼지기 직전에 발생합니다. 각 모듈은 이 신호를 받으면 
    즉시 하던 일을 멈추고 안전하게 리소스를 반환해야 합니다.
    
    Trigger:
        - MainWindow의 closeEvent 발생 시
        - 메뉴의 '종료' 버튼 클릭 시
        
    Subscribers (Action):
        - ConnectionService: 소켓 연결 close
        - LogManager: 파일 핸들 flush 및 close
        - WorkerThreads: 실행 중인 스레드 안전 종료 (quit/wait)
    """


class LogSignals(QObject):
    """
    [로깅 이벤트 그룹]
    UI 출력과 파일 기록을 통합 관리하기 위한 채널입니다.
    """
    
    # TODO: 다음 프로젝트에는 ['메시지, 레벨, 로그 발생 장소'] 를 넣을 수 있게 개선하기
    message = pyqtSignal(str, str)
    """
    통합 로그 메시지 발행
    
    UI(LogWidget)와 파일(FileHandler) 양쪽에 로그를 남기기 위한 단일 진입점입니다.
    직접 파일에 쓰지 말고 반드시 이 시그널을 통해야 스레드 안전성이 보장됩니다.
    
    Args:
        str (msg): 로그 내용 본문
        str (level): 로그 레벨 ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
                     * 레벨에 따라 UI에서의 텍스트 색상이 결정됨
    
    Example:
        event_bus.log.message.emit("데이터 파싱 시작", "INFO")
    """


class ConnSignals(QObject):
    """
    [통신 상태 이벤트 그룹]
    PLC, Robot Controller 등 외부 장비와의 연결 상태를 관리합니다.
    """
    
    status_changed = pyqtSignal(bool)
    """
    메인 장비 연결 상태 변경 알림
    
    앱의 조작 가능 여부(Enable/Disable)를 결정하는 가장 중요한 플래그입니다.
    
    Args:
        bool (is_connected): 
            - True: 연결 성공 (조작 가능)
            - False: 연결 끊김 (조작 불가, 재연결 시도 중)
            
    Subscribers:
        - MainToolbar: 연결 아이콘 색상 변경 (Green/Red)
        - ControlPanel: 버튼 활성화/비활성화 처리
    """


class DataSignals(QObject):
    """
    [데이터 및 비즈니스 로직 이벤트 그룹]
    작업 데이터(Sequence)의 로드, 변경 및 실행 진행률을 담당합니다.
    """
    
    sequence_data_loaded = pyqtSignal(list)
    """
    시퀀스 데이터 알림
        모니터링 UI가 현재 작업 목록을 표시할 수 있게 하기 위해
    
    Args:
        list[dict]: 실행될 전체 시퀀스 데이터 리스트
    """

    progress_updated = pyqtSignal(int, int, str)
    """
    작업 실행 진행률 업데이트 (Real-time Progress)
    
    현재 실행 중인 시퀀스 단계와 상태를 UI에 반영합니다.
    
    Args:
        int (current_step): 현재 실행 중인 스텝 번호 (1부터 시작)
        int (total_steps): 전체 스텝 개수 (Progress Bar 계산용)
        str (status): 현재 스텝의 상태 ('PROCESSING', 'DONE', 'FAILED', 'WAITING')
    """


class ControlSignals(QObject):
    """
    [제어 및 모니터링 이벤트 그룹]
    로봇이나 턴테이블의 실시간 위치 정보나 목표값 등 고빈도(약 0.1초마다) 호출 데이터를 처리
    """
    
    robot_current_pose = pyqtSignal(object)
    """
    FANUC 현재 World 좌표 정보
        바닥(베이스 좌표계) 기준 TCP(Tool Center Point) 위치
    
    Args:
        - .x, .y, .z, .w, .p, .r 속성을 가진 FANUCPose 객체
    """

    tool_current_pose = pyqtSignal(object)
    """FANUC 현재 Tool 좌표 정보"""

    turntable_current_pose = pyqtSignal(object)
    """
    턴테이블 현재 각도/속도 정보 (TurntablePose)
    
    Args:
        - .angle (float): 현재 각도
        - .velocity (float): 현재 회전 속도
    """


# =============================================================================
# 2. 실제 QObject
# =============================================================================
class _EventBusBackend(QObject):
    """
    실제 시그널을 정의하는 Qt 객체

    이 클래스는 앱(QApplication)이 준비된 후에 생성된다
    각 기능별 시그널 클래스들을 멤버로 포함하여 계층 구조를 형성
    """

    def __init__(self):
        super().__init__()

        # 각 시그널 그룹을 한 줄로 선언
        self.system = SystemSignals()
        self.log = LogSignals()
        self.conn = ConnSignals()
        self.data = DataSignals()
        self.control = ControlSignals()
        
        # (편의상 그룹 리스트 보관 - disconnect_all 등 관리 목적)
        self._signal_groups = [
            self.system, self.log, self.conn, self.data, self.control
        ]


    def disconnect_all(self, signal_name: str | None = None):
        """
        EventBus의 모든 시그널 또는 특정 시그널의 연결을 해제
        
        Args:
            signal_name (str, optional): 
                연결을 해제할 특정 시그널의 이름
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
                    try:
                        # getattr로 가져올 때 없는 이름이면 AttributeError 발생 가능
                        signal = getattr(self, current_signal_name, None)
                        if signal:
                            signal.disconnect()
                    except (TypeError, RuntimeError):
                        pass    # 연결 없는 경우 or 이미 삭제된 객체에 disconnect()를 호출하면



# =============================================================================
# 3. 공개 EventBus - 다른 파일들은 리팩토링 되어서 싱글톤이 없어진 것을 모르게
# =============================================================================
class EventBus:
    """
    [전역 이벤트 버스 (Global Event Bus) - 외부에서 사용]
    
    애플리케이션 내의 '느슨한 결합(Loose Coupling)'을 위해 존재하는 싱글톤 성격의 통신 허브
    UI(View), 로직(Service/Worker), 데이터(Model/ViewModel) 간의 직접적인 참조를 끊고
    이벤트 기반으로 데이터를 주고받기 위해 사용한다
    QObject를 상속받지 않았기 때문에 Import 시점에 충돌이 절대 발생하지 않는다

    사용 원칙:
        1. Publisher (발행자): 누가 받는지 신경 쓰지 않고 emit 한다
        2. Subscriber (구독자): 누가 보냈는지 신경 쓰지 않고 connect 하여 로직을 수행
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
        사용자가 EVENT_BUS.system.info 를 찾으면 이 함수가 호출됩니다.
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
