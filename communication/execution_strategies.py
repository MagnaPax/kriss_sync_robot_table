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
    """
    [로봇 단독 실행 전략]
    서보 모터 없이 'FANUC 로봇 팔'만 혼자서 움직이는 모드이다.
    복잡한 턴테이블 동기화 없이 로봇만 테스트할 때 사용한다.
    
    [핵심 기술: Packet-Only SSOT]
    - 예전처럼 신호를 하나하나 껐다 켰다(Bit-banging) 하지 않는다.
    - "이번엔 여기로 가고 신호는 이렇게 해!" 하고 24바이트짜리 편지(Packet) 한 통을 딱 보내면 끝이다.
    """

    # 펄스 신호 폭 조절 (너무 빠르면 PLC가 못 알아들으니까 조금 기다려준다)
    PRE_TRIGGER_DELAY_S = 0.05      # '데이터 장전' 하고 '발사' 누르기 전 대기 시간
    TRIGGER_HOLD_S = 0.05           # '발사' 버튼 누르고 나서 떼기 전까지 유지 시간


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

    # -------------------------------------------------------------------------
    # Helper Methods (도우미 함수들)
    # -------------------------------------------------------------------------
    def _pack_simple_motion(
        self,
        current_pose: FanucPoseModel,
        target_pose: FanucPoseModel,
        *,
        is_trigger: bool,
        is_loop_active: bool,
    ) -> Any:
        """
        [패킷 포장 도우미]
        로봇에게 보낼 편지(Packet) 내용을 작성한다.
        턴테이블 계산 같은 복잡한 건 빼고, 로봇 이동 명령만 깔끔하게 담는다.
        """
        signals = {
            FanucSignal.IMSP: True,
            FanucSignal.HOLD: True,
            FanucSignal.SFSP: True,
            FanucSignal.ENABLE: True,
            FanucSignal.RSR3: True,                   # "DO46 신호 기다릴게" 모드 켜기
            FanucSignal.TRIGGER_DI43: is_trigger,     # "지금 출발해!" 신호 (Pulse)
            FanucSignal.LOOP_DI44: is_loop_active,    # "계속 움직여" 신호 (Loop)
        }
        # 목표 위치와 신호를 합쳐서 하나의 구조체로 만든다.
        return target_pose.to_struct(current_pose, signals)

    def _apply_feed_override_safe(self, pose: FanucPoseModel) -> FanucPoseModel:
        """
        [안전 속도 적용]
        사용자가 화면에서 "속도 줄여!"라고 `override_feed_rate`를 설정했으면,
        CSV 파일에 빠르다고 적혀 있어도 사용자가 설정한 느린 속도로 덮어쓴다.
        (단, CSV가 더 느리면 CSV 속도를 따른다. 안전 제일!)
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
        [한 발짝 이동 명령]
        한 번의 이동(Step)을 위해 3단계에 걸쳐서 패킷을 쏜다.
        
        순서:
        1. 장전 (Load): "이 데이터로 갈 준비 해" (DI43=False)
        2. 조준 (Wait): PLC가 데이터를 읽을 때까지 잠깐 기다린다.
        3. 발사 (Trigger): "가라!" (DI43=True)
        4. 유지 (Hold): 신호가 확실히 들어갈 때까지 누르고 있는다.
        5. 복귀 (Reset): "신호 끈다" (DI43=False) -> 그래야 다음에 또 켤 수 있다.
        """
        # 1) Load (장전)
        try:
            packet_load = self._pack_simple_motion(
                current_pose, target_pose,
                is_trigger=False, is_loop_active=loop_active
            )
            robot.write_command_packet(packet_load)
        except Exception as e:
            EVENT_BUS.log.message.emit(f"{self._log_prefix} 장전(LOAD) 패킷 전송 실패: {e}", "ERROR")
            raise

        # 2) PLC가 스캔할 시간을 준다 (0.05초)
        time.sleep(self.PRE_TRIGGER_DELAY_S)

        # 3) Trigger (발사!) - 그 전에 '도착' 깃발을 내린다.
        done_event.clear()
        try:
            packet_trigger = self._pack_simple_motion(
                current_pose, target_pose,
                is_trigger=True, is_loop_active=loop_active
            )
            robot.write_command_packet(packet_trigger)
        except Exception as e:
            EVENT_BUS.log.message.emit(f"{self._log_prefix} 발사(TRIGGER) 패킷 전송 실패: {e}", "ERROR")
            raise

        # 4) 신호 유지
        time.sleep(self.TRIGGER_HOLD_S)

        # 5) Reset (신호 끄기)
        try:
            packet_reset = self._pack_simple_motion(
                current_pose, target_pose,
                is_trigger=False, is_loop_active=loop_active
            )
            robot.write_command_packet(packet_reset)
        except Exception as e:
            EVENT_BUS.log.message.emit(f"{self._log_prefix} 복귀(RESET) 패킷 전송 실패: {e}", "ERROR")
            raise

    # -------------------------------------------------------------------------
    # Main Execution (실행부)
    # -------------------------------------------------------------------------
    def execute(self, sequence_data: List[Dict[str, Any]]) -> tuple[bool, str]:
        """
        [실행 메인 함수]
        로봇 단독 제어를 시작한다.
        
        [프로토콜 규칙]
        - DI44: 켜져 있으면 "계속 일해", 꺼지면 "집에 가"
        - DI43: 한번 껐다 켜면(Pulse) "다음 칸으로 가"
        - DO46: 로봇이 도착하면 켜짐 (Rising Edge)
        """
        if not sequence_data:
            return True, "데이터가 텅 비어있습니다."

        EVENT_BUS.log.message.emit(f"{self._log_prefix} 로봇 단독 모드 시작 (데이터 {len(sequence_data)}건)", "INFO")
        EVENT_BUS.data.sequence_data_loaded.emit(sequence_data)

        robot = self.robot
        total_steps = len(sequence_data)

        # 로봇이 도착했는지 알려주는 이벤트를 만든다.
        robot_motion_done_event = threading.Event()

        # [감시자] DO46 신호가 꺼졌다가 켜지는지 지켜보는 로직
        prev_do46_val = False

        def _on_motion_done_edge_detect(*args: Any):
            nonlocal prev_do46_val

            # (데이터 껍질 까기 - 복잡하니 넘어감)
            raw_val: Any = None
            try:
                if len(args) == 2:
                    raw_val = args[1]
                elif len(args) >= 3:
                    raw_val = args[-1] if isinstance(args[-1], (bool, int, bytes, bytearray)) else args[1]

                for _ in range(3):
                    if hasattr(raw_val, "contents"): raw_val = raw_val.contents
                    elif hasattr(raw_val, "data"): raw_val = raw_val.data
                    elif hasattr(raw_val, "value"): raw_val = raw_val.value
                    else: break
            except Exception:
                raw_val = False

            # (값 확인)
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

            # 핵심: 0에서 1로 변했으면(Rising Edge) 도착한 것이다!
            if (not prev_do46_val) and current_val:
                robot_motion_done_event.set()

            prev_do46_val = current_val

        # ---- 시작하기 전에 현재 DO46 값을 한번 읽어둔다.
        try:
            prev_do46_val = robot.read_complete_signal()
        except Exception:
            prev_do46_val = False

        # 감시자를 등록한다. 실패하면 바로 멈춘다.
        try:
            handle_motion = robot.register_robot_motion_done_callback(_on_motion_done_edge_detect)
        except Exception as e:
            EVENT_BUS.log.message.emit(f"{self._log_prefix} 감시자 등록 실패로 작업 중단: {e}", "ERROR")
            # [안전] 혹시 모르니 신호를 싹 다 끄고 종료한다.
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
            # 로봇 상태 점검
            robot.validate_robot_ready()

            # 로봇 움직임 시작
            EVENT_BUS.control.robot_moving_status_changed.emit({'is_robot_moving': True})

            # [Step 1] 첫 번째 위치로 이동!
            current_pose = robot.read_current_world_pose()
            target_pose = FanucPoseModel.from_dict(sequence_data[0])
            target_pose = self._apply_feed_override_safe(target_pose)

            EVENT_BUS.data.progress_updated.emit(1, total_steps, TaskStatus.PROCESSING)

            # 첫 발사! (Loop 신호도 같이 켠다)
            self._send_step_packets_packet_only(
                robot, current_pose, target_pose,
                loop_active=True,
                done_event=robot_motion_done_event,
            )
            current_pose = target_pose

            # [Step 2 ~ 끝] 반복 이동
            for i in range(1, total_steps):
                step_idx = i + 1

                # (1) 이전 이동이 끝날 때까지 기다린다 (DO46)
                if not self._wait_event_with_safety(robot_motion_done_event, timeout=self.move_timeout):
                    if self._is_interrupted():
                        raise InterruptedError("사용자가 작업을 중단했습니다.")
                    raise TimeoutError(f"[Step {step_idx}] 로봇이 안 와서 에러남 (시간초과)")

                # 도착했으니 깃발 내린다.
                robot_motion_done_event.clear()

                # (2) 다음 목표 준비
                target_pose = FanucPoseModel.from_dict(sequence_data[i])
                target_pose = self._apply_feed_override_safe(target_pose)

                # (3) 발사! (장전 -> 발사 -> 복귀)
                self._send_step_packets_packet_only(
                    robot, current_pose, target_pose,
                    loop_active=True,
                    done_event=robot_motion_done_event,
                )

                EVENT_BUS.data.progress_updated.emit(i, total_steps, TaskStatus.COMPLETED)
                EVENT_BUS.data.progress_updated.emit(step_idx, total_steps, TaskStatus.PROCESSING)
                EVENT_BUS.log.message.emit(f"{self._log_prefix}  -> [Step {step_idx}] 출발 성공!", "DEBUG")

                current_pose = target_pose

            # [마무리] 마지막 이동이 끝날 때까지 기다린다.
            EVENT_BUS.log.message.emit(f"{self._log_prefix} 마지막 이동 완료 대기 중...", "INFO")
            if not self._wait_event_with_safety(robot_motion_done_event, timeout=self.move_timeout):
                EVENT_BUS.log.message.emit(f"{self._log_prefix} 마지막 이동 대기 시간 초과됨 (무시하고 종료)", "WARNING")

            # [종료 프로토콜]Loop 끄고, Trigger 끄고, 0으로 채운 패킷을 보낸다.
            EVENT_BUS.log.message.emit(f"{self._log_prefix} 종료 패킷 전송 중...", "DEBUG")
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
            return True, "모든 작업이 성공적으로 끝났습니다."

        except InterruptedError as e:
            EVENT_BUS.log.message.emit(f"{self._log_prefix} 작업 중단됨: {e}", "WARNING")
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
            # 시퀀스 종료
            EVENT_BUS.data.sequence_job_finished.emit()
            # 로봇 움직임 종료
            EVENT_BUS.control.robot_moving_status_changed.emit({'is_robot_moving': False})
            try:
                if handle_motion:
                    robot.remove_notification(handle_motion)
            except Exception:
                pass

            # 마지막으로 확실하게 신호 끄기 (Clean-up)
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
        """[안전 대기] 기다리는 동안 정지 버튼 눌렸는지 계속 확인한다."""
        start = time.time()
        while time.time() - start < timeout:
            if (t := QThread.currentThread()) and t.isInterruptionRequested():
                return False
            if event.wait(0.1):
                return True
        return False

    def _is_interrupted(self) -> bool:
        """누가 멈추라고 했는지 확인하는 함수이다."""
        return bool((thread := QThread.currentThread()) and thread.isInterruptionRequested())

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

        # 처리할 전체 시퀀스 데이터 방송 (UI 갱신용)
        EVENT_BUS.data.sequence_data_loaded.emit(sequence_data)

        # 설정값 최신화
        self.busy_timeout = SETTINGS.servo.busy_timeout
        self.move_timeout = SETTINGS.servo.move_timeout

        adapter = self.servo
        total_steps = len(sequence_data)
        EVENT_BUS.log.message.emit(f"{self._log_prefix} 서보 시퀀스 시작 (총 {total_steps}건)", "INFO")
        
        # 1. 초기화 (전원 켜기)
        for axis in ServoAxis:
            adapter.set_servo_state(axis, True)
            # [안전 점검] 혹시 에러가 떠있으면 시작 안 함.
            if adapter.has_servo_error(axis):
                raise RuntimeError(f"서보 축({axis.name})에 에러가 켜져 있어서 작업을 중단합니다.")

        try:
            # 2. 실행 루프 (하나씩 실행)
            for step_idx, row in enumerate(sequence_data, start=1):

                # (A) 사용자가 멈춤 버튼 눌렀는지 확인
                if self._is_interrupted():
                    raise InterruptedError("사용자가 작업을 중단시켰습니다.")

                # (B) UI 진행률 업데이트
                EVENT_BUS.data.progress_updated.emit(step_idx, total_steps, TaskStatus.PROCESSING)
                EVENT_BUS.log.message.emit(f"{self._log_prefix} {step_idx}/{total_steps} 진행 중...", "DEBUG")

                # (Pre-Check) 턴테이블을 움직여야 하는지 판단
                pose_turntable = ServoPoseModel.create_for_axis(row, KEY_TURNTABLE_DEG)
                current_turntable_pos = adapter.read_current_servo_motion(ServoAxis.TURNTABLE)['position']
                
                should_move_turntable = True

                # [Type Hinting] 변수 초기화
                pose_revolution = None
                pose_rotation = None

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

                # (C) 명령 내리기
                seq_id = row.get('id', step_idx)
                
                # 로그에 보기 좋게 출력
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
        [핵심 계산 함수]
        로봇이 얼마나 빨리 움직여야 턴테이블과 딱 맞춰서 도착할지 계산하고,
        PLC에게 보낼 '명령서(Packet)'를 만드는 함수이다.
        
        [동작 원리]
        1. 턴테이블이 목표 각도까지 가는 데 몇 초 걸리는지 계산한다. (시간 = 거리 / 속도)
        2. 로봇이 목표 위치까지 가는 데 거리가 얼마인지 계산한다.
        3. "로봇아, 너도 이 시간 안에 저기까지 가야 해" 라고 명령하기 위해 로봇 속도를 역산한다. (속도 = 거리 / 시간)
        
        Returns: (PLC로 보낼 패킷 데이터, 계산된 로봇 속도)
        """
        # 1. 턴테이블이 이동하는 데 걸리는 시간 계산
        # (목표 각도 - 현재 각도) / 속도 = 걸리는 시간
        tt_delta = abs(target_turntable_angle - current_turntable_angle)
        expected_move_time = tt_delta / target_turntable_velocity if target_turntable_velocity > 0 else 0.0
        
        # 2. 로봇이 이동해야 할 거리 계산 (직선 거리 mm)
        robot_dist, _ = current_robot_pose.distance_to(target_robot_pose)
        
        # 3. 로봇 속도 계산 (Time Stretching)
        if robot_dist < 0.001: 
            # 로봇이 조금도 안 움직여도 되면 속도는 0이다.
            robot_calculated_velocity = 0.0
        elif expected_move_time < 0.001:
            # 턴테이블은 가만히 있고 로봇만 움직여야 할 때
            # 이전 속도를 그대로 쓰거나, 기본값(100)으로 움직인다.
            robot_calculated_velocity = previous_robot_velocity if previous_robot_velocity > 0 else 100.0
        else:
            # 시간 = 거리 / 속도 공식을 뒤집어서 -> 속도 = 거리 / 시간
            robot_calculated_velocity = robot_dist / expected_move_time
            
        # 안전장치: 아무리 빨라야 한다고 해도 500mm/s 이상은 위험하니 제한한다.
        robot_calculated_velocity = min(robot_calculated_velocity, 500.0)
        
        # 4. 계산된 속도를 포함해서 최종 목표 지점 데이터를 만든다.
        robot_target_final = FanucPoseModel(
            x=target_robot_pose.x, y=target_robot_pose.y, z=target_robot_pose.z,
            w=target_robot_pose.w, p=target_robot_pose.p, r=target_robot_pose.r,
            f=robot_calculated_velocity
        )
        
        # 5. 로봇에게 보낼 신호 깃발들을 세팅한다.
        signals = {
            FanucSignal.IMSP: True, FanucSignal.HOLD: True, FanucSignal.SFSP: True, FanucSignal.ENABLE: True,
            FanucSignal.CYCLE_STOP: False, FanucSignal.START: False, 
            FanucSignal.RSR2: False,       
            FanucSignal.RSR3: True,                 # "DO46 신호 기다릴게" 모드 켜기
            FanucSignal.TRIGGER_DI43: data_ready,   # "데이터 가져가세요" (Pulse 신호)
            FanucSignal.LOOP_DI44: start_trigger    # "멈추지 말고 계속해" (Loop 신호)
        }
        
        # 6. 이 모든 정보를 24바이트짜리 패킷 하나로 꽉꽉 눌러 담아서 반환한다.
        packet = robot_target_final.to_struct(current_robot_pose, signals)
        return packet, robot_calculated_velocity

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
        EVENT_BUS.log.message.emit(f"{self._log_prefix} CSV 통합 동기화 제어 시작 (데이터 {len(sequence_data)}건)", "INFO")
        EVENT_BUS.data.sequence_data_loaded.emit(sequence_data)

        robot = self.robot
        servo = self.servo
        
        # =========================================================================
        # 1. 로봇이 도착했는지 확인하기 위한 '이벤트(깃발)' 만들기
        # =========================================================================
        robot_motion_done_event = threading.Event()     # "로봇 도착함(DO46)" 신호를 받으면 깃발을 든다.
        
        self._timestamp_robot_done = None
        
        # =========================================================================
        # 2. 로봇의 도착 신호(DO46)를 감지하는 감시자 함수 정의
        # =========================================================================
        
        # 이전 신호 상태를 기억하기 위한 변수 (0이었다가 1이 될 때만 감지하려고)
        prev_do46_val = False 

        def _on_robot_motion_done_edge_detect(*args: Any):
            """
            [알림 콜백] 
            PLC가 "DO46 신호 바뀌었어!" 하고 알려주면 이 함수가 실행된다.
            꺼져있다가 켜지는 순간(Rising Edge)을 포착해서 '이벤트 깃발'을 든다.
            """
            nonlocal prev_do46_val
            self._timestamp_robot_done = time.time()
            
            # (복잡한 데이터 포장지를 벗겨내고 알맹이 값만 꺼내는 과정)
            raw_val: Any = None
            try:
                if len(args) == 2:
                    raw_val = args[1]
                elif len(args) >= 3:
                    raw_val = args[-1] if isinstance(args[-1], (bool, int, bytes, bytearray)) else args[1]
                
                for _ in range(3):
                    if hasattr(raw_val, 'contents'): raw_val = raw_val.contents
                    elif hasattr(raw_val, 'data'): raw_val = raw_val.data
                    elif hasattr(raw_val, 'value'): raw_val = raw_val.value
                    else: break
            except:
                raw_val = False

            # (꺼낸 값을 True/False로 확실하게 변환)
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

            # [핵심] 전에는 꺼져있었는데(False), 지금 켜졌다면(True) -> 도착한 것이다!
            if not prev_do46_val and current_val:
                robot_motion_done_event.set()
                
            prev_do46_val = current_val

        # =========================================================================
        # 3. 감시자 등록 & 초기화
        # =========================================================================
        # "앞으로 DO46 신호 바뀌면 저한테 알려주세요" 하고 등록한다.
        handle_motion = robot.register_robot_motion_done_callback(_on_robot_motion_done_edge_detect)
        
        # 혹시 처음에 이미 신호가 켜져있는지 확인해둔다.
        try:
            prev_do46_val = robot.read_complete_signal() 
        except:
            prev_do46_val = False

        try:
            # 서보 모터들에 문제없나 점검하고 전원을 넣는다.
            for axis in ServoAxis:
                servo.set_servo_state(axis, True)
                if servo.has_servo_error(axis):
                    raise RuntimeError(f"서보 축({axis.name})에 에러가 있어서 시작할 수 없음.")

            # 로봇도 문제없나 점검한다.
            robot.validate_robot_ready()
            
            # 시작할 때 필요한 변수들을 초기화한다.
            current_pose = FanucPoseModel(x=0, y=0, z=0, w=0, p=0, r=0)
            previous_robot_velocity = 0.0
            
            # 턴테이블이 지금 몇 도에 있는지 확인한다.
            try:
                tt_fb = servo.read_current_servo_motion(ServoAxis.TURNTABLE)
                current_turntable_angle = tt_fb['position']
            except:
                current_turntable_angle = 0.0
            
            total_steps = len(sequence_data)
            
            # [Step 0: 서보 모터(드릴) 시동]
            # ---------------------------------------------------------------------
            # 작업 내내 계속 돌아가야 하는 모터들(공전/자전)을 먼저 켠다.
            m3_deg_per_s = 0.0 # 초기화
            if sequence_data:
                first_row = sequence_data[0]
                
                m1_rpm = first_row.get(KEY_TOOL_REV_RPM, 0.0)             # 공전(뺑뺑이) 속도
                m2_rpm = first_row.get(KEY_TOOL_ROT_RPM, 0.0)             # 자전(드릴) 속도
                m3_deg_per_s = first_row.get(KEY_TURNTABLE_FEED_RATE, 0.0)# 턴테이블 속도
                _m3_pos = first_row.get(KEY_TURNTABLE_DEG, 0.0) 
                
                EVENT_BUS.log.message.emit(f"{self._log_prefix} 서보 모터 예열 시작: Rev={m1_rpm}RPM, Rot={m2_rpm}RPM", "INFO")
                
                # 공전 모터 켜기
                if m1_rpm is not None:
                    servo.move_velocity(ServoAxis.TOOL_REVOLUTION, m1_rpm)
                
                # 자전 모터 켜기
                if m2_rpm is not None:
                    servo.move_velocity(ServoAxis.TOOL_ROTATION, m2_rpm)

                time.sleep(0.5) # 모터가 웅~ 하고 켜질 때까지 잠깐 기다려준다.

            # =========================================================================
            # [Step 1: 첫 번째 이동 시작!]
            # =========================================================================
            if sequence_data:
                row = sequence_data[0]
                EVENT_BUS.data.progress_updated.emit(1, total_steps, TaskStatus.PROCESSING)

                # 첫 줄 데이터를 읽어서 목표 위치를 설정한다.
                target_pose = FanucPoseModel.from_dict(row)
                pose_turntable = ServoPoseModel.create_for_axis(row, KEY_TURNTABLE_DEG)
                
                # [로봇 명령 전송]
                # -------------------------------------------------------------
                # 1. [Load] "이 데이터로 갈 준비 해" (아직 출발은 아님, Trigger=False)
                packet_load, velocity = self._calculate_and_pack(
                    current_pose, target_pose, 
                    current_turntable_angle, pose_turntable.angle, m3_deg_per_s,
                    0.0, 
                    data_ready=False,   
                    start_trigger=True 
                )
                robot.write_command_packet(packet_load)
                
                # 깃발을 내리고 기다릴 준비를 한다.
                robot_motion_done_event.clear()

                # 서보(턴테이블)도 출발시킨다!
                servo.move_turntable_atomic(ServoAxis.TURNTABLE, pose_turntable.angle, m3_deg_per_s)
                
                # 2. [Trigger] "자, 이제 진짜 출발!" (Trigger=True)
                #    (Load 명령을 보내고 아주 잠깐 숨을 고른 뒤에 출발 신호를 보낸다)
                time.sleep(0.25)
                packet_trigger, _ = self._calculate_and_pack(
                    current_pose, target_pose, 
                    current_turntable_angle, pose_turntable.angle, m3_deg_per_s,
                    0.0, 
                    data_ready=True,   # 여기가 핵심! 트리거 ON!
                    start_trigger=True 
                )
                robot.write_command_packet(packet_trigger)
                
                EVENT_BUS.log.message.emit(f"{self._log_prefix} [Step 1] 첫 번째 동작 시작!", "DEBUG")
                
                # 내비게이션 현재 위치 업데이트
                current_pose = target_pose
                current_turntable_angle = pose_turntable.angle
                previous_robot_velocity = velocity 
                
            # =========================================================================
            # [Step 2 ~ 끝: 연속 동작 루프]
            # =========================================================================
            for i in range(1, total_steps):
                time.sleep(0.3) # 다음 동작 넘어가기 전 안전하게 숨 고르기
                step_idx = i + 1
                row = sequence_data[i]
                
                # (1) 로봇이 "나 도착했어(DO46)" 라고 할 때까지 기다린다.
                if not self._wait_event_with_safety(robot_motion_done_event, timeout=self.move_timeout):
                    if self._is_interrupted(): raise InterruptedError("사용자가 멈춤 버튼을 눌렀음.")
                    raise TimeoutError(f"[Step {step_idx}] 로봇이 너무 오래 걸려서 에러남 (타임아웃).")
                
                # 도착했으니 깃발을 내리고 다음 기다림을 준비한다.
                robot_motion_done_event.clear() 

                # (2) 다음 목표 데이터를 준비 미리 로봇에게 보내둔다 (Load)
                target_pose = FanucPoseModel.from_dict(row)
                pose_turntable = ServoPoseModel.create_for_axis(row, KEY_TURNTABLE_DEG)
                
                packet_load, velocity = self._calculate_and_pack(
                    current_pose, target_pose, 
                    current_turntable_angle, pose_turntable.angle, m3_deg_per_s,
                    previous_robot_velocity, 
                    data_ready=False,   # 아직 출발 신호는 끈 상태로 데이터만 전송
                    start_trigger=True  # Loop 모드 유지
                )
                robot.write_command_packet(packet_load)

                # UI에 "이번 스텝 하고 있어요" 라고 표시한다.
                EVENT_BUS.data.progress_updated.emit(i, total_steps, TaskStatus.COMPLETED)
                EVENT_BUS.data.progress_updated.emit(step_idx, total_steps, TaskStatus.PROCESSING)

                # -----------------------------------------------------------------
                # (3) 턴테이블과 로봇 동시 출발!
                # -----------------------------------------------------------------
                
                # 서보 턴테이블 출발
                servo.move_turntable_atomic(ServoAxis.TURNTABLE, pose_turntable.angle, m3_deg_per_s)
                
                # 로봇 출발 (Trigger ON)
                time.sleep(0.3) # 데이터가 확실히 들어갈 때까지 살짝 대기
                packet_trigger, _ = self._calculate_and_pack(
                    current_pose, target_pose, 
                    current_turntable_angle, pose_turntable.angle, m3_deg_per_s,
                    previous_robot_velocity, 
                    data_ready=True,   # "출발!" 신호 킴
                    start_trigger=True 
                )
                robot.write_command_packet(packet_trigger)
                
                EVENT_BUS.log.message.emit(f"{self._log_prefix}  -> [Step {step_idx}] 출발합니다!", "DEBUG")
                
                # 현재 위치 정보 갱신
                current_pose = target_pose
                current_turntable_angle = pose_turntable.angle
                previous_robot_velocity = velocity

            # [마지막 정리] 다 보냈으면 마지막 동작이 끝날 때까지 기다린다.
            EVENT_BUS.log.message.emit(f"{self._log_prefix} 마지막 동작이 끝날 때까지 대기 중...", "INFO")
            if not self._wait_event_with_safety(robot_motion_done_event, timeout=self.move_timeout):
                EVENT_BUS.log.message.emit(f"{self._log_prefix} 마지막 동작 대기 시간 초과됨 (그냥 종료함).", "WARNING")
            
            # [종료 프로토콜] 로봇에게 "이제 진짜 끝이야" 라고 알린다. (모든 신호 끄기)
            EVENT_BUS.log.message.emit(f"{self._log_prefix} 작업 종료 절차 실행 (모든 신호 끄기)...", "DEBUG")
            
            time.sleep(0.3)
            signals_finish = {
                FanucSignal.IMSP: True, FanucSignal.HOLD: True, FanucSignal.SFSP: True, FanucSignal.ENABLE: True,
                FanucSignal.RSR3: True,
                FanucSignal.TRIGGER_DI43: False, # 트리거 끄기
                FanucSignal.LOOP_DI44: False     # 루프 끄기
            }
            zero_packet = FanucPoseModel.create_signal_only_packet(signals_finish)
            robot.write_command_packet(zero_packet)

            # 성공했다고 알림
            EVENT_BUS.data.progress_updated.emit(total_steps, total_steps, TaskStatus.COMPLETED)
            return True, f"{self._log_prefix} 모든 작업이 완벽하게 끝났습니다."

        except InterruptedError as e:
            EVENT_BUS.log.message.emit(f"{self._log_prefix} 사용자 요청으로 멈춥니다. 장비 정지 신호 전송 중...", "WARNING")
            try: robot.set_emergency_stop()
            except: pass
            try: servo.request_immediate_stop()
            except: pass
            return False, str(e)

        except Exception as e:
            EVENT_BUS.log.message.emit(f"{self._log_prefix} 실행 중 오류가 터졌습니다: {e}. 비상 정지합니다!", "ERROR")
            try: robot.set_emergency_stop() 
            except: pass
            try: servo.request_immediate_stop() 
            except: pass
            return False, f"{self._log_prefix} 오류 발생: {e}"
            
        finally:
            EVENT_BUS.data.sequence_job_finished.emit()
            try: robot.remove_notification(handle_motion)
            except: pass
            
            # [뒷정리] 혹시 켜져있을지 모르는 신호들을 한번 더 확실하게 끈다.
            try:
                cleanup_signals = {
                    FanucSignal.IMSP: True, FanucSignal.HOLD: True, FanucSignal.SFSP: True, FanucSignal.ENABLE: True,
                    FanucSignal.TRIGGER_DI43: False,
                    FanucSignal.LOOP_DI44: False
                }
                cleanup_packet = FanucPoseModel.create_signal_only_packet(cleanup_signals)
                robot.write_command_packet(cleanup_packet)

                # 서보 모터는 원점 위치로 안전하게 복귀시킨다.
                servo.home_all_safely(timeout=30.0)
                EVENT_BUS.log.message.emit(f"{self._log_prefix} 서보 모터 원점 복귀 완료.", "DEBUG")
            except Exception as e:
                EVENT_BUS.log.message.emit(f"{self._log_prefix} 뒷정리 하다가 오류 발생: {e}", "WARNING")

    def execute_deprecated(self, sequence_data: List[Dict[str, Any]]) -> tuple[bool, str]:
        """[사용 안함] 옛날 방식 코드이다."""
        return False, "This method is deprecated. Use execute() instead."

    def _wait_event_with_safety(self, event: threading.Event, timeout: float) -> bool:
        """
        [안전하게 기다리기] 
        그냥 멍하니 기다리면 사용자가 '정지' 버튼을 눌러도 못 알아차린다.
        그래서 0.1초마다 눈을 뜨고 "정지 버튼 눌렸나?" 확인하면서 기다린다.
        
        Returns: 이벤트가 잘 오면 True, 시간 초과되거나 정지되면 False
        """
        start = time.time()
        while time.time() - start < timeout:
            # 1. 사용자가 STOP 버튼을 눌렀는지 체크
            if (t := QThread.currentThread()) and t.isInterruptionRequested():
                return False
            
            # 2. 0.1초만 잠깐 대기
            if event.wait(0.1):
                return True # 기다리던 신호가 왔다!
                
        return False # 너무 오래 기다려도 안 왔다.
        
    def _is_interrupted(self) -> bool:
        """현재 누가 내 어깨를 치면서 "그만해"라고 했는지 확인하는 함수이다."""
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

