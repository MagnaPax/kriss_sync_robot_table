# models/sequence_model.py
"""
View  ←→  ViewModel  →  Model

시퀀스 도메인 모델 (순수 비즈니스 로직)

책임:
    - 시퀀스 데이터 구조 정의
    - 시퀀스 파싱 로직
    - 실행 상태 관리
    - 유효성 검증

Thread-Safety:
    - 모든 공유 상태 접근은 Lock으로 보호
    - 속성 읽기도 Lock 획득 (일관성 보장)
"""

from typing import List, Optional, Dict, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum, auto
import threading


# =============================================================================
# 예외 정의
# =============================================================================
class SequenceError(Exception):
    """이 모듈 전용의 기본 예외 타입"""
    pass


class SequenceParseError(SequenceError):
    """
    파싱 과정에서 발생한 오류를 나타내는 예외
    
    SequenceError 를 상속하기 때문에 더 일반적인 핸들링도 가능
    """
    def __init__(self, message: str, line_number: int = 0):
        """
        Args:
            message: 오류 메시지
            line_number: 오류가 발생한 라인 번호
        """
        super().__init__(message)
        self.line_number = line_number


# =============================================================================
# 상태 정의
# =============================================================================
class SequenceState(Enum):
    """시퀀스 실행 상태"""
    IDLE = auto()
    RUNNING = auto()
    PAUSED = auto()
    COMPLETED = auto()
    ERROR = auto()


# =============================================================================
# 데이터 모델
# =============================================================================
# frozen=True -> 불변. 동일 단계를 여러 곳에서 참조하거나 캐시할 때 안전 보장
@dataclass(frozen=True)
class SequenceStep:
    """
    개별 시퀀스 단계 
    
    frozen=True -> 불변
    
    Attributes:
        command: 명령어 (예: MOVE, ROTATE, WAIT, MEASURE)
        params: 숫자 파라미터들의 리스트
        line_number: 원본 텍스트 파일에서의 줄 번호 (디버깅/에러 메세지에 사용)
    """
    command: str
    # default_factory=list -> 모든 인스턴스가 같은 리스트 객체 공유하지 않도록
    params: List[float] = field(default_factory=list)
    line_number: int = 0

    def __post_init__(self):
        if not self.command:
            raise SequenceError(f"명령어가 비어있습니다 (Line {self.line_number})")


# =============================================================================
# 순수 도메인 모델
# =============================================================================
class SequenceModel:
    """
    시퀀스 도메인 모델 (순수 비즈니스 로직)

    시퀀스 전체(여러 SequenceStep)를 관리하고 실행 흐름을 제어한다
    
    Thread-Safe:
        - 모든 공유 상태 접근은 Lock으로 보호
        - 다중 스레드 환경에서 안전하게 사용 가능
    
    사용 예: (파싱→실행→제어)
        # 파싱
        model = SequenceModel()
        model.parse_from_text(text_content)
        
        # 실행
        model.start()
        while model.is_running:
            step = model.next_step()
            if step:
                execute_command(step)
        
        # 일시정지/재개
        model.pause()
        model.resume()
        
        # 강제 재시작
        model.restart()
    """
    
    def __init__(self):
        """초기화 (의존성 없음)"""
        # 로드된 단계 리스트(내부 저장용). 외부에서는 .steps 프로퍼티로 복사본만 제공
        self._steps: List[SequenceStep] = []
        # 다음에 실행할 단계의 인덱스(0-based). 0이면 아직 시작 전
        self._current_index: int = 0
        # 초기 상태를 IDLE로 설정
        self._state: SequenceState = SequenceState.IDLE
        # 모델의 공유 상태(steps, index, state)에 대한 동시 접근을 보호
        self._lock = threading.Lock()

    # =========================================================================
    # 속성 (읽기 전용, Thread-Safe)
    # =========================================================================
    
    @property   # 객체 필드 접근을 돕는 데코레이터
    def steps(self) -> List[SequenceStep]:
        """로드된 시퀀스 단계 (읽기 전용)"""
        # 읽는 도중에도 lock 사용
        with self._lock:
            # 외부에서 내부의 리스트를 변경하지 못하게 사본을 반환
            return self._steps.copy()
    
    @property
    def current_index(self) -> int:
        """현재 실행 중인(다음 실행할) 인덱스 반환"""
        with self._lock:
            return self._current_index
    
    @property
    def state(self) -> SequenceState:
        """현재 실행 상태 반환"""
        with self._lock:
            return self._state
    
    @property
    def is_running(self) -> bool:
        """
        실행 중인지 여부 반환 -> UI 및 로직이 빠르게 체크할 때 유용
        """
        with self._lock:
            return self._state == SequenceState.RUNNING
    
    @property
    def is_paused(self) -> bool:
        """일시정지 여부"""
        with self._lock:
            return self._state == SequenceState.PAUSED
    
    @property
    def is_completed(self) -> bool:
        """완료 여부"""
        with self._lock:
            return self._state == SequenceState.COMPLETED
    
    @property
    def progress(self) -> float:
        """
        진행률 (0.0 ~ 1.0)
        
        Note:
            - current_index는 '다음 실행할 단계'를 가리킴
            - 즉, 0이면 아직 시작 안 함, len(steps)이면 모두 완료
        """
        with self._lock:
            if not self._steps:
                return 0.0
            # `current_index / len(steps)` 이므로 0 -> 0%, len(steps) -> 100%
            # min(max()) 이상한 값(음수)이 되지 않도록
            return min(max(self._current_index / len(self._steps), 0.0), 1.0)
    
    @property
    def total_steps(self) -> int:
        """전체 단계 수"""
        with self._lock:
            return len(self._steps)

    # =========================================================================
    # 파싱 (순수 로직, Thread-Safe)
    # =========================================================================
    
    def parse_from_text(self, text: str) -> None:
        """
        텍스트를 파싱하여 시퀀스 로드

        문법적 파싱만 수행. 의미적 검증(예: 좌표 범위, 파라미터 의미)은 validate()에서 처리
        
        Args:
            text: 시퀀스 텍스트
            
        Raises:
            SequenceParseError: 파싱 실패 시 (라인 번호 포함)
            
        Note:
            - 성공 시 상태를 IDLE로 리셋
            - Thread-Safe: 파싱 완료 후 원자적으로 교체
        """

        # 빈 문자열이나 공백만 온 경우 즉시 SequenceParseError를 던져 '호출자'에게 알림
        # 이 클래스에는 순수 로직만 들어가므로 자체적으로 로그 남기는 작업을 하지 않는다
        if not text or not text.strip():
            raise SequenceParseError("텍스트가 비어있습니다")
        
        # 긴 파싱 작업은 Lock을 걸지 않고 수행(성능 때문에)
        steps: List[SequenceStep] = []
        
        # enumerate(..., 1) -> 1-based 라인 번호 제공
        # text.strip().split('\n') -> 줄 단위 반복
        for line_num, line in enumerate(text.strip().split('\n'), 1):
            line = line.strip()
            
            # 빈 줄이나 주석 나오면 건너뛴다
            if not line or line.startswith('#'):
                continue
            
            try:
                # 각 라인을 _parse_line 로 파싱
                step = self._parse_line(line, line_num)
                if step:
                    steps.append(step)

            # 예외가 발생하면 그냥 호출자에게 던진다
            # 발생하는 모든 예외는 결국 이 Model의 ViewModel인 SequenceViewModel 이 받아서 처리한다
            # _parse_line 이 SequenceParseError를 던지면 그대로 전파(호출자에게 라인 번호와 메시지 전달)
            except SequenceParseError:
                raise
            # 그 외 예기치 못한 예외는 SequenceParseError로 래핑하여 발생한 라인 번호를 담아 재발생 시킨다
            except Exception as e:
                raise SequenceParseError(
                    f"파싱 실패: {str(e)}",
                    line_number=line_num
                ) from e
            
        # 주석/빈 줄만 있어 실제 단계가 하나도 없으면 에러를 던진다
        if not steps:
            raise SequenceParseError("유효한 시퀀스 단계가 없습니다")
        
        # Lock 을 걸고 새로운 값으로 원자적(Atomic) 교체
        # 즉, 전부 실행되거나 아예 실행 안 되거나 해서 중간에 바뀌다 만 뒤죽박죽 상태를 만들지 않는다
        with self._lock:
            self._steps = steps
            self._current_index = 0
            self._state = SequenceState.IDLE
    
    def _parse_line(self, line: str, line_num: int) -> Optional[SequenceStep]:
        """
        한 줄 파싱
        
        Returns:
            SequenceStep 또는 None (빈 줄)
            
        Raises:
            SequenceParseError: 파싱 오류
        """
        parts = line.split()    # 공백 기준으로 분할
        if not parts:
            # 비어있으면 None 반환(호출부에서 빈 줄을 건너뛰지만 안전하게 한번 더 거름)
            return None
        
        # 첫 번째 토큰을 명령어로 보고 대문자로 변환하여 통일한다(대소문자 혼용 방지)
        command = parts[0].upper()
        
        # 파라미터
        # 나머지 토큰들을 float로 변환해 params에 저장
        params: List[float] = []

        # enumerate(parts[1:], 1)로 파라미터 순번(1-based)을 추적해, 변환 실패 시 어느 파라미터가 문제인지 명확히 알린다
        for i, param_str in enumerate(parts[1:], 1):
            try:
                params.append(float(param_str))

            # 숫자 형식이 아닌 값이 들어오면 SequenceParseError를 던진다
            except ValueError:
                raise SequenceParseError(
                    f"잘못된 파라미터 #{i} '{param_str}' (숫자 형식 필요)",
                    line_number=line_num
                )
        
        # 정상적으로 파싱되면 SequenceStep 인스턴스를 만들어 반환
        return SequenceStep(
            command=command,
            params=params,
            line_number=line_num
        )

    # =========================================================================
    # 실행 제어 (명확한 API - start()는 시작 전용, restart()는 강제 재시작, Thread-Safe)
    # 
    # 시퀀스의 실행 흐름을 제어하는 메서드 모음
    # 모두 Lock을 걸어서 스레드 안전(Thread-Safe)하게 실행
    # =========================================================================
    
    def start(self) -> bool:
        """
        시퀀스 실행 시작(초기 시작 용)
        
        Returns:
            성공 여부
            
        Note:
            - IDLE 또는 COMPLETED 상태에서만 시작 가능
            - PAUSED 상태는 resume() 사용
            - RUNNING 상태는 restart() 사용
        """
        with self._lock:
            # _steps가 비어있으면 시작할 수 없으므로 False 반환
            if not self._steps:
                return False
            
            # 명확한 전제 조건
            # 현재 상태가 IDLE 또는 COMPLETED인 경우에만 동작(== PAUSED 혹은 RUNNING 은 실패)
            if self._state not in (SequenceState.IDLE, SequenceState.COMPLETED):
                return False
            
            # 성공하면 상태를 RUNNING으로 바꾸고 인덱스를 0으로 초기화
            self._state = SequenceState.RUNNING
            self._current_index = 0
            return True
    
    def restart(self) -> bool:
        """
        어떤 상태이든지 강제로 처음부터 재시작 (RUNNING 중에도 재시작 가능)
        
        Returns:
            성공 여부
            
        Note:
            - 현재 상태와 무관하게 처음부터 다시 시작
            - RUNNING 중에도 호출 가능
        """
        with self._lock:
            if not self._steps:
                return False
            
            self._state = SequenceState.RUNNING
            self._current_index = 0
            return True
    
    def next_step(self) -> Optional[SequenceStep]:
        """
        다음 단계 반환 및 인덱스 증가
        
        Returns:
            SequenceStep 또는 None (완료/중단 시)
            
        Note:
            - RUNNING 상태에서만 동작
            - 마지막 단계 후 자동으로 COMPLETED 전환
        """
        with self._lock:
            # 현재 상태가 RUNNING이 아니면 None 반환(실행 불가)
            if self._state != SequenceState.RUNNING:
                return None
            
            # 인덱스가 범위 밖(>= len)이라면 COMPLETED로 전환 후 None 반환
            if self._current_index >= len(self._steps):
                self._state = SequenceState.COMPLETED
                return None
            
            # step 을 리턴 하기 전에 인덱스를 증가시켜 다음 호출에 이어지도록
            step = self._steps[self._current_index]
            self._current_index += 1
            
            # 마지막 단계 실행 후 자동 완료(COMPLETED 상태로 전환)
            if self._current_index >= len(self._steps):
                self._state = SequenceState.COMPLETED
            
            return step
    
    def pause(self) -> bool:
        """
        실행 일시정지
        
        Returns:
            성공 여부 (RUNNING → PAUSED)
        """
        with self._lock:

            # 실행 중일 때만 동작
            if self._state != SequenceState.RUNNING:
                return False
            
            # 상태를 PAUSED 로 전환
            self._state = SequenceState.PAUSED
            return True
    
    def resume(self) -> bool:
        """
        실행 재개
        
        Returns:
            성공 여부 (PAUSED → RUNNING)
        """
        with self._lock:

            # PAUSED 상태에서만 동작
            if self._state != SequenceState.PAUSED:
                return False
            
            # 상태를 RUNNING 로 전환
            self._state = SequenceState.RUNNING
            return True
    
    def stop(self) -> None:
        """
        실행 중단 및 상태 초기화
        
        Note:
            - 상태를 IDLE로 리셋
            - 인덱스를 0으로 리셋
            - 이미 IDLE/COMPLETED 상태면 아무 동작 안 함
        """
        with self._lock:
            if self._state not in (SequenceState.IDLE, SequenceState.COMPLETED):
                self._state = SequenceState.IDLE
                self._current_index = 0

    # =========================================================================
    # 유틸리티 메서드(Thread-Safe)
    # =========================================================================
    
    def get_remaining_steps(self) -> List[SequenceStep]:
        """
        현재 진행 중(RUNNING) 또는 일시정지(PAUSED) 상태일 때 남은 단계를 잘라서 반환
        
        Returns:
            남은 SequenceStep 리스트
            
        Note:
            - RUNNING 또는 PAUSED 상태에서만 유효
            - 다른 상태에서는 빈 리스트 반환
        """
        with self._lock:

            # 진행 중(RUNNING) 또는 일시정지(PAUSED) 상태가 아닌
            # 다른 상태(IDLE, COMPLETED)에서는 빈 리스트 반환
            if self._state not in (SequenceState.RUNNING, SequenceState.PAUSED):
                return []
            # 사본을 리턴(외부에서 변경 차단)
            return self._steps[self._current_index:].copy()
    
    def get_step_at(self, index: int) -> Optional[SequenceStep]:
        """
        특정 인덱스의 단계 반환 - 인덱스 범위를 벗어나면 None
        
        Args:
            index: 조회할 인덱스
            
        Returns:
            SequenceStep 또는 None (범위 초과 시)
        """
        with self._lock:
            if 0 <= index < len(self._steps):
                return self._steps[index]
            return None
    
    def validate(
        self,
        valid_commands: Optional[set] = None,
        param_constraints: Optional[Dict[str, Union[int, Tuple[int, int]]]] = None
    ) -> List[str]:
        """
        시퀀스 의미적 검증(예: 좌표 범위, 파라미터 의미)

        사전적 검사(명령어 유효성, 파라미터 개수 제약)를 수행하고 경고 메시지 리스트를 반환
        
        Args:
            valid_commands: 유효한 명령어 집합 - 없으면(None) 검사 안 함)
            param_constraints: 명령어별 파라미터 개수 제약을 지정한다. 예:
                {
                    'MOVE': 3,           # 정확히 3개
                    'ROTATE': (1, 1),    # 최소1, 최대1
                    'MEASURE': (0, 2),   # 0~2개 허용
                }
        
        Returns:
            검증 결과가 빈 리스트면 문제 없음으로, 만약 비어있지 않으면 경고 메시지가 포함
        """
        warnings: List[str] = []
        
        with self._lock:
            if not self._steps:
                warnings.append("시퀀스가 비어있습니다")
                return warnings
            
            steps_copy = self._steps.copy()
        
        # 시간이 오래 걸릴 수 있는 검증 작업은 Lock 밖에서 수행
        if valid_commands:
            for step in steps_copy:
                if step.command not in valid_commands:
                    warnings.append(
                        f"Line {step.line_number}: "
                        f"알 수 없는 명령어 '{step.command}'"
                    )
        
        if param_constraints:
            for step in steps_copy:
                if step.command in param_constraints:
                    constraint = param_constraints[step.command]
                    actual = len(step.params)
                    
                    if isinstance(constraint, int):
                        # 정확한 개수
                        if actual != constraint:
                            warnings.append(
                                f"Line {step.line_number}: "
                                f"'{step.command}' 파라미터 개수 불일치 "
                                f"(기대: {constraint}, 실제: {actual})"
                            )
                    else:
                        # 범위 (min, max)
                        min_c, max_c = constraint
                        if not (min_c <= actual <= max_c):
                            warnings.append(
                                f"Line {step.line_number}: "
                                f"'{step.command}' 파라미터 개수 범위 위반 "
                                f"(기대: {min_c}~{max_c}, 실제: {actual})"
                            )
        
        return warnings
    
    def __repr__(self) -> str:
        """객체의 문자열 표현을 반환(디버깅/로깅 시 유용)"""
        with self._lock:
            return (
                f"SequenceModel("
                f"steps={len(self._steps)}, "
                f"state={self._state.name}, "
                f"index={self._current_index})"
            )





# ==========================================================
# 단독 실행 (테스트용)
"""
실행 명령어
python -m models.sequence_model
"""
# ==========================================================
if __name__ == "__main__":
    """
    샘플 시퀀스 문자열을 파싱해서 로드하는 테스트 코드

    두 개의 스레드를 만들어서:

        하나는 executor()로 start()→next_step() 루프 실행(실제 단계마다 time.sleep으로 시뮬레이션)
        다른 하나는 monitor()로 주기적으로 state, progress, get_remaining_steps를 읽어 출력

    스레드 동작으로 인해 Lock이 있어도 데이터가 깨지지 않는지 검증

    마지막으로 API 동작( start(), pause(), resume(), restart() )의 정확성 테스트(간단한 assert)를 수행
    """

    import time
    from threading import Thread
    
    print("=" * 70)
    print("SequenceModel Thread-Safety 테스트")
    print("=" * 70)
    
    model = SequenceModel()
    
    # 샘플 시퀀스
    sample = """
    # 샘플 시퀀스
    MOVE 100.0 200.0 50.0
    ROTATE 90.0
    WAIT 1.5
    MEASURE
    """
    
    try:
        model.parse_from_text(sample)
        print(f"✅ 파싱 성공: {model.total_steps}단계\n")
    except SequenceParseError as e:
        print(f"❌ 파싱 실패: {e}")
        exit(1)
    
    # Thread 1: 실행
    def executor():
        print(f"[Executor] 시작")
        model.start()
        
        while model.is_running:
            step = model.next_step()
            if step:
                print(f"[Executor] {step.command} {step.params}")
                time.sleep(0.1)
        
        print(f"[Executor] 완료 (진행률: {model.progress:.0%})")
    
    # Thread 2: 상태 모니터링
    def monitor():
        print(f"[Monitor] 시작")
        time.sleep(0.05)  # Executor가 먼저 시작하도록
        
        for _ in range(5):
            state = model.state
            progress = model.progress
            remaining = len(model.get_remaining_steps())
            print(f"[Monitor] State={state.name}, Progress={progress:.0%}, Remaining={remaining}")
            time.sleep(0.15)
    
    t1 = Thread(target=executor, daemon=True)
    t2 = Thread(target=monitor, daemon=True)
    
    t1.start()
    t2.start()
    
    t1.join()
    t2.join()
    
    print("\n" + "=" * 70)
    print("API 명확성 테스트")
    print("=" * 70)
    
    model2 = SequenceModel()
    model2.parse_from_text("MOVE 1 2 3")
    
    print(f"초기 상태: {model2.state.name}")
    
    print(f"\nstart() 호출...")
    assert model2.start() == True
    print(f"→ {model2.state.name}")
    
    print(f"\npause() 호출...")
    assert model2.pause() == True
    print(f"→ {model2.state.name}")
    
    print(f"\nPAUSED 상태에서 start() 호출...")
    assert model2.start() == False  # ← 실패 (resume 사용해야 함)
    print(f"→ {model2.state.name} (변화 없음)")
    
    print(f"\nresume() 호출...")
    assert model2.resume() == True
    print(f"→ {model2.state.name}")
    
    print(f"\nrestart() 호출...")
    assert model2.restart() == True
    print(f"→ {model2.state.name}, index={model2.current_index}")
    
    print("\n✅ 모든 테스트 통과!")