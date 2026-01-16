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
from models.fanuc_pose_model import FANUCPose
FanucPoseModel = FANUCPose # Alias for consistency
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


# =========================================================
# 2. 전략 구현 (Strategies)
# =========================================================
class FanucOnlyExecutor(BaseExecutor):
    """로봇 단독 제어 (Packet-Only SSOT, DO46 Rising-Edge Sync)"""

    # Trigger packet pulse widths (tune if needed)
    PRE_TRIGGER_DELAY_S = 0.05      # time between load packet and trigger packet
    TRIGGER_HOLD_S = 0.05           # time to keep DI43=True before sending DI43=False reset packet
    MOVE_TIMEOUT = 60.0             # Default timeout

    def __init__(self, robot: FanucAdapter, servo: ServoAdapter):
        super().__init__(robot, servo)
        self.MOVE_TIMEOUT = getattr(SETTINGS.servo, "move_timeout", 60.0)

    def can_execute(self, sample_data: Dict[str, Any]) -> bool:
        """
        이 실행기가 주어진 데이터를 처리할 수 있는지 판단함.
        로봇 키(X,Y,Z...)만 있고 서보 키(Rev,Rot,TT...)가 없을 때 True를 반환함.
        """
        data_keys = set(sample_data.keys())
        has_robot = not ROBOT_KEYS.isdisjoint(data_keys)
        has_servo = not SERVO_KEYS.isdisjoint(data_keys)
        # 로봇 키가 있고, 서보 키는 없을 때
        return has_robot and not has_servo

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------
    def _pack_simple_motion(
        self,
        current_pose: FanucPoseModel,
        target_pose: FanucPoseModel,
        *,
        is_trigger: bool,
        is_loop_active: bool,
    ) -> Any:
        """턴테이블 계산 없이, 순수 로봇 이동 + 신호만 담은 패킷 생성."""
        signals = {
            FanucSignal.IMSP: True,
            FanucSignal.HOLD: True,
            FanucSignal.SFSP: True,
            FanucSignal.ENABLE: True,
            FanucSignal.RSR3: True,  # DO46 Sync Mode
            FanucSignal.TRIGGER_DI43: is_trigger,     # Pulse
            FanucSignal.LOOP_DI44: is_loop_active,    # Hold
        }
        return target_pose.to_struct(current_pose, signals)

    def _apply_feed_override_safe(self, pose: FanucPoseModel) -> FanucPoseModel:
        """
        override_feed_rate가 있으면 '더 느릴 때만' 적용(min).
        """
        ov = getattr(self.robot, "override_feed_rate", None)
        if ov is not None:
            feed = min(pose.f, ov)
            return FanucPoseModel(
                x=pose.x, y=pose.y, z=pose.z,
                w=pose.w, p=pose.p, r=pose.r,
                f=feed
            )
        return pose

    def _send_step_packets_packet_only(
        self,
        robot: "FanucAdapter",
        current_pose: FanucPoseModel,
        target_pose: FanucPoseModel,
        *,
        loop_active: bool,
        done_event: threading.Event,
    ) -> None:
        """
        Packet-only SSOT로 한 스텝을 발사한다.

        Sequence:
        1) Load  (DI43=False, DI44=loop_active)  -> data preload + DI43 reset
        2) wait PRE_TRIGGER_DELAY_S
        3) Trigger (DI43=True,  DI44=loop_active)
        4) hold TRIGGER\_HOLD\_S
        5) Reset (DI43=False, DI44=loop_active)  -> explicit pulse close (important for Step1 too)

        done_event는 Trigger 직전에 clear하여 레이스를 줄인다.
        """
        # 1) Load (DI43=False)
        try:
            packet_load = self._pack_simple_motion(
                current_pose, target_pose,
                is_trigger=False, is_loop_active=loop_active
            )
            robot.write_command_packet(packet_load)
        except Exception as e:
            EVENT_BUS.log.message.emit(f"{self._log_prefix} Step Packet [LOAD] 실패: {e}", "ERROR")
            raise

        # 2) separation delay (PLC scan / ADS update window)
        time.sleep(self.PRE_TRIGGER_DELAY_S)

        # 3) Trigger (DI43=True)
        done_event.clear()
        try:
            packet_trigger = self._pack_simple_motion(
                current_pose, target_pose,
                is_trigger=True, is_loop_active=loop_active
            )
            robot.write_command_packet(packet_trigger)
        except Exception as e:
            EVENT_BUS.log.message.emit(f"{self._log_prefix} Step Packet [TRIGGER] 실패: {e}", "ERROR")
            raise

        # 4) hold pulse width
        time.sleep(self.TRIGGER_HOLD_S)

        # 5) Reset (DI43=False) — close pulse explicitly
        try:
            packet_reset = self._pack_simple_motion(
                current_pose, target_pose,
                is_trigger=False, is_loop_active=loop_active
            )
            robot.write_command_packet(packet_reset)
        except Exception as e:
            EVENT_BUS.log.message.emit(f"{self._log_prefix} Step Packet [RESET] 실패: {e}", "ERROR")
            raise

    # -------------------------------------------------------------------------
    # Main
    # -------------------------------------------------------------------------
    def execute(self, sequence_data: List[Dict[str, Any]]) -> tuple[bool, str]:
        """
        FANUC 로봇 단독 제어 (Packet-Only SSOT)

        프로토콜:
        - DI44: 루프 동안 High 유지 (packet bit)
        - DI43: 매 스텝 Load(False) -> Trigger(True) -> Reset(False) (packet bit)
        - DO46: Rising edge로 스텝 진행 (notification callback)
        """
        if not sequence_data:
            return True, "데이터가 없습니다."

        EVENT_BUS.log.message.emit(f"{self._log_prefix} FanucOnly 모드 시작 (데이터 {len(sequence_data)}건)", "INFO")
        EVENT_BUS.data.sequence_data_loaded.emit(sequence_data)

        robot = self.robot
        total_steps = len(sequence_data)

        # DO46(이동 완료) 이벤트
        robot_motion_done_event = threading.Event()

        # Edge detection state (closure)
        prev_do46_val = False

        def _on_motion_done_edge_detect(*args):
            nonlocal prev_do46_val

            # 1) extract raw val
            raw_val = None
            try:
                if len(args) == 2:
                    raw_val = args[1]
                elif len(args) >= 3:
                    raw_val = args[-1] if isinstance(args[-1], (bool, int, bytes, bytearray)) else args[1]

                # 2) deep extraction
                for _ in range(3):
                    if hasattr(raw_val, "contents"):
                        raw_val = raw_val.contents
                    elif hasattr(raw_val, "data"):
                        raw_val = raw_val.data
                    elif hasattr(raw_val, "value"):
                        raw_val = raw_val.value
                    else:
                        break
            except Exception:
                raw_val = False

            # 3) normalize
            current_val = False
            try:
                if isinstance(raw_val, (bool, int)):
                    current_val = bool(raw_val)
                elif isinstance(raw_val, (bytes, bytearray)):
                    current_val = (int.from_bytes(raw_val, "little") != 0)
                else:
                    current_val = False
            except Exception:
                current_val = False

            # Rising edge: 0 -> 1
            if (not prev_do46_val) and current_val:
                robot_motion_done_event.set()

            prev_do46_val = current_val

        # ---- DO46 init order: read signal -> register callback
        try:
            prev_do46_val = robot.read_complete_signal()
        except Exception:
            prev_do46_val = False

        # Callback registration: if it fails, STOP immediately (critical)
        try:
            handle_motion = robot.register_robot_motion_done_callback(_on_motion_done_edge_detect)
        except Exception as e:
            EVENT_BUS.log.message.emit(f"{self._log_prefix} DO46 콜백 등록 실패로 작업 중단: {e}", "ERROR")
            # [Safety] 등록 실패 시에도 신호 Reset 시도
            try:
                cleanup_signals = {
                    FanucSignal.IMSP: True, FanucSignal.HOLD: True, FanucSignal.SFSP: True, FanucSignal.ENABLE: True,
                    FanucSignal.TRIGGER_DI43: False,
                    FanucSignal.LOOP_DI44: False
                }
                cleanup_packet = FanucPoseModel.create_signal_only_packet(cleanup_signals)
                robot.write_command_packet(cleanup_packet)
            except: pass
            return False, "DO46 콜백 등록 실패"

        try:
            robot.validate_robot_ready()

            # Step 1
            current_pose = robot.get_current_pose_model()
            target_pose = FanucPoseModel.from_dict(sequence_data[0])
            target_pose = self._apply_feed_override_safe(target_pose)

            EVENT_BUS.data.progress_updated.emit(1, total_steps, TaskStatus.PROCESSING)

            # Send Step1 packets (explicit pulse close)
            self._send_step_packets_packet_only(
                robot, current_pose, target_pose,
                loop_active=True,
                done_event=robot_motion_done_event,
            )
            current_pose = target_pose

            # Step 2+
            for i in range(1, total_steps):
                step_idx = i + 1

                # Wait DO46 of previous step
                if not self._wait_event_with_safety(robot_motion_done_event, timeout=self.MOVE_TIMEOUT):
                    if self._is_interrupted():
                        raise InterruptedError("사용자가 작업을 중단했습니다.")
                    raise TimeoutError(f"[Step {step_idx}] 로봇 이동 대기(DO46) 시간 초과됨")

                robot_motion_done_event.clear()

                # Prepare next target
                target_pose = FanucPoseModel.from_dict(sequence_data[i])
                target_pose = self._apply_feed_override_safe(target_pose)

                # Pre-load + trigger + reset via packets
                self._send_step_packets_packet_only(
                    robot, current_pose, target_pose,
                    loop_active=True,
                    done_event=robot_motion_done_event,
                )

                EVENT_BUS.data.progress_updated.emit(i, total_steps, TaskStatus.COMPLETED)
                EVENT_BUS.data.progress_updated.emit(step_idx, total_steps, TaskStatus.PROCESSING)

                EVENT_BUS.log.message.emit(f"{self._log_prefix}  -> [Step {step_idx}] 출발! (Packet DI43 Pulse)", "DEBUG")

                current_pose = target_pose

            # Wait last move done (best effort)
            EVENT_BUS.log.message.emit(f"{self._log_prefix} 마지막 이동 완료 대기 중...", "INFO")
            if not self._wait_event_with_safety(robot_motion_done_event, timeout=self.MOVE_TIMEOUT):
                EVENT_BUS.log.message.emit(f"{self._log_prefix} 마지막 로봇 이동 대기 시간 초과됨 (무시하고 종료)", "WARNING")

            # Finish protocol: loop off + trigger off (signal-only packet)
            EVENT_BUS.log.message.emit(f"{self._log_prefix} 종료 프로토콜 실행 (Zero Payload 전송)...", "DEBUG")
            signals_finish = {
                FanucSignal.IMSP: True,
                FanucSignal.HOLD: True,
                FanucSignal.SFSP: True,
                FanucSignal.ENABLE: True,
                FanucSignal.RSR3: True,
                FanucSignal.TRIGGER_DI43: False,
                FanucSignal.LOOP_DI44: False,
            }
            zero_packet = FanucPoseModel.create_signal_only_packet(signals_finish)
            robot.write_command_packet(zero_packet)

            EVENT_BUS.data.progress_updated.emit(total_steps, total_steps, TaskStatus.COMPLETED)
            return True, "작업이 성공적으로 완료됨"

        except InterruptedError as e:
            EVENT_BUS.log.message.emit(f"{self._log_prefix} 작업 중단: {e}", "WARNING")
            try:
                robot.set_emergency_stop()
            except Exception:
                pass
            return False, str(e)

        except Exception as e:
            EVENT_BUS.log.message.emit(f"{self._log_prefix} 오류 발생: {e}", "ERROR")
            try:
                robot.set_emergency_stop()
            except Exception:
                pass
            return False, f"Error: {e}"

        finally:
            EVENT_BUS.data.sequence_job_finished.emit()

            try:
                if handle_motion is not None:
                    robot.remove_notification(handle_motion)
            except Exception:
                pass

            # Packet-based cleanup: ensure DI43/DI44 are OFF
            try:
                cleanup_signals = {
                    FanucSignal.IMSP: True,
                    FanucSignal.HOLD: True,
                    FanucSignal.SFSP: True,
                    FanucSignal.ENABLE: True,
                    FanucSignal.TRIGGER_DI43: False,
                    FanucSignal.LOOP_DI44: False,
                }
                cleanup_packet = FanucPoseModel.create_signal_only_packet(cleanup_signals)
                robot.write_command_packet(cleanup_packet)
            except Exception:
                pass

    def _wait_event_with_safety(self, event: threading.Event, timeout: float) -> bool:
        """
        [안전 대기] 이벤트를 기다리는 동안 정지 버튼 확인.
        """
        start = time.time()
        while time.time() - start < timeout:
            if (t := QThread.currentThread()) and t.isInterruptionRequested():
                return False
            if event.wait(0.1):
                return True
        return False

    def _is_interrupted(self) -> bool:
        """안전장치: 현재 실행 중인 스레드가 정지 요청을 받았는지 확인한다."""
        return bool((thread := QThread.currentThread()) and thread.isInterruptionRequested())

class ServoOnlyExecutor(BaseExecutor):
    """
    [서보 모터 전용 실행기]
    로봇 없이 Panasonic 서보 모터 3축(툴 2개 + 턴테이블 1개)만 단독으로 제어함.
    주로 서보 모터 테스트나 캘리브레이션 용도로 쓰임.
    """

    def __init__(self, robot: FanucAdapter, servo: ServoAdapter):
        super().__init__(robot, servo)
        
        # 서보가 움직임을 완료할 때까지 얼마나 기다려줄지 설정파일에서 가져옴.
        self.BUSY_TIMEOUT = SETTINGS.servo.busy_timeout
        self.MOVE_TIMEOUT = SETTINGS.servo.move_timeout

    def can_execute(self, sample_data: Dict[str, Any]) -> bool:
        """
        데이터에 서보 관련 키(Rev,Rot...)만 있고 로봇 키는 없을 때 실행 가능함.
        """
        data_keys = set(sample_data.keys())
        has_robot = not ROBOT_KEYS.isdisjoint(data_keys)
        has_servo = not SERVO_KEYS.isdisjoint(data_keys)
        # 서보 키가 있고, 로봇 키는 없을 때
        return has_servo and not has_robot

    def execute(self, sequence_data: List[Dict[str, Any]]) -> tuple[bool, str]:
        """
        [두뇌] 시퀀스 데이터를 순차적으로 실행
        Returns: (성공여부, 결과메시지)
        """
        EVENT_BUS.log.message.emit(f"{self._log_prefix} 서보 단독 제어 시작 (데이터 {len(sequence_data)}건)", "INFO")
        EVENT_BUS.log.message.emit(f"{self._log_prefix} 에서 처리될 전체 데이터\n{(sequence_data)}\n", "DEBUG")

        # 처리할 전체 시퀀스 데이터 방송 - execute 가 실행될 때 마다 이 시그널을 구독하는 ui가 갱신된다
        EVENT_BUS.data.sequence_data_loaded.emit(sequence_data)

        # 설정값 최신화 (실행 시점의 Settings 값 적용)
        self.BUSY_TIMEOUT = SETTINGS.servo.busy_timeout
        self.MOVE_TIMEOUT = SETTINGS.servo.move_timeout

        adapter = self.servo
        total_steps = len(sequence_data)
        EVENT_BUS.log.message.emit(f"{self._log_prefix} 서보 시퀀스 시작 (총 {total_steps}건)", "INFO")
        
        # 1. 초기화 (Setup) - 전원 ON
        for axis in ServoAxis:
            adapter.set_servo_state(axis, True)
            # [SAFETY CHECK] 실행 전 서보 에러 확인
            if adapter.has_servo_error(axis):
                raise RuntimeError(f"서보 축({axis.name})에 에러가 감지되었습니다. 작업을 중단합니다.")

        try:
            # 2. 실행 루프 (Loop)
            for step_idx, row in enumerate(sequence_data, start=1):

                # (A) 중단 요청 확인
                if self._is_interrupted():
                    raise InterruptedError("사용자에 의해 작업이 중단되었습니다.")

                # (B) UI 진행률 업데이트
                # 현재 시퀀스 스탭 상태: 처리 중
                EVENT_BUS.data.progress_updated.emit(step_idx, total_steps, TaskStatus.PROCESSING)
                EVENT_BUS.log.message.emit(f"{self._log_prefix} {step_idx}/{total_steps} 진행 중", "DEBUG")

                # (Pre-Check) 턴테이블 이동 결정
                pose_turntable = ServoPoseModel.create_for_axis(row, KEY_TURNTABLE_DEG)
                current_turntable_pos = adapter.read_current_servo_motion(ServoAxis.TURNTABLE)['position']
                
                should_move_turntable = True

                # 1. 위치 체크: 이미 목표 위치에 있는가?
                if abs(current_turntable_pos - pose_turntable.angle) < 0.05:
                    EVENT_BUS.log.message.emit(
                        f"{self._log_prefix} 턴테이블이 이미 목표 각도({pose_turntable.angle:.2f}°)에 있습니다. 이동 스킵.",
                        "INFO"
                    )
                    should_move_turntable = False

                # 2. 속도 체크: 속도가 0인가?
                elif pose_turntable.velocity <= 0:
                    EVENT_BUS.log.message.emit(
                        f"{self._log_prefix} 턴테이블 속도가 0입니다. 이동 스킵.",
                        "INFO"
                    )
                    should_move_turntable = False

                # (C) 명령 생성 및 전송
                seq_id = row.get('id', step_idx)
                # 보기 좋게 주요 파라미터만 추출하여 로그 출력
                log_msg = (
                    f"\n"
                    f"{self._log_prefix} 시퀀스 #{seq_id} 실행 시작 ({step_idx}/{total_steps}) | "
                    f"공전={row.get(KEY_TOOL_REV_RPM, 0):.1f}RPM, "
                    f"자전={row.get(KEY_TOOL_ROT_RPM, 0):.1f}RPM, "
                    f"턴테이블={row.get(KEY_TURNTABLE_DEG, 0):.1f}deg, "
                    f"턴테이블 속도={row.get(KEY_TURNTABLE_FEED_RATE, 0):.1f}mm/rev"
                )
                EVENT_BUS.log.message.emit(log_msg, "INFO")

                # [Axis 1] Tool 공전 (속도 제어)
                if KEY_TOOL_REV_RPM in row:
                    pose_revolution = ServoPoseModel.create_for_axis(row, KEY_TOOL_REV_RPM)
                    EVENT_BUS.log.message.emit(f"{self._log_prefix} pose_revolution 생성: {pose_revolution}", "DEBUG")
                    if pose_revolution.velocity != 0:
                        adapter.move_velocity(ServoAxis.TOOL_REVOLUTION, pose_revolution.velocity)
                    else:
                        adapter.stop_axis(ServoAxis.TOOL_REVOLUTION)

                    # 명령 후 즉시 에러 체크
                    err_rev = adapter.is_servo_error_active(ServoAxis.TOOL_REVOLUTION)
                    if err_rev['error']:
                        EVENT_BUS.log.message.emit(f"{self._log_prefix} Axis 1 에러 발생! ID: {err_rev['id']}", "ERROR")

                # [Axis 2] Tool 자전 (속도 제어)
                if KEY_TOOL_ROT_RPM in row:
                    pose_rotation = ServoPoseModel.create_for_axis(row, KEY_TOOL_ROT_RPM)
                    EVENT_BUS.log.message.emit(f"{self._log_prefix} pose_rotation 생성: {pose_rotation}", "DEBUG")
                    if pose_rotation.velocity != 0:
                        adapter.move_velocity(ServoAxis.TOOL_ROTATION, pose_rotation.velocity)
                    else:
                        adapter.stop_axis(ServoAxis.TOOL_ROTATION)

                    # 명령 후 즉시 에러 체크
                    err_rot = adapter.is_servo_error_active(ServoAxis.TOOL_ROTATION)
                    if err_rot['error']:
                        EVENT_BUS.log.message.emit(f"{self._log_prefix} Axis 2 에러 발생! ID: {err_rot['id']}", "ERROR")

                # [Axis 3] 턴테이블 (위치 제어)
                EVENT_BUS.log.message.emit(f"{self._log_prefix} pose_turntable 생성: {pose_turntable}", "DEBUG")
                if should_move_turntable:
                    adapter.move_turntable_atomic(ServoAxis.TURNTABLE, pose_turntable.angle, pose_turntable.velocity)

                # (D) 대기 (Stop-and-Go)
                # 각 스텝의 이동이 물리적으로 완료될 때까지 여기서 멈춰서 기다림.
                # 단, 이동 명령을 내리지 않은 경우(should_move_turntable=False)는 기다리지 않음.
                if should_move_turntable:
                    if not self._wait_for_turntable_completion(ServoAxis.TURNTABLE, target_pos=pose_turntable.angle):
                        adapter.request_immediate_stop()
                        
                        # 왜 멈췄는지 이유를 파악해서 보고함
                        msg = "작업 중단됨" if self._is_interrupted() else f"턴테이블 응답 없음 또는 시간 초과 ({self.MOVE_TIMEOUT}s)"
                        return False, msg

                # 개발용 로그
                feedback_revolution = adapter.read_current_servo_motion(ServoAxis.TOOL_REVOLUTION)
                feedback_rotation = adapter.read_current_servo_motion(ServoAxis.TOOL_ROTATION)
                feedback_turntable = adapter.read_current_servo_motion(ServoAxis.TURNTABLE)

                if KEY_TOOL_REV_RPM in row:
                    EVENT_BUS.log.message.emit(
                        f"{self._log_prefix} 툴 공전 (RPM) 완료: 목표={pose_revolution.velocity:.1f}, 현재={feedback_revolution['velocity']:.1f}", "DEBUG"
                    )
                if KEY_TOOL_ROT_RPM in row:
                    EVENT_BUS.log.message.emit(
                        f"{self._log_prefix} 툴 자전 (RPM) 완료: 목표={pose_rotation.velocity:.1f}, 현재={feedback_rotation['velocity']:.1f}", "DEBUG"
                    )
                EVENT_BUS.log.message.emit(
                    f"{self._log_prefix} 턴테이블 (deg & RPM) 완료: 목표={pose_turntable.angle:.1f} & {pose_turntable.velocity:.1f}, 현재={feedback_turntable['position']:.1f} & {feedback_turntable['velocity']:.1f}", "DEBUG"
                )

                # (E) 현재 시퀀스 스탭 상태: 완료
                EVENT_BUS.data.progress_updated.emit(step_idx, total_steps, TaskStatus.COMPLETED)

            return True, "모든 서보 시퀀스 작업이 완료되었습니다."

        except InterruptedError as e:
            EVENT_BUS.log.message.emit(f"{self._log_prefix} 작업이 사용자에 의해 중단되었습니다. 서보 정지 신호 전송...", "WARNING")
            adapter.request_immediate_stop()
            return False, str(e)

        except Exception as e:
            try:
                adapter.request_immediate_stop()
            except Exception:
                pass # 에러 처리 중 발생한 에러는 무시(원래 발생한 에러가 더 중요함)
                
            return False, f"{self._log_prefix} 오류 발생: {str(e)}"

        finally:
            # 시퀀스 실행 종료 방송
            EVENT_BUS.data.sequence_job_finished.emit()

            # 3. 종료 처리 (Teardown)
            EVENT_BUS.log.message.emit(f"{self._log_prefix} 종료 절차: 서보모터 정지 및 전원 차단을 시도합니다...", "DEBUG")

            # MOVE_TIMEOUT을 통해 충분한 감속시간 확보
            is_safely_shutdown = adapter.shutdown_all_with_power_off(timeout=self.MOVE_TIMEOUT)

            if is_safely_shutdown:
                EVENT_BUS.log.message.emit(f"{self._log_prefix} 모든 서보모터가 안전하게 종료되었습니다. ", "INFO")
            else:
                EVENT_BUS.log.message.emit(f"{self._log_prefix} 경고: 정지 대기 시간 초과({self.MOVE_TIMEOUT}s). 되었거나 종료 절차 중 오류가 발생하였습니다.", "WARNING")


    def _wait_for_turntable_completion(self, axis_idx: int, target_pos: Optional[float] = None) -> bool:
        EVENT_BUS.log.message.emit(f"{self._log_prefix} {axis_idx}축 이동 완료 대기 중...", "DEBUG")
        """
        턴테이블이 실제로 목표 위치에 도착할 때까지 기다리는 함수임.
        1. 먼저 모터가 '나 움직이기 시작했어(Busy)'라고 신호를 줄 때까지 기다림.
        2. 그 다음 모터가 '나 도착해서 멈췄어'라고 할 때까지 기다림.
        Returns: 성공하면 True, 실패하거나 중단되면 False
        """
        try:
            # -------------------------------------------------------------
            # Phase 1: Busy 신호 감지 (움직임 시작 확인)
            # -------------------------------------------------------------
            # 명령을 보내자마자 바로 확인하면 아직 안 움직이고 있을 수도 있어서,
            # 잠시 동안 반복해서 체크함.
            start_wait = time.time()
            busy_detected = False

            while time.time() - start_wait < self.BUSY_TIMEOUT:
                
                # (A) 실제로 움직이고 있는지 (속도 체크)
                moving = self.servo.is_servo_moving_physically(axis_idx)
                
                if moving:
                    busy_detected = True
                    EVENT_BUS.control.servo_physical_moving_status_changed({'is_servo_moving': True})
                else:
                    # 안 움직이는데? -> 혹시 이미 목표 위치에 있나?
                    if target_pos is not None:
                        current_pos = self.servo.read_current_servo_motion(axis_idx)['position']
                        # 오차 0.05도 이내면 "이미 도착해있음"으로 간주하고 성공 처리
                        if abs(current_pos - target_pos) < 0.05: 
                            EVENT_BUS.log.message.emit(
                                f"{self._log_prefix} 축 {axis_idx}가 이미 목표 위치({target_pos:.3f})에 있으므로 대기를 종료합니다.", 
                                "DEBUG"
                            )
                            return True
                
                # (B) 움직이다가 멈췄으면 -> 도착한 것임!
                if busy_detected and not moving:
                    feedback = self.servo.read_current_servo_motion(axis_idx)
                    actual_pos = feedback['position']
                    EVENT_BUS.log.message.emit(
                        f"{self._log_prefix} Axis {axis_idx} 이동 완료: CSV목표={target_pos:.3f}, 현재위치={actual_pos:.3f}", 
                        "DEBUG"
                    )
                    return True

                # (C) 사용자가 정지 버튼 눌렀는지 체크
                if self._is_interrupted():
                    return False

                time.sleep(0.1)
            
            # 기다려도 끝까지 안 움직이면 뭔가 잘못된 것임
            if not busy_detected:
                EVENT_BUS.log.message.emit(f"{self._log_prefix} 축 {axis_idx} 반응 없음 (Busy Timeout)", "ERROR")
                return False

            # -------------------------------------------------------------
            # Phase 2: 도착 대기 (움직임 종료 확인)
            # -------------------------------------------------------------
            move_start_time = time.time()

            # 계속 움직이는 동안은 여기서 뱅뱅 돌면서 기다림
            while self.servo.is_servo_moving_physically(axis_idx):
                # 중단 요청 체크
                if self._is_interrupted(): return False

                # 너무 오래 걸리면 에러 (타임아웃)
                if time.time() - move_start_time > self.MOVE_TIMEOUT:
                    EVENT_BUS.log.message.emit(f"{self._log_prefix} 축 {axis_idx} 이동 시간 초과 ({self.MOVE_TIMEOUT}초)", "ERROR")
                    return False

            feedback = self.servo.read_current_servo_motion(axis_idx)
            actual_pos = feedback['position']
            EVENT_BUS.log.message.emit(
                f"{self._log_prefix} Axis {axis_idx} 이동 완료: CSV목표={target_pos:.3f}, 현재위치={actual_pos:.3f}", 
                "DEBUG"
            )
            return True
        
        finally:
            # 성공/실패 여부에 상관없이 마지막에는 바쁨 신호를 해제
            EVENT_BUS.control.servo_physical_moving_status_changed({'is_servo_moving': False})

    def _is_interrupted(self) -> bool:
        """
        [안전장치] 현재 스레드 중단 요청 확인
        Walrus operator(:=)를 사용하여 None 체크와 메서드 호출을 한 번에 처리
        """
        # 1. thread 변수에 현재 스레드 할당
        # 2. thread가 None이 아니면(True), 뒤의 isInterruptionRequested() 호출
        # 3. thread가 None이면(False), 바로 False 반환
        return bool((thread := QThread.currentThread()) and thread.isInterruptionRequested())

class IntegratedExecutor(BaseExecutor):
    """CSV 파일 형식 (로봇 + 턴테이블 통합 제어)"""

    def __init__(self, robot: FanucAdapter, servo: ServoAdapter):
        super().__init__(robot, servo)
        
        # 서보를 기다려주는 시간 (설정 파일에서 값 로드)
        self.BUSY_TIMEOUT = SETTINGS.servo.busy_timeout
        self.MOVE_TIMEOUT = SETTINGS.servo.move_timeout

    def can_execute(self, sample_data: Dict[str, Any]) -> bool:
        data_keys = set(sample_data.keys())
        has_robot = not ROBOT_KEYS.isdisjoint(data_keys)
        has_servo = not SERVO_KEYS.isdisjoint(data_keys)
        has_specific_key = (KEY_TURNTABLE_DEG in data_keys) or (KEY_ROBOT_X in data_keys)
        return has_robot and has_servo and has_specific_key

    def _calculate_and_pack(
        self, 
        current_robot_pose: FanucPoseModel, 
        target_robot_pose: FanucPoseModel, 
        current_turntable_angle: float,
        target_turntable_angle: float,
        target_turntable_velocity: float,
        previous_robot_velocity: float, 
        data_ready: bool, 
        start_trigger: bool
    ) -> tuple[Any, float]:
        """
        [Helper] 로봇 속도 계산 및 데이터 패킷 생성 함수임.
        
        핵심 원리:
        "서보 모터가 움직이는 시간 동안 로봇도 딱 맞춰서 움직이게 하자!"
        -> 턴테이블이 A에서 B로 가는 데 3초가 걸린다면, 로봇도 3초 동안 움직일 수 있는 속도로 설정함.
        
        Returns: (PLC로 보낼 패킷 구조체, 계산된 로봇 속도)
        """
        # 1. 턴테이블 이동 시간 계산
        # (목표 각도 - 현재 각도) / 속도 = 걸리는 시간
        tt_delta = abs(target_turntable_angle - current_turntable_angle)
        expected_move_time = tt_delta / target_turntable_velocity if target_turntable_velocity > 0 else 0.0
        
        # 2. 로봇 이동 거리 계산
        # 현재 위치에서 목표 위치까지의 직선 거리 (mm)
        robot_dist, _ = current_robot_pose.distance_to(target_robot_pose)
        
        # 3. 로봇 속도 역산 (속도 = 거리 / 시간)
        if robot_dist < 0.001: 
            # 로봇이 움직일 거리가 없으면 속도도 0
            robot_calculated_velocity = 0.0
        elif expected_move_time < 0.001:
            # 턴테이블은 안 움직이는데 로봇만 움직여야 할 때
            # 이전 속도를 그대로 쓰거나, 기본값(100.0) 사용
            robot_calculated_velocity = previous_robot_velocity if previous_robot_velocity > 0 else 100.0
        else:
            # 거리 / 시간 = 속도
            robot_calculated_velocity = robot_dist / expected_move_time
            
        # 안전을 위해 너무 빠르면 500 mm/s로 제한함
        robot_calculated_velocity = min(robot_calculated_velocity, 500.0)
        
        # 4. 최종 타겟 포즈 (계산된 속도 반영)
        robot_target_final = FanucPoseModel(
            x=target_robot_pose.x, y=target_robot_pose.y, z=target_robot_pose.z,
            w=target_robot_pose.w, p=target_robot_pose.p, r=target_robot_pose.r,
            f=robot_calculated_velocity
        )
        
        # 5. 로봇에게 보낼 신호들 조합
        signals = {
            FanucSignal.IMSP: True, FanucSignal.HOLD: True, FanucSignal.SFSP: True, FanucSignal.ENABLE: True,
            FanucSignal.CYCLE_STOP: False, FanucSignal.START: False, 
            FanucSignal.RSR2: False,       
            FanucSignal.RSR3: True,                 # DO46 Sync 모드 사용
            FanucSignal.TRIGGER_DI43: data_ready,   # "데이터 준비됐어" (Pulse)
            FanucSignal.LOOP_DI44: start_trigger    # "계속 움직여" (Loop/Trigger)
        }
        
        # 6. 최종 24바이트 패킷으로 변환
        packet = robot_target_final.to_struct(current_robot_pose, signals)
        return packet, robot_calculated_velocity

    def execute(self, sequence_data: List[Dict[str, Any]]) -> tuple[bool, str]:
        """
        [통합 실행] 로봇 팔과 서보 모터를 같이 움직이는 핵심 기능임.
        
        [어떻게 동작하나요?]
        1. 시작할 때 스핀들 모터(공전/자전)를 먼저 켜서 계속 돌게 만듦 (Continuous).
        2. 로봇은 '서보가 90도 돌 때 나도 30cm 움직여야지' 하고 속도를 자동으로 계산함.
        3. 매 스텝마다 로봇에게 '준비해' -> '출발해' 신호를 보내서 딱딱 맞춰서 움직임.
        
        [신호 규칙]
        - 로봇이 다 움직이면 DO46 신호를 보내줌 (Rising Edge).
        - 우리는 DI43 신호를 껐다 켜서(Pulse) '다음 동작 시작해'라고 명령함.
        """
        EVENT_BUS.log.message.emit(f"{self._log_prefix} CSV 통합 동기화 제어 시작 (데이터 {len(sequence_data)}건)", "INFO")
        EVENT_BUS.data.sequence_data_loaded.emit(sequence_data)

        robot = self.robot
        servo = self.servo
        
        # =========================================================================
        # 1. 동기화 이벤트 객체 생성
        # =========================================================================
        robot_motion_done_event = threading.Event()     # 로봇: "이동 끝났어" (DO46) - [핵심 동기화 신호]
        
        self._timestamp_robot_done = None
        
        # =========================================================================
        # 2. 콜백 함수 정의 (Robust Edge Detection & Value Normalization)
        # =========================================================================
        
        # [Edge Detection State]
        prev_do46_val = False 

        def _on_robot_motion_done_edge_detect(*args):
            """
            [알림 처리] 로봇이 이동을 완료했을 때(DO46) 호출됨.
            신호가 0에서 1로 켜지는 순간(Rising Edge)을 정확히 포착해서 이벤트를 발생시킴.
            """
            nonlocal prev_do46_val
            self._timestamp_robot_done = time.time()
            
            # 1. 값 추출 (어떤 형태로 들어오든 유연하게 처리)
            raw_val = None
            try:
                if len(args) == 2:
                    raw_val = args[1]
                elif len(args) >= 3:
                    raw_val = args[-1] if isinstance(args[-1], (bool, int, bytes, bytearray)) else args[1]
                
                # 2. 구조체 껍질 벗기기
                for _ in range(3):
                    if hasattr(raw_val, 'contents'): raw_val = raw_val.contents
                    elif hasattr(raw_val, 'data'): raw_val = raw_val.data
                    elif hasattr(raw_val, 'value'): raw_val = raw_val.value
                    else: break
            except:
                raw_val = False

            # 3. 값 판단 (False Positive 방지)
            current_val = False
            try:
                if isinstance(raw_val, (bool, int)):
                    current_val = bool(raw_val)
                elif isinstance(raw_val, (bytes, bytearray)):
                    val_int = int.from_bytes(raw_val, "little")
                    current_val = (val_int != 0)
                else:
                    current_val = False
            except:
                current_val = False

            # Edge Detection (꺼져있다가 켜질 때만!)
            if not prev_do46_val and current_val:
                robot_motion_done_event.set()
                
            prev_do46_val = current_val

        # =========================================================================
        # 3. 알림 구독 (Subscribe)
        # =========================================================================
        handle_motion = robot.register_robot_motion_done_callback(_on_robot_motion_done_edge_detect)
        
        # [Robust Init] DO46 초기 상태 읽기
        try:
            prev_do46_val = robot.read_complete_signal() # or read_robot_motion_done_signal alias
        except:
            prev_do46_val = False

        try:
            # 초기화: 서보 축 상태 확인 및 에러 체크
            for axis in ServoAxis:
                servo.set_servo_state(axis, True)
                if servo.has_servo_error(axis):
                    raise RuntimeError(f"서보 축({axis.name}) 에러 감지됨. 작업 중단함.")

            # 로봇 상태 확인
            robot.validate_robot_ready()
            
            # [Explicit Safety] Loop 신호(DI44)는 패킷(Packet) 내의 비트로 제어됨.
            # 초기화 시점에 별도 디지털 출력으로 켜지 않고, 첫 패킷 전송 시 켜짐.
            # robot.write_digital_signal(FanucSignal.LOOP_DI44, True)

            # 상태 변수 초기화
            current_pose = FanucPoseModel(x=0, y=0, z=0, w=0, p=0, r=0)
            previous_robot_velocity = 0.0
            
            # 턴테이블 초기 각도 읽어옴 (안전하게)
            try:
                tt_fb = servo.read_current_servo_motion(ServoAxis.TURNTABLE)
                current_turntable_angle = tt_fb['position']
            except:
                current_turntable_angle = 0.0
            
            total_steps = len(sequence_data)
            
            # [Step 0: 서보 모터 일괄 기동]
            # ---------------------------------------------------------------------
            # 첫 번째 스텝의 속도 데이터를 기준으로 공전/자전 모터를 먼저 돌리기 시작함.
            # 이 모터들은 작업 내내 계속 돔 (Continuous).
            if sequence_data:
                first_row = sequence_data[0]
                
                # CSV 첫 행의 값을 전체 시퀀스의 '속도'로 사용함.
                m1_rpm = first_row.get(KEY_TOOL_REV_RPM, 0.0) # 공전 속도
                m2_rpm = first_row.get(KEY_TOOL_ROT_RPM, 0.0) # 자전 속도
                m3_deg_per_s = first_row.get(KEY_TURNTABLE_FEED_RATE, 0.0) # 턴테이블 속도
                m3_pos = first_row.get(KEY_TURNTABLE_DEG, 0.0) 
                
                EVENT_BUS.log.message.emit(f"{self._log_prefix} 서보 모터 가동 시작: Rev={m1_rpm}RPM, Rot={m2_rpm}RPM, TT_Vel={m3_deg_per_s}", "INFO")
                
                # 공전 (Axis 1) 켜기
                if m1_rpm is not None:
                    servo.move_velocity(ServoAxis.TOOL_REVOLUTION, m1_rpm)
                
                # 자전 (Axis 2) 켜기
                if m2_rpm is not None:
                    servo.move_velocity(ServoAxis.TOOL_ROTATION, m2_rpm)

                time.sleep(0.5) # 모터가 켜지고 안정화될 때까지 잠시 대기

            # =========================================================================
            # [Step 1: 로봇 시동 (Immediate Start)]
            # =========================================================================
            if sequence_data:
                row = sequence_data[0]
                EVENT_BUS.data.progress_updated.emit(1, total_steps, TaskStatus.PROCESSING)

                # (A) 데이터 파싱 & 초기화
                target_pose = FanucPoseModel.from_dict(row)
                pose_turntable = ServoPoseModel.create_for_axis(row, KEY_TURNTABLE_DEG)
                
                # (C) 로봇 데이터 전송
                # -------------------------------------------------------------
                # 1. 패킷 생성 (DI43=False) -> Data Load
                packet_load, velocity = self._calculate_and_pack(
                    current_pose, target_pose, 
                    current_turntable_angle, pose_turntable.angle, m3_deg_per_s,
                    0.0, 
                    data_ready=False,   
                    start_trigger=True 
                )
                robot.write_command_packet(packet_load)
                
                # [중요] 이벤트 클리어 (초기화)
                robot_motion_done_event.clear()

                # 서보 이동 (Step 1)
                servo.move_turntable_atomic(ServoAxis.TURNTABLE, pose_turntable.angle, m3_deg_per_s)
                
                # 2. 트리거 패킷 전송 (DI43=True) -> Start!
                #    (주의: 데이터 패킷과 동일하되 DI43 비트만 킴)
                time.sleep(0.25)  # [Legacy Timing] 0.05 -> 0.25
                packet_trigger, _ = self._calculate_and_pack(
                    current_pose, target_pose, 
                    current_turntable_angle, pose_turntable.angle, m3_deg_per_s,
                    0.0, 
                    data_ready=True,   # DI43 ON
                    start_trigger=True 
                )
                robot.write_command_packet(packet_trigger)
                
                EVENT_BUS.log.message.emit(f"{self._log_prefix} [Init] Step 1 시작됨 (자동 트리거).", "DEBUG")
                
                # 현재 위치 갱신
                current_pose = target_pose
                current_turntable_angle = pose_turntable.angle
                previous_robot_velocity = velocity 
                
            # =========================================================================
            # [Step 2+: 파이프라인 루프 (Pipeline Loop)]
            # =========================================================================
            for i in range(1, total_steps):
                time.sleep(0.3) # [Legacy Timing] Loop Start Buffer
                step_idx = i + 1
                row = sequence_data[i]
                
                # (0) 펄스 리셋 (DI43=False) - 별도 패킷 없이 다음 로드 패킷에서 처리됨
                # robot.write_digital_signal(FanucSignal.TRIGGER_DI43, False)

                # (1) 이전 동작 완료 확인 (DO46)
                if not self._wait_event_with_safety(robot_motion_done_event, timeout=self.MOVE_TIMEOUT):
                    if self._is_interrupted(): raise InterruptedError("사용자에 의해 중단됨.")
                    raise TimeoutError(f"[Step {step_idx}] 로봇 이동 대기(DO46) 시간 초과됨.")
                
                robot_motion_done_event.clear() 

                # 2. 데이터 미리 채우기 (DI43=False)
                # -----------------------------------------------------------------
                # 턴테이블 속도: 매 스텝 설정 OR 고정? (현재는 CSV 첫 줄 m3_deg_per_s 사용 권장 or Row별)
                # 일단 안전하게 Fixed Value(m3_deg_per_s) 사용 (0115_retest 철학)
                
                target_pose = FanucPoseModel.from_dict(row)
                pose_turntable = ServoPoseModel.create_for_axis(row, KEY_TURNTABLE_DEG)
                
                packet_load, velocity = self._calculate_and_pack(
                    current_pose, target_pose, 
                    current_turntable_angle, pose_turntable.angle, m3_deg_per_s,
                    previous_robot_velocity, 
                    data_ready=False,   
                    start_trigger=True  # Loop ON
                )
                robot.write_command_packet(packet_load)

                # 진행 상황 UI 업데이트 (인덱스 보정)
                EVENT_BUS.data.progress_updated.emit(i, total_steps, TaskStatus.COMPLETED)     # 이전 스텝 완료
                EVENT_BUS.data.progress_updated.emit(step_idx, total_steps, TaskStatus.PROCESSING) # 현재 스텝 진행

                # -----------------------------------------------------------------
                # 3. 다음 동작 트리거 (DI43 High)
                # -----------------------------------------------------------------
                
                # (C) 로봇 트리거 (Packet DI43=True)
                # -----------------------------------------------------------------
                
                # 서보 이동 (Step 1)
                servo.move_turntable_atomic(ServoAxis.TURNTABLE, pose_turntable.angle, m3_deg_per_s)
                
                # 2. 트리거 패킷 전송 (DI43=True) -> Start!
                #    (Load 패킷 후 짧은 대기 -> Trigger 패킷)
                time.sleep(0.3) # [Legacy Timing] 0.05 -> 0.3
                packet_trigger, _ = self._calculate_and_pack(
                    current_pose, target_pose, 
                    current_turntable_angle, pose_turntable.angle, m3_deg_per_s,
                    previous_robot_velocity, 
                    data_ready=True,   # DI43 ON!
                    start_trigger=True 
                )
                robot.write_command_packet(packet_trigger)
                
                EVENT_BUS.log.message.emit(f"{self._log_prefix}  -> [Step {step_idx}] 출발! (DI43 Trigger)", "DEBUG")
                
                # (F) 위치 정보 갱신
                current_pose = target_pose
                current_turntable_angle = pose_turntable.angle
                previous_robot_velocity = velocity

            # [종료 대기]
            EVENT_BUS.log.message.emit(f"{self._log_prefix} 마지막 이동 완료 대기 중...", "INFO")
            if not self._wait_event_with_safety(robot_motion_done_event, timeout=self.MOVE_TIMEOUT):
                EVENT_BUS.log.message.emit(f"{self._log_prefix} 마지막 로봇 이동 대기 시간 초과됨 (무시하고 종료).", "WARNING")
            
            # [Finish Protocol] Zero Payload 전송
            # 로봇 프로그램을 깔끔하게 종료시키기 위해 '0'으로 채워진 패킷을 한 번 보냄
            EVENT_BUS.log.message.emit(f"{self._log_prefix} 종료 프로토콜 실행 (Zero Payload 전송)...", "DEBUG")
            
            # 1. DI44(Loop) 끄기 (Packet으로 처리됨)
            # robot.write_digital_signal(FanucSignal.LOOP_DI44, False)
            # robot.write_digital_signal(FanucSignal.TRIGGER_DI43, False)
            # time.sleep(0.1)
            
            # 2. Zero Packet 전송
            time.sleep(0.3) # [Legacy Timing] Finish Buffer
            signals_finish = {
                FanucSignal.IMSP: True, FanucSignal.HOLD: True, FanucSignal.SFSP: True, FanucSignal.ENABLE: True,
                FanucSignal.RSR3: True,
                FanucSignal.TRIGGER_DI43: False, # Trigger OFF
                FanucSignal.LOOP_DI44: False     # Loop OFF
            }
            zero_packet = FanucPoseModel.create_signal_only_packet(signals_finish)
            robot.write_command_packet(zero_packet)

            # 최종 완료 방송
            EVENT_BUS.data.progress_updated.emit(total_steps, total_steps, TaskStatus.COMPLETED)
            return True, f"{self._log_prefix} 모든 작업이 성공적으로 완료됨."

        except InterruptedError as e:
            EVENT_BUS.log.message.emit(f"{self._log_prefix} 사용자가 중단했음. 장비 정지 신호 보냄...", "WARNING")
            try: robot.set_emergency_stop()
            except: pass
            # packet-based stop handles this implicitly
            # try: robot.write_digital_signal(FanucSignal.LOOP_DI44, False)
            # except: pass
            try: servo.request_immediate_stop()
            except: pass
            return False, str(e)

        except Exception as e:
            EVENT_BUS.log.message.emit(f"{self._log_prefix} 오류 발생함: {e}. 장비 정지 시도...", "ERROR")
            try: robot.set_emergency_stop() 
            except: pass
            try: servo.request_immediate_stop() 
            except: pass
            return False, f"{self._log_prefix} 오류 발생: {e}"
            
        finally:
            EVENT_BUS.data.sequence_job_finished.emit()
            try: robot.remove_notification(handle_motion)
            except: pass
            
            try:
                # [Packet Based Cleanup] 모든 신호 OFF 패킷 전송
                # robot.write_digital_signal(FanucSignal.TRIGGER_DI43, False)
                # robot.write_digital_signal(FanucSignal.LOOP_DI44, False)
                
                cleanup_signals = {
                    FanucSignal.IMSP: True, FanucSignal.HOLD: True, FanucSignal.SFSP: True, FanucSignal.ENABLE: True,
                    FanucSignal.TRIGGER_DI43: False,
                    FanucSignal.LOOP_DI44: False
                }
                cleanup_packet = FanucPoseModel.create_signal_only_packet(cleanup_signals)
                robot.write_command_packet(cleanup_packet)

                servo.home_all_safely(timeout=30.0)
                EVENT_BUS.log.message.emit(f"{self._log_prefix} Homing 수행 완료.", "DEBUG")
            except Exception as e:
                EVENT_BUS.log.message.emit(f"{self._log_prefix} 클린업 중 오류: {e}", "WARNING")

    def execute_deprecated(self, sequence_data: List[Dict[str, Any]]) -> tuple[bool, str]:
        """
        [DEPRECATED] 
        과거 스텝별 동기화 로직은 더 이상 사용하지 않음.
        (Continuous Motor Mode로 대체됨)
        """
        return False, "This method is deprecated. Use execute() instead."

    def _wait_event_with_safety(self, event: threading.Event, timeout: float) -> bool:
        """
        [안전 대기] 이벤트를 기다리는 동안에도 '정지 버튼'이 눌렸는지 계속 감시함.
        
        원리:
        그냥 wait(60초) 해버리면 60초 동안 프로그램이 멈춰서 정지 버튼이 안 먹힘.
        그래서 0.1초씩 쪼개서 600번 기다리는 방식을 사용함.
        
        Returns: 이벤트가 오면 True, 시간 초과나 정지면 False
        """
        start = time.time()
        while time.time() - start < timeout:
            # 1. 사용자가 STOP 버튼을 눌렀는지 체크 (안전)
            if (t := QThread.currentThread()) and t.isInterruptionRequested():
                return False
            
            # 2. 0.1초만 잠깐 대기
            if event.wait(0.1):
                return True # 이벤트가 발생했으면 즉시 성공!
                
        return False # 결국 시간 초과됨
        
    def _is_interrupted(self) -> bool:
        return bool((thread := QThread.currentThread()) and thread.isInterruptionRequested())

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

