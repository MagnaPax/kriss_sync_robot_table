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
from models.fanuc_pose_model import FANUCPoseModel, FANUCPose
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
            return True, f"{self._log_prefix} 로봇 목적지 전송 완료"
        except InterruptedError:
            return False, f"{self._log_prefix} 사용자 요청에 의한 작업 중단."
        except Exception as e:
            return False, f"{self._log_prefix} 실행 중 오류: {e}"

        # 로봇 실행 신호 전송
        try:
            if self._is_interrupted():
                return False, f"{self._log_prefix} 사용자에 의한 작업 중단"

            wait_time_to_change_signal: float = 1.0
            rsr_signal: str = FanucSignal.FR_ROBOT_START_VAR2.path
            robot.trigger_move_signal(rsr_signal, wait_time_to_change_signal)
            return True, f"{self._log_prefix} 로봇 trigger 신호 전송 완료"
        except Exception as e:
            return False, f"{self._log_prefix} 실행 중 오류: {e}"




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
            return True, f"{self._log_prefix} 사용자가 입력한 턴테이블 이동 목표 데이터 전송 완료"
        except InterruptedError:
            return False, f"{self._log_prefix} TT 데이터 전송 중 작업 중단됨."
        except Exception as e:
            return False, f"{self._log_prefix} TT 데이터 전송 중 오류: {e}"

        try:
            if self._is_interrupted():
                return False, f"{self._log_prefix} 사용자에 의한 작업 중단"

            adapter.trigger_tt_manual_move()
            return True, f"{self._log_prefix} 사용자가 입력한 턴테이블 trigger 신호 전송 완료"
        except InterruptedError:
            return False, f"{self._log_prefix} TT trigger 신호 전송 중 작업 중단됨."
        except Exception as e:
            return False, f"{self._log_prefix} TT trigger 신호 전송 중 오류: {e}"

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
        여기가 진짜 실행부이다. 로봇과 서보를 지휘하는 지휘자 역할을 한다.
        
        [전체 흐름]
        1. 준비: 툴(드릴 등) 모터를 먼저 윙~ 돌려놓는다.
        2. 1번 스텝: 첫 번째 위치로 로봇과 턴테이블을 보낸다.
        3. 반복 스텝: 2번부터 끝까지 착착착 다음 위치로 이동시킨다.
           - 로봇이 "나 도착했어(DO46)" 라고 하면 다음 지점을 알려주는 식이다.
        4. 종료: 다 끝나면 정리하고 퇴근(Homing)한다.
        """



        # TODO:  QRunnable과 QThreadPool 사용해야 되지 않을까? 제미나이에게 물어보기






        EVENT_BUS.log.message.emit(f"{self._log_prefix} CSV 통합 동기화 제어 시작 (데이터 {len(sequence_data)}건)", "INFO")
        EVENT_BUS.data.sequence_data_loaded.emit(sequence_data)

        robot = self.robot
        servo = self.servo

        total_data = FANUCPoseModel.pre_calculate_all(sequence_data)
        total_count = len(total_data)

        current_idx = 0

        # --- Step 1 --- #
        # 처음 300개의 시퀀스((x, z, feed_rate) * 300 = 900개의 데이터) 전송
        if current_idx < total_count:
            # 
            buffers     = robot.prepare_chunk_buffers(total_data, current_idx, FanucSignal.BUFFER_SIZE)
            # PLC에 전송(send_buffer1 배열에 저장 후 실행)
            robot.send_to_plc_group(1, buffers)
            current_idx += FanucSignal.BUFFER_SIZE

        if current_idx < total_count:
            buffers     = robot.prepare_chunk_buffers(total_data, current_idx, FanucSignal.BUFFER_SIZE)
            # PLC에 전송(send_buffer2 배열에 저장 후 실행)
            robot.send_to_plc_group(2, buffers)
            current_idx += FanucSignal.BUFFER_SIZE
            
        use_group_1 = True



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








class OLD_ServoOnlyExecutor(BaseExecutor):
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

        # 처리할 전체 시퀀스 데이터 방송 (UI 갱신용)
        EVENT_BUS.data.sequence_data_loaded.emit(sequence_data)

        # 설정값 최신화
        self.busy_timeout = SETTINGS.servo.busy_timeout
        self.move_timeout = SETTINGS.servo.move_timeout

        adapter = self.servo
        total_steps = len(sequence_data)
        EVENT_BUS.log.message.emit(f"{self._log_prefix} 서보 시퀀스 시작 (총 {total_steps}건)", "INFO")
        
        # 1. 여기서 전원 켤 필요 없음. 
        # 앱이 실행되자마자 실행되는 모니터링 스레드에서 전원 켠다.

        try:
            # 2. 실행 루프 (하나씩 실행)
            for step_idx, row in enumerate(sequence_data, start=1):

                # 사용자가 멈춤 버튼 눌렀는지 확인
                if self._is_interrupted():
                    raise InterruptedError("사용자가 작업을 중단시켰습니다.")

                # UI 진행률 업데이트
                EVENT_BUS.data.progress_updated.emit(step_idx, total_steps, TaskStatus.PROCESSING)
                EVENT_BUS.log.message.emit(f"{self._log_prefix} {step_idx}/{total_steps} 진행 중...", "DEBUG")
                
                # 변수 초기화
                pose_revolution = None
                pose_rotation = None
                should_move_turntable = True

                # (Pre-Check) 턴테이블을 움직여야 하는지 판단
                pose_turntable = ServoPoseModel.create_for_axis(row, KEY_TURNTABLE_DEG)
                current_turntable_pos = adapter.read_current_servo_motion(ServoAxis.TURNTABLE)['position']

                # 1. 위치 체크: 이미 그 자리에 있으면 안 움직인다.
                if abs(current_turntable_pos - pose_turntable.angle) < 0.05:
                    EVENT_BUS.log.message.emit(
                        f"{self._log_prefix} 턴테이블이 이미 목표 각도({pose_turntable.angle:.2f}°)에 있어서 건너뜁니다.",
                        "INFO"
                    )
                    should_move_turntable = False

                # 2. 속도 체크: 속도가 0이면 안 움직인다.
                elif pose_turntable.velocity <= 0:
                    EVENT_BUS.log.message.emit(
                        f"{self._log_prefix} 턴테이블 속도가 0이라서 건너뜁니다.",
                        "INFO"
                    )
                    should_move_turntable = False

                # 시퀀스 ID 추출
                seq_id = row.get('id', step_idx)
                
                # 로그 메시지
                log_msg = (
                    f"\n"
                    f"{self._log_prefix} 시퀀스 #{seq_id} 실행 시작 ({step_idx}/{total_steps}) | "
                    f"공전={row.get(KEY_TOOL_REV_RPM, 0):.1f}RPM, "
                    f"자전={row.get(KEY_TOOL_ROT_RPM, 0):.1f}RPM, "
                    f"턴테이블={row.get(KEY_TURNTABLE_DEG, 0):.1f}deg, "
                    f"턴테이블 속도={row.get(KEY_TURNTABLE_FEED_RATE, 0):.1f}mm/rev"
                )
                EVENT_BUS.log.message.emit(log_msg, "INFO")

                # [1번 모터] Tool 공전
                if KEY_TOOL_REV_RPM in row:
                    pose_revolution = ServoPoseModel.create_for_axis(row, KEY_TOOL_REV_RPM)
                    if pose_revolution.velocity != 0:
                        adapter.move_velocity(ServoAxis.TOOL_REVOLUTION, pose_revolution.velocity)
                    else:
                        adapter.stop_axis(ServoAxis.TOOL_REVOLUTION)

                    # 에러 체크
                    err_rev = adapter.is_servo_error_active(ServoAxis.TOOL_REVOLUTION)
                    if err_rev['error']:
                        EVENT_BUS.log.message.emit(f"{self._log_prefix} 1번 축 에러 발생! ID: {err_rev['id']}", "ERROR")

                # [2번 모터] Tool 자전
                if KEY_TOOL_ROT_RPM in row:
                    pose_rotation = ServoPoseModel.create_for_axis(row, KEY_TOOL_ROT_RPM)
                    if pose_rotation.velocity != 0:
                        adapter.move_velocity(ServoAxis.TOOL_ROTATION, pose_rotation.velocity)
                    else:
                        adapter.stop_axis(ServoAxis.TOOL_ROTATION)

                    # 에러 체크
                    err_rot = adapter.is_servo_error_active(ServoAxis.TOOL_ROTATION)
                    if err_rot['error']:
                        EVENT_BUS.log.message.emit(f"{self._log_prefix} 2번 축 에러 발생! ID: {err_rot['id']}", "ERROR")

                # [3번 모터] 턴테이블 (핵심)
                # 여기는 위치 제어니까 목표 각도까지 정확히 가야 한다.
                if should_move_turntable:
                    adapter.move_turntable_atomic(ServoAxis.TURNTABLE, pose_turntable.angle, pose_turntable.velocity)

                # (D) 대기 (Stop-and-Go)
                # 턴테이블이 도착할 때까지 여기서 멈춰서 기다린다.
                if should_move_turntable:
                    if not self._wait_for_turntable_completion(ServoAxis.TURNTABLE, target_pos=pose_turntable.angle):
                        adapter.request_immediate_stop()
                        
                        msg = "작업 중단됨" if self._is_interrupted() else f"턴테이블 응답 없음 또는 시간 초과 ({self.move_timeout}s)"
                        return False, msg

                # 잘 끝났는지 결과 확인용 로그
                feedback_revolution = adapter.read_current_servo_motion(ServoAxis.TOOL_REVOLUTION)
                feedback_rotation = adapter.read_current_servo_motion(ServoAxis.TOOL_ROTATION)
                feedback_turntable = adapter.read_current_servo_motion(ServoAxis.TURNTABLE)

                if KEY_TOOL_REV_RPM in row and pose_revolution:
                    EVENT_BUS.log.message.emit(
                        f"{self._log_prefix} 툴 공전 확인: 목표={pose_revolution.velocity:.1f}, 현재={feedback_revolution['velocity']:.1f}", "DEBUG"
                    )
                if KEY_TOOL_ROT_RPM in row and pose_rotation:
                    EVENT_BUS.log.message.emit(
                        f"{self._log_prefix} 툴 자전 확인: 목표={pose_rotation.velocity:.1f}, 현재={feedback_rotation['velocity']:.1f}", "DEBUG"
                    )
                EVENT_BUS.log.message.emit(
                    f"{self._log_prefix} 턴테이블 확인: 목표={pose_turntable.angle:.1f}, 현재={feedback_turntable['position']:.1f}", "DEBUG"
                )

                # 이번 스텝 완료!
                EVENT_BUS.data.progress_updated.emit(step_idx, total_steps, TaskStatus.COMPLETED)

            return True, "모든 서보 작업이 완료되었습니다."

        except InterruptedError as e:
            EVENT_BUS.log.message.emit(f"{self._log_prefix} 사용자가 멈췄음. 서보 정지 시키는 중...", "WARNING")
            adapter.request_immediate_stop()
            return False, str(e)

        except Exception as e:
            try:
                adapter.request_immediate_stop()
            except Exception:
                pass 
                
            return False, f"{self._log_prefix} 오류 발생: {str(e)}"

        finally:
            # 끝났다고 알림
            EVENT_BUS.data.sequence_job_finished.emit()

            # 3. 종료 처리 (안전하게 끄기)
            EVENT_BUS.log.message.emit(f"{self._log_prefix} 서보 모터를 안전하게 끕니다...", "DEBUG")

            is_safely_shutdown = adapter.shutdown_all_with_power_off(timeout=self.move_timeout)

            if is_safely_shutdown:
                EVENT_BUS.log.message.emit(f"{self._log_prefix} 깔끔하게 종료되었습니다.", "INFO")
            else:
                EVENT_BUS.log.message.emit(f"{self._log_prefix} 경고: 끄는데 너무 오래 걸리거나 문제가 있었습니다.", "WARNING")


    def _wait_for_turntable_completion(self, axis_idx: int, target_pos: Optional[float] = None) -> bool:
        EVENT_BUS.log.message.emit(f"{self._log_prefix} 턴테이블 이동 완료 대기 중...", "DEBUG")
        """
        [대기 로직] 턴테이블이 목표에 도착할 때까지 지켜보는 함수이다.
        1. "움직이기 시작했니?" (Busy 확인)
        2. "다 움직였니?" (Busy 꺼짐 확인 & 위치 확인)
        Returns: 잘 도착하면 True, 아니면 False
        """
        try:
            # -------------------------------------------------------------
            # Phase 1: 움직임 시작 감지
            # -------------------------------------------------------------
            start_wait = time.time()
            busy_detected = False

            start_wait = time.time()
            busy_detected = False

            while time.time() - start_wait < self.busy_timeout:
                
                # 실제로 움직임?
                moving = self.servo.is_servo_moving_physically(axis_idx)
                
                if moving:
                    busy_detected = True
                    EVENT_BUS.control.servo_physical_moving_status_changed.emit({'is_servo_moving': True})
                else:
                    # 안 움직임? 목표에 이미 가있나?
                    if target_pos is not None:
                        current_pos = self.servo.read_current_servo_motion(axis_idx)['position']
                        # 오차범위 0.05도
                        if abs(current_pos - target_pos) < 0.05: 
                            EVENT_BUS.log.message.emit(
                                f"{self._log_prefix} 이미 목표 위치({target_pos:.3f})에 도착해 있습니다.", 
                                "DEBUG"
                            )
                            return True
                
                # 움직이다가 멈춤 -> 도착!
                if busy_detected and not moving:
                    feedback = self.servo.read_current_servo_motion(axis_idx)
                    actual_pos = feedback['position']
                    EVENT_BUS.log.message.emit(
                        f"{self._log_prefix} 이동 완료: 목표={target_pos:.3f}, 현재={actual_pos:.3f}", 
                        "DEBUG"
                    )
                    return True

                # 도중에 정지 버튼 눌렸나?
                if self._is_interrupted():
                    return False

                time.sleep(0.1)
            
            # 한참 기다려도 꼼짝도 안 하면 에러다.
            if not busy_detected:
                EVENT_BUS.log.message.emit(f"{self._log_prefix} 반응이 없습니다 (Busy Timeout)", "ERROR")
                return False

            # -------------------------------------------------------------
            # Phase 2: 움직임 끝날 때까지 대기
            # -------------------------------------------------------------
            move_start_time = time.time()

            # 계속 움직이는 중이면 여기서 뺑뺑이 돈다.
            while self.servo.is_servo_moving_physically(axis_idx):
                if self._is_interrupted(): return False

                if time.time() - move_start_time > self.move_timeout:
                    EVENT_BUS.log.message.emit(f"{self._log_prefix} 너무 오래 걸려서 타임아웃 되었습니다.", "ERROR")
                    return False

            feedback = self.servo.read_current_servo_motion(axis_idx)
            actual_pos = feedback['position']
            EVENT_BUS.log.message.emit(
                f"{self._log_prefix} 이동 완료: 목표={target_pos:.3f}, 현재={actual_pos:.3f}", 
                "DEBUG"
            )
            return True
        
        finally:
            # 어쨌든 끝났으니 바쁨 신호는 끈다.
            EVENT_BUS.control.servo_physical_moving_status_changed.emit({'is_servo_moving': False})

    def _is_interrupted(self) -> bool:
        """누가 "그만해!"(정지) 라고 했는지 확인함."""
        return bool((thread := QThread.currentThread()) and thread.isInterruptionRequested())


