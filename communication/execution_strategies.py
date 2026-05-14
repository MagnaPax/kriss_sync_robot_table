# communication/execution_strategies.py
"""
Execution Strategies (전략 구현부)

이 모듈은 기기 제어의 구체적인 실행 로직(The "How")을 담고 있는 전략 클래스들의 집합이다.
`TwinCATCommander`에 의해 선택되어 실제로 장비를 움직이는 역할을 한다.

[포함된 실행 전략]
1. IntegratedExecutor (통합 제어):
    - 로봇과 턴테이블을 정교하게 동기화하여 패킷 단위로 제어한다.
    - CSV 데이터를 기반으로 로봇의 이동 속도와 턴테이블의 회전을 조율한다.

2. FanucOnlyExecutor (로봇 단독):
    - 서보 모터 없이 로봇 팔만 단독으로 제어한다.
    - Packet-Based SSOT 방식을 사용하여 안정적인 신호 교환을 보장한다.

3. ServoOnlyExecutor (서보 단독):
    - 로봇 없이 턴테이블 및 툴 모터(공전/자전)를 테스트하거나 제어한다.

4. LegacyIntegratedExecutor:
    - 구형 텍스트 포맷 등을 지원하기 위한 호환성 전략이다.

[구조]
- `BaseExecutor`: 모든 전략이 상속받아야 할 공통 인터페이스 (추상 클래스)
"""
import time
import threading
from PyQt6.QtCore import QThread
from abc import ABC, abstractmethod
from typing import List, Any, Optional, Dict

from core.event_bus import EVENT_BUS
from communication.fanuc_adapter import FanucAdapter
from communication.servo_adapter import ServoAdapter
from models.fanuc_pose_model import FANUCPoseModel
from models.servo_pose_model import ServoPoseModel
from config.data_formats import (
    TaskStatus, SERVO_KEYS, ROBOT_KEYS,
    KEY_ROBOT_X, KEY_TURNTABLE_DEG, KEY_TURNTABLE_FEED_RATE,
    KEY_TOOL_REV_RPM, KEY_TOOL_ROT_RPM
)
from models.servo_pose_key import ServoAxis
from models.fanuc_pose_key import FanucSignal
from core.settings import SETTINGS



# =========================================================
# 1. 추상 실행기 (Base Executor)
# =========================================================
class BaseExecutor(ABC):
    def __init__(self, robot: FanucAdapter, servo: ServoAdapter):
        self.robot = robot
        self.servo = servo
        self._log_prefix = f"[{self.__class__.__name__}]"

    @abstractmethod
    def can_execute(self, sample_data: Dict[str, Any]) -> bool:
        """이 데이터 형식을 처리할 수 있는지 확인"""
        pass

    @abstractmethod
    def execute(self, sequence_data: List[Dict[str, Any]]) -> tuple[bool, str]:
        """실제 실행 로직"""
        pass

    def _is_interrupted(self) -> bool:
        """현재 스레드에 중단 요청이 있는지 확인"""
        return bool((thread := QThread.currentThread()) and thread.isInterruptionRequested())

    def _wait_event_with_safety(self, event: threading.Event, timeout: float) -> bool:
        """
        [안전 대기] 이벤트를 기다리면서 중단 요청도 함께 감시한다.
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self._is_interrupted():
                return False
            if event.wait(0.1): # 0.1초 단위로 폴링하며 확인
                return True
        return False


# =========================================================
# 2. 전략 구현 (Strategies)
# =========================================================
class FanucOnlyExecutor(BaseExecutor):
    """
    [로봇 단독 실행 전략]
    서보 모터 없이 'FANUC 로봇 팔'만 혼자서 움직이는 모드이다.
    복잡한 턴테이블 동기화 없이 로봇만 테스트할 때 사용한다.
    
    [핵심 기술: Packet-Only SSOT]
    - 예전처럼 신호를 하나하나 껐다 켰다(Bit-banging) 하지 않는다.
    - "이번엔 여기로 가고 신호는 이렇게 해!" 하고 24바이트짜리 편지(Packet) 한 통을 딱 보내면 끝이다.
    """

    def __init__(self, robot: FanucAdapter, servo: ServoAdapter):
        super().__init__(robot, servo)
        # 설정 파일에서 타임아웃 시간을 가져온다 (없으면 기본 60초)
        self.move_timeout = getattr(SETTINGS.servo, "move_timeout", 60.0)

    def can_execute(self, sample_data: Dict[str, Any]) -> bool:
        """
        이 데이터가 로봇 단독 모드용인지 검사한다.
        - 로봇 좌표(X, Y, Z...)는 있는데
        - 서보 데이터(회전, 공전...)는 하나도 없으면
        - "아, 이건 로봇 혼자 하는거구나" 하고 True를 반환한다.
        """
        data_keys = set(sample_data.keys())
        has_robot = not ROBOT_KEYS.isdisjoint(data_keys)
        has_servo = not SERVO_KEYS.isdisjoint(data_keys)
        # 로봇 키는 있고, 서보 키는 없을 때 합격!
        return has_robot and not has_servo

    def execute(self, sequence_data: List[Dict[str, Any]]) -> tuple[bool, str]:
        EVENT_BUS.log.message.emit(f"{self._log_prefix} 로봇 단독 모드 시작 (데이터 {len(sequence_data)}건)", "INFO")

        robot = self.robot

        # 로봇 상태 확인
        try:
            robot.validate_robot_ready()
        except Exception as e:
            return False, f"{self._log_prefix} 로봇이 준비되지 않았습니다: {e}"

        # 목적지 데이터 전송(앱->PLC)
        try:
            robot.send_target_data_to_plc_buffer(sequence_data, FanucSignal.FR_BUFFER_FOR_MANUAL_MOVE.path)
        except InterruptedError:
            return False, f"{self._log_prefix} 사용자 요청에 의한 작업 중단."
        except Exception as e:
            return False, f"{self._log_prefix} 실행 중 오류: {e}"
        else:
            EVENT_BUS.log.message.emit(f"{self._log_prefix} 로봇 목적지 전송 완료", "INFO")

        # 로봇 실행 신호 전송
        try:
            if self._is_interrupted():
                return False, f"{self._log_prefix} 사용자에 의한 작업 중단"

            wait_time_to_change_signal: float = 1.0
            rsr_signal: str = FanucSignal.RSR2.path
            robot.trigger_move_signal(rsr_signal, wait_time_to_change_signal)
        except Exception as e:
            return False, f"{self._log_prefix} 실행 중 오류: {e}"
        else:
            return True, f"{self._log_prefix} 로봇 trigger 신호 전송 완료"



class ServoOnlyExecutor(BaseExecutor):
    """
    [서보 모터 단독 실행 전략]
    로봇 팔은 가만히 두고 'Panasonic 서보 모터(턴테이블, 드릴)'만 제어하는 모드이다.
    주로 서보 모터가 잘 도는지 테스트하거나 캘리브레이션할 때 사용한다.
    """

    def __init__(self, robot: FanucAdapter, servo: ServoAdapter):
        super().__init__(robot, servo)
        
        # 설정 파일에서 얼마나 기다려줄지 값을 가져온다.
        self.busy_timeout = SETTINGS.servo.busy_timeout
        self.move_timeout = SETTINGS.servo.move_timeout

    def can_execute(self, sample_data: Dict[str, Any]) -> bool:
        """
        이 데이터가 서보 단독 모드용인지 검사한다.
        - 서보 데이터(회전, 공전...)는 있는데
        - 로봇 키(X, Y, Z...)가 하나도 없으면
        - "옳거니, 이건 서보만 돌리는거구나" 하고 True를 반환한다.
        """
        data_keys = set(sample_data.keys())
        has_robot = not ROBOT_KEYS.isdisjoint(data_keys)
        has_servo = not SERVO_KEYS.isdisjoint(data_keys)
        # 서보 키는 있고, 로봇 키는 없을 때 합격!
        return has_servo and not has_robot

    def execute(self, sequence_data: List[Dict[str, Any]]) -> tuple[bool, str]:
        """
        [실행 메인 함수]
        서보 모터 전용 데이터를 순서대로 하나씩 실행한다.
        Returns: (성공여부, 결과메시지)
        """
        EVENT_BUS.log.message.emit(f"{self._log_prefix} 서보 단독 제어 시작 (데이터 {len(sequence_data)}건)", "INFO")
        EVENT_BUS.log.message.emit(f"{self._log_prefix} 에서 처리될 전체 데이터\n{(sequence_data)}\n", "DEBUG")

        adapter = self.servo

        try:
            # 한 번의 턴테이블 동작만 수행하기 때문에 sequence_data[0]만 보낸다
            adapter.send_tt_target_data(sequence_data[0])
        except InterruptedError:
            return False, f"{self._log_prefix} TT 데이터 전송 중 작업 중단됨."
        except Exception as e:
            return False, f"{self._log_prefix} TT 데이터 전송 중 오류: {e}"
        else:
            EVENT_BUS.log.message.emit(f"{self._log_prefix} 턴테이블 이동 목표 데이터 전송 완료", "INFO")

        try:
            if self._is_interrupted():
                return False, f"{self._log_prefix} 사용자에 의한 작업 중단"

            adapter.trigger_tt_manual_move()
        except InterruptedError:
            return False, f"{self._log_prefix} TT trigger 신호 전송 중 작업 중단됨."
        except Exception as e:
            return False, f"{self._log_prefix} TT trigger 신호 전송 중 오류: {e}"
        else:
            return True, f"{self._log_prefix} 사용자가 입력한 턴테이블 trigger 신호 전송 완료"

    def _is_interrupted(self) -> bool:
        """누가 "그만해!"(정지) 라고 했는지 확인함."""
        return bool((thread := QThread.currentThread()) and thread.isInterruptionRequested())



class IntegratedExecutor(BaseExecutor):
    """
    [통합 실행 전략]
    로봇 팔(FANUC)과 턴테이블(Panasonic)을 정교하게 동기화해서 움직이는 클래스이다.
    CSV 파일에 적힌 대로 '로봇이 움직이는 동안 턴테이블도 같이 돈다'는 것이 핵심이다.
    """

    def __init__(self, robot: FanucAdapter, servo: ServoAdapter):
        super().__init__(robot, servo)
        
        # 서보 모터가 다 움직일 때까지 기다려줄 최대 시간 (설정값)
        self.busy_timeout = SETTINGS.servo.busy_timeout
        self.move_timeout = SETTINGS.servo.move_timeout

    def can_execute(self, sample_data: Dict[str, Any]) -> bool:
        """
        이 실행기가 처리할 수 있는 데이터인지 확인한다.
        - 로봇 데이터(X, Y, Z...)도 있고
        - 서보 데이터(회전 속도 등)도 있고
        - 특히 '턴테이블 각도'나 '로봇 X좌표'가 있으면 "아, 이건 내가 처리해야겠구나" 하고 True를 반환한다.
        """
        data_keys = set(sample_data.keys())
        has_robot = not ROBOT_KEYS.isdisjoint(data_keys)
        has_servo = not SERVO_KEYS.isdisjoint(data_keys)
        has_specific_key = (KEY_TURNTABLE_DEG in data_keys) or (KEY_ROBOT_X in data_keys)
        return has_robot and has_servo and has_specific_key

    def execute(self, sequence_data: List[Dict[str, Any]]) -> tuple[bool, str]:
        """
        [메인 실행 로직]
        로봇과 서보를 지휘하는 통합 실행부.
        """
        EVENT_BUS.log.message.emit(f"{self._log_prefix} CSV 통합 동기화 제어 시작 (데이터 {len(sequence_data)}건)", "INFO")
        EVENT_BUS.data.sequence_data_loaded.emit(sequence_data)

        robot = self.robot
        servo = self.servo

        total_count = len(sequence_data)
        if total_count == 0:
            return True, f"{self._log_prefix} 실행할 데이터가 없습니다."

        try:
            import threading
            import concurrent.futures

            # 동기화를 위한 이벤트 객체들
            robot_ready_event = threading.Event()
            servo_ready_event = threading.Event()
            start_event = threading.Event()

            def robot_task():
                EVENT_BUS.log.message.emit(f"{self._log_prefix} [Robot] 스레드 시작", "DEBUG")
                total_data = FANUCPoseModel.FR_pre_calculate_all(sequence_data)
                EVENT_BUS.log.message.emit(f"{self._log_prefix} [Robot] 데이터 가공 완료: 총 {len(total_data)}행", "DEBUG")
                
                # 1. 초기 버퍼 (PRLINE 0, Chunk 1, Chunk 2) 전송
                robot.FR_send_to_plc_first(robot.FR_prepare_single_buffers(total_data))
                EVENT_BUS.log.message.emit(f"{self._log_prefix} [Robot] 단일 버퍼 (PRLINE 0) 전송 완료", "DEBUG")

                current_idx = 1

                if current_idx < total_count:
                    buffers = robot.FR_prepare_chunk_buffers(total_data, current_idx, SETTINGS.robot.robot_buffer_size)
                    robot.FR_send_to_plc_group(SETTINGS.robot.robot_buffer_size, 1, buffers)
                    robot.FR_send_to_plc_info(1, buffers)
                    current_idx += SETTINGS.robot.robot_buffer_size
                    EVENT_BUS.log.message.emit(f"{self._log_prefix} [Robot] Chunk 1 전송 완료", "DEBUG")

                if current_idx < total_count:
                    buffers = robot.FR_prepare_chunk_buffers(total_data, current_idx, SETTINGS.robot.robot_buffer_size)
                    robot.FR_send_to_plc_group(SETTINGS.robot.robot_buffer_size, 2, buffers)
                    robot.FR_send_to_plc_info(2, buffers)
                    current_idx += SETTINGS.robot.robot_buffer_size
                    EVENT_BUS.log.message.emit(f"{self._log_prefix} [Robot] Chunk 2 전송 완료", "DEBUG")

                # 로봇 초기 데이터 장전 완료 알림
                robot_ready_event.set()

                # 메인 스레드의 트리거 및 시작 신호 대기
                if not self._wait_event_with_safety(start_event, timeout=10.0):
                    if self._is_interrupted():
                        raise InterruptedError("작업 중단됨")
                    else:
                        raise TimeoutError("로봇: 시작 신호 대기 시간 초과")

                EVENT_BUS.log.message.emit(f"{self._log_prefix} [Robot] RSR 동작 후 데이터 송신 루프 시작", "DEBUG")
                use_group_1 = True

                # 2. RSR 동작 후, DO46 신호에 맞춰 루프 구동
                while current_idx < total_count and not self._is_interrupted():
                    robot.FR_wait_for_robot_signal(check_interrupt=self._is_interrupted)
                    if self._is_interrupted(): break

                    buffers = robot.FR_prepare_chunk_buffers(total_data, current_idx, SETTINGS.robot.robot_buffer_size)
                    group_num = 1 if use_group_1 else 2

                    robot.FR_send_to_plc_group(SETTINGS.robot.robot_buffer_size, group_num, buffers)
                    robot.FR_send_to_plc_info(group_num, buffers)

                    use_group_1 = not use_group_1
                    current_idx += SETTINGS.robot.robot_buffer_size

                EVENT_BUS.log.message.emit(f"{self._log_prefix} [Robot] 모든 데이터 처리 완료.", "INFO")

            def servo_task():
                try:
                    EVENT_BUS.log.message.emit(f"{self._log_prefix} [Servo] 스레드 시작", "DEBUG")
                    all_data = servo.SM_load_csv_data(sequence_data)
                except Exception as e:
                    EVENT_BUS.log.message.emit(f"{self._log_prefix} [Servo] 데이터 로드 실패: {e}", "ERROR")
                    raise
                
                EVENT_BUS.log.message.emit(f"{self._log_prefix} [Motor] 시퀀스 데이터 변환 완료. 총 {len(all_data)}건", "DEBUG")

                total_len = len(all_data)
                if total_len == 0:
                    servo_ready_event.set()
                    return

                current_ptr = 0

                # 1. 초기 1000개 데이터 로드
                chunk1 = all_data[0:500]
                servo.SM_send_buffer_chunk(1, chunk1)
                ch1 = len(chunk1)
                current_ptr += ch1
                EVENT_BUS.log.message.emit(f"{self._log_prefix} [Servo] Chunk 1 전송 완료", "DEBUG")

                if total_len > 500:
                    chunk2 = all_data[500:1000]
                    servo.SM_send_buffer_chunk(501, chunk2)
                    ch2 = len(chunk2)
                    current_ptr += ch2
                    EVENT_BUS.log.message.emit(f"{self._log_prefix} [Servo] Chunk 2 전송 완료", "DEBUG")                
                else:
                    current_ptr = total_len

                # 서보 초기 데이터 장전 완료 알림
                servo_ready_event.set()

                # 메인 스레드의 트리거 및 시작 신호 대기
                if not self._wait_event_with_safety(start_event, timeout=10.0):
                    if self._is_interrupted():
                        raise InterruptedError("작업 중단됨")
                    else:
                        raise TimeoutError("서보: 시작 신호 대기 시간 초과")

                EVENT_BUS.log.message.emit(f"{self._log_prefix} [Servo] 버퍼 업데이트 감시 루프 시작", "DEBUG")
                servo.watch_buffer_update(all_data, current_ptr, check_interrupt=self._is_interrupted)
                EVENT_BUS.log.message.emit(f"{self._log_prefix} [Servo] 모든 데이터 처리 완료.", "INFO")


            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                """
                두 개의 작업(로봇, 서보)을 동시에 스레드로 던짐
                    아래 두 개의 함수를 동시에 실행시킨 뒤 둘 다 끝날 때까지 기다려.
                    하나라도 죽으면 즉시 보고해. (동기적 대기, Fork-Join 패턴)

                with 문을 사용하여 블록 종료 시 자동으로 shutdown()이 호출됨
                """

                f_robot = pool.submit(robot_task)
                f_servo = pool.submit(servo_task)
                
                # 1. 두 스레드가 초기 준비를 마칠 때까지 대기
                # (에러 감지 및 중단 신호 감시를 위해 폴링 방식 사용)
                while not (robot_ready_event.is_set() and servo_ready_event.is_set()):
                    if self._is_interrupted():
                        raise InterruptedError("사용자에 의해 중단되었습니다.")
                    if f_robot.done() and f_robot.exception():
                        raise f_robot.exception()
                    if f_servo.done() and f_servo.exception():
                        raise f_servo.exception()
                    time.sleep(0.1)
                
                EVENT_BUS.log.message.emit(f"{self._log_prefix} 로봇과 서보 초기 데이터 보내기 완료. 동기화 트리거 준비됨", "INFO")

                # 2. 메인 스레드에서 시작 신호(Trigger) 발송
                wait_time_to_change_signal: float = 0.1
                rsr_signal = FanucSignal.RSR1.path
                robot.trigger_move_signal(rsr_signal, wait_time_to_change_signal)

                EVENT_BUS.log.message.emit(f"{self._log_prefix} >> '{rsr_signal}' 신호 Trigger 완료 🚀", "INFO")

                # 3. 스레드들에게 루프 진입 허가
                start_event.set()

                # 4. 스레드들이 모두 완료될 때까지 대기
                concurrent.futures.wait(
                    [f_robot, f_servo], 
                    return_when=concurrent.futures.FIRST_EXCEPTION
                )

                # 내부에서 예외가 발생했는지 확인 후 다시 던지기
                if f_robot.exception(): raise f_robot.exception()
                if f_servo.exception(): raise f_servo.exception()

        except InterruptedError:
            return False, f"{self._log_prefix} (로봇-모터) 통합 제어 중 사용자에 의해 중단"
        except Exception as e:
            return False, f"{self._log_prefix} (로봇-모터) 통합 제어 중 오류: {e}"
        else:
            return True, f"{self._log_prefix} (로봇-모터) 통합 제어 완료"



class LegacyIntegratedExecutor(BaseExecutor):
    """
    레거시 TXT 파일 형식
    """

    def can_execute(self, sample_data: Dict[str, Any]) -> bool:
        data_keys = set(sample_data.keys())
        # TXT 레거시 키 (axis_x, Y...) 와 서보 키가 공존할 때
        has_legacy_robot = any(k in data_keys for k in ['axis_x', 'axis_y', 'axis_z', 'feed_rate'])
        has_servo = not SERVO_KEYS.isdisjoint(data_keys)
        return has_legacy_robot and has_servo

    def execute(self, sequence_data: List[Dict[str, Any]]) -> tuple[bool, str]:
        EVENT_BUS.log.message.emit(f"{self._log_prefix} 레거시 파일 모드로 실행 (데이터 {len(sequence_data)}건)", "INFO")

        return True, "레거시 파일 모드 실행 완료 -> TODO: 로직 만들어야 된다"
