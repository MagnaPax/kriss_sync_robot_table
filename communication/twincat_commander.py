# communication/twincat_commander.py
"""
TwinCAT Commander (Model Layer)
    전략 패턴(Strategy Pattern) 사용

    역할:
        TwinCAT 에 연결된 기기(FANUC 로봇, 턴테이블) 제어
"""
import time
import threading
from PyQt6.QtCore import QThread, QObject
from abc import ABC, abstractmethod
from typing import List, Any, Optional, Dict

from core.event_bus import EVENT_BUS
from communication.fanuc_adapter import FanucAdapter
from communication.servo_adapter import ServoAdapter
from communication.twincat_connector import TwinCATConnector
from models.fanuc_pose_model import FANUCPose
from models.servo_pose_model import ServoPoseModel
from config.data_formats import (
    TaskStatus, SERVO_KEYS, ROBOT_KEYS,
    KEY_ROBOT_X, KEY_ROBOT_Y, KEY_ROBOT_Z, KEY_ROBOT_W, KEY_ROBOT_P, KEY_ROBOT_R,
    KEY_ROBOT_FEED_RATE, KEY_TURNTABLE_DEG, KEY_TURNTABLE_FEED_RATE,
    KEY_TOOL_REV_RPM, KEY_TOOL_ROT_RPM
)
from models.servo_pose_key import ServoAxis
from core.settings import SETTINGS


# =========================================================
# 1. 추상 실행기 (Base Executor)
# =========================================================
class BaseExecutor(ABC):
    def __init__(self, robot: FanucAdapter, servo: ServoAdapter):
        self.robot = robot
        self.servo = servo

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
    """로봇 단독 제어"""

    def can_execute(self, sample_data: Dict[str, Any]) -> bool:
        data_keys = set(sample_data.keys())
        has_robot = not ROBOT_KEYS.isdisjoint(data_keys)
        has_servo = not SERVO_KEYS.isdisjoint(data_keys)
        # 로봇 키가 있고, 서보 키는 없을 때
        return has_robot and not has_servo

    def execute(self, sequence_data: List[Dict[str, Any]]) -> tuple[bool, str]:
        """
        FANUC 로봇에게 연속적인 이동 경로를 명령하며 각 스텝마다 정확한 동기화를 보장
        
        1. 초기화:
            - Handshake용 Event와 Callback을 준비
            - `write_initial_signals()`로 로봇을 깨운다
        
        2. 시퀀스 루프 (Step-by-Step):
            a. Delta 계산 (Pre-calculation): 
                - 현재 위치와 목표 위치의 차이(Delta)를 계산한다 (모델 내부 `to_struct`에서 수행).
            b. 패킷 전송 (Trigger): 
                - `write_command_packet()`으로 데이터를 한 방에 보낸다.
            c. 완료 대기 (Handshake):
                - 로봇이 이동을 완료하고 DO45 신호를 Rising Edge(0->1)로 띄울 때까지 기다린다.
                - `_move_complete_event.wait()`로 효율적으로 대기하며, 폴링(무한루프)을 사용하지 않는다.
                - 안전장치: 0.1초마다 `QThread` 중단 요청(Stop 버튼)을 체크하여 즉각 반응한다.
            
        3. 종료:
            - 모든 이동이 끝나면 `set_finish_signals()`로 정리한다.
            - `finally` 블록에서 Notification 리소스를 반드시 해제한다.
        
        Returns:
            (성공여부, 메시지)
        """
        EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] FANUC 단독 제어 시작 (데이터 {len(sequence_data)}건)", "INFO")
        EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] 에서 처리될 전체 데이터\n{(sequence_data)}\n", "DEBUG")

        # 처리할 전체 시퀀스 데이터 방송
        EVENT_BUS.data.sequence_data_loaded.emit(sequence_data)

        adapter = self.robot

        # 사용자 입력 feed rate 초기화 (새 작업 시작이기 때문)
        adapter.override_feed_rate = None

        num_sequences = len(sequence_data)  # 전체 시퀀스 갯수
        
        # Event 객체 생성 (Handshake용)
        # 원본 파일: 260102.FANUC_FULL_THREADING.py
        import threading
        _move_complete_event = threading.Event()
        
        # 콜백 함수 정의
        def _on_robot_move_complete_signal(notification, data):
            # 원본 라인 127: move_next_event.set()
            _move_complete_event.set()

        # 알림(Notification) 등록 핸들
        notify_handle = None

        try:
            # 1. 시작 전 로봇 상태 검증
            adapter.validate_robot_ready()
            
            # Notification 등록
            notify_handle = adapter.register_handshake_callback(_on_robot_move_complete_signal)
            EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] Handshake 알림 등록 완료 (Handle: {notify_handle})", "DEBUG")

            previous_pose = None  # 이전 명령 (Delta 계산용)
            
            # 2. 초기 신호 전송
            # 원본 라인 185: plc.write_by_name(STRUCT_SYMBOL, init_payload, FanucUI1Struct)
            adapter.write_initial_signals()

            # 3. 시퀀스 루프
            for idx, row in enumerate(sequence_data, 1):
                # (A) 중단 요청 확인 (안전장치)
                if (thread := QThread.currentThread()) and thread.isInterruptionRequested():
                    return False, "사용자에 의해 작업이 중단되었습니다."

                adapter.validate_robot_ready() # 매 스텝 시작 전 체크

                # 데이터에 'id'가 있으면 가져오고, 없다면 루프 인덱스(idx)를 id로 사용
                current_id = row.get('id') or idx

                # 현재 시퀀스 진행상태 방송: 진행중
                EVENT_BUS.data.progress_updated.emit(current_id, num_sequences, "processing")
                EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] 현재 시퀀스 진행상태: {(current_id)}", "DEBUG")

                # 이동 속도 결정
                if adapter.override_feed_rate is not None:
                    # 사용자가 '지금' 바꾼 FEED RATE
                    feed_rate = adapter.override_feed_rate
                else:
                    # GO TO 버튼 눌렀을 때 입력한 FEED RATE 
                    # (또는 데이터에 있는 F값)
                    feed_rate = row.get(KEY_ROBOT_FEED_RATE, 10.0)

                # 4. 목표 포즈 생성 (데이터 매핑)
                target_pose = FANUCPose(
                    x=row.get(KEY_ROBOT_X, 0.0), y=row.get(KEY_ROBOT_Y, 0.0), z=row.get(KEY_ROBOT_Z, 0.0),
                    w=row.get(KEY_ROBOT_W, 0.0), p=row.get(KEY_ROBOT_P, 0.0), r=row.get(KEY_ROBOT_R, 0.0),
                    f=feed_rate
                )
                # 현재 로봇 위치 방송
                EVENT_BUS.control.robot_current_pose.emit(target_pose)
                EVENT_BUS.log.message.emit(f"\n현재 로봇 위치: {target_pose}\n", "DEBUG")

                # 5. 첫 번째 스텝 처리 (Delta=0)
                if previous_pose is None:
                    # 원본 로직: "if prev_coords is None: move_deltas = zero_deltas.copy()"
                    # to_struct 내부에서 prev_pose와 target_pose가 같으면 Delta 0으로 처리됨
                    # 따라서 첫 번째는 자기 자신을 prev로 넘겨줌
                    previous_pose = target_pose
                
                # 6. 신호(Signal) 준비
                # 원본 라인 177: base_signals = {'IMSP': True, ...}
                signals = {
                    'IMSP': True, 'Hold': True, 'SFSP': True, 'Enable': True,
                    'CycleStop': False, 'Start': False, 'RSR2': False, 'DI43': True # DI43=True (이동 명령)
                }
                
                # 원본 라인 208: if i == 1: signals['RSR2'] = True
                # (첫 번째 무브먼트일 때 RSR2를 켜주는 로직 복원)
                if idx == 1:
                    signals['RSR2'] = True

                # 7. 패킷 생성 (Delta 계산은 모델 내부 위임)
                # 원본 라인 210: payload = pack_fanuc_payload(...)
                packet = target_pose.to_struct(previous_pose, signals)

                # 8. 전송 (Write)
                # 원본 라인 213: plc.write_by_name(STRUCT_SYMBOL, payload, FanucUI1Struct)
                adapter.write_command_packet(packet)
                
                EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] #{idx} 명령 전송 완료. Rising Edge 대기 중...", "DEBUG")
                
                # 9. Handshake 대기 (Wait for Rising Edge)
                # 원본 라인 219: if move_next_event.wait(timeout=20.0): ...
                # QThread 중단을 감지하기 위해 루프 사용 (사용자 요청 시 즉시 반응)
                
                _move_complete_event.clear() # 확실하게 클리어
                
                wait_start = time.time()
                timeout = 20.0 # 20초 타임아웃
                success = False
                
                while time.time() - wait_start < timeout:
                    # (A) 중단 요청 확인
                    if (thread := QThread.currentThread()) and thread.isInterruptionRequested():
                        EVENT_BUS.log.message.emit("대기 중 사용자 중단 요청 감지", "WARNING")
                        break # 바깥 루프의 중단 로직에서 처리됨
                    
                    # (B) 이벤트 확인 (0.1초씩 끊어서 대기)
                    if _move_complete_event.wait(timeout=0.1):
                        success = True
                        break
                        
                if not success:
                    # 타임아웃인지 중단인지 확인
                    if (thread := QThread.currentThread()) and thread.isInterruptionRequested():
                        return False, "사용자에 의해 작업이 중단되었습니다."
                    else:
                        return False, f"[{self.__class__.__name__}] 로봇 응답 시간 초과 (Timeout 20s)"
                
                EVENT_BUS.log.message.emit(" -> OK (Rising Edge Detected)", "DEBUG")

                # 10. 기준점 업데이트
                # 원본 라인 226: prev_coords = target_coords
                previous_pose = target_pose

                # 11. 첫 번째 스텝 이후 RSR2 끄기 (옵션)
                # 원본 라인 228: if i == 1: signals['RSR2'] = False ...
                if idx == 1:
                    signals['RSR2'] = False
                    # 신호만 끄고 다시 전송 (Delta는 그대로 둬야 함? 원본은 그대로 둠)
                    # 원본은 target_coords, move_deltas 그대로 사용
                    packet = target_pose.to_struct(previous_pose, signals) # previous_pose가 갱신되었으므로 Delta는 0이 됨
                    adapter.write_command_packet(packet)


                # 현재 시퀀스 진행상태 방송: 완료
                EVENT_BUS.data.progress_updated.emit(current_id, num_sequences, "processed")

            # 3. 종료 신호
            # 원본의 finally 블록 혹은 루프 종료 후 정리
            adapter.set_finish_signals()
            return True, "작업 완료"
        
        except Exception as e:
            try:
                adapter.set_emergency_stop()
            except:
                pass
            
            # 사용자 친화적 메시지 변환
            msg = str(e)
            if "Robot Fault" in msg:
                msg = "로봇 하드웨어 결함이 감지되었습니다. 비상 정지 버튼이 눌려있거나 컨트롤러에 알람이 있는지 확인 후 리셋해 주세요."
            elif "symbol not found" in msg.lower():
                msg = "로봇 통신 변수를 찾을 수 없습니다. PLC 프로그램이 실행 중인지 확인해 주세요."

            return False, f"[{self.__class__.__name__}] {msg}"
            
        finally:
            # 리소스 정리 (콜백 해제)
            if notify_handle is not None:
                adapter.remove_notification(notify_handle)
                EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] 계산 요청 알림 해제 완료", "DEBUG")

    def _is_interrupted(self) -> bool:
        """안전장치: 현재 실행 중인 스레드가 정지 요청을 받았는지 확인한다."""
        return bool((thread := QThread.currentThread()) and thread.isInterruptionRequested())

class ServoOnlyExecutor(BaseExecutor):
    """
    [서보 모터 전용 실행기]
    로봇 없이 Panasonic 서보 모터 3축(툴 2개 + 턴테이블 1개)만 단독 제어
    """

    def __init__(self, robot: FanucAdapter, servo: ServoAdapter):
        super().__init__(robot, servo)
        
        # 서보를 기다려주는 시간 (설정 파일에서 값 로드)
        self.BUSY_TIMEOUT = SETTINGS.servo.busy_timeout
        self.MOVE_TIMEOUT = SETTINGS.servo.move_timeout

    def can_execute(self, sample_data: Dict[str, Any]) -> bool:
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
        EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] 서보 단독 제어 시작 (데이터 {len(sequence_data)}건)", "INFO")
        EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] 에서 처리될 전체 데이터\n{(sequence_data)}\n", "DEBUG")

        # 처리할 전체 시퀀스 데이터 방송
        EVENT_BUS.data.sequence_data_loaded.emit(sequence_data)

        # 설정값 최신화 (실행 시점의 Settings 값 적용)
        self.BUSY_TIMEOUT = SETTINGS.servo.busy_timeout
        self.MOVE_TIMEOUT = SETTINGS.servo.move_timeout

        adapter = self.servo
        total_steps = len(sequence_data)
        EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] 서보 시퀀스 시작 (총 {total_steps}건)", "INFO")
        
        try:
            # 1. 초기화 (Setup) - 전원 ON
            for axis in ServoAxis:
                adapter.set_servo_state(axis, True)

            # 2. 실행 루프 (Loop)
            for step_idx, row in enumerate(sequence_data, start=1):

                # (A) 중단 요청 확인
                if self._is_interrupted():
                    adapter.request_immediate_stop()
                    return False, "사용자에 의해 작업이 중단되었습니다."

                # (B) UI 진행률 업데이트
                EVENT_BUS.data.progress_updated.emit(step_idx, total_steps, TaskStatus.PROCESSING)
                EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] {step_idx}/{total_steps} 진행 중", "DEBUG")

                # (Pre-Check) 턴테이블 이동 결정
                pose_turntable = ServoPoseModel.create_for_axis(row, KEY_TURNTABLE_DEG)
                current_turntable_pos = adapter.read_current_servo_motion(ServoAxis.TURNTABLE)['position']
                
                should_move_turntable = True

                # 1. 위치 체크: 이미 목표 위치에 있는가?
                if abs(current_turntable_pos - pose_turntable.angle) < 0.05:
                    EVENT_BUS.log.message.emit(
                        f"[{self.__class__.__name__}] 턴테이블이 이미 목표 각도({pose_turntable.angle:.2f}°)에 있습니다. 이동 스킵.",
                        "INFO"
                    )
                    should_move_turntable = False

                # 2. 속도 체크: 속도가 0인가?
                elif pose_turntable.velocity <= 0:
                    EVENT_BUS.log.message.emit(
                        f"[{self.__class__.__name__}] 턴테이블 속도가 0입니다. 이동 스킵.",
                        "INFO"
                    )
                    should_move_turntable = False

                # (C) 명령 생성 및 전송
                seq_id = row.get('id', step_idx)
                # 보기 좋게 주요 파라미터만 추출하여 로그 출력
                log_msg = (
                    f"\n"
                    f"[{self.__class__.__name__}] 시퀀스 #{seq_id} 실행 시작 ({step_idx}/{total_steps}) | "
                    f"공전={row.get(KEY_TOOL_REV_RPM, 0):.1f}RPM, "
                    f"자전={row.get(KEY_TOOL_ROT_RPM, 0):.1f}RPM, "
                    f"턴테이블={row.get(KEY_TURNTABLE_DEG, 0):.1f}deg, "
                    f"턴테이블 속도={row.get(KEY_TURNTABLE_FEED_RATE, 0):.1f}mm/rev"
                )
                EVENT_BUS.log.message.emit(log_msg, "INFO")

                # [Axis 1] Tool 공전 (속도 제어)
                pose_revolution = ServoPoseModel.create_for_axis(row, KEY_TOOL_REV_RPM)
                EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] pose_revolution 생성: {pose_revolution}", "DEBUG")
                if pose_revolution.velocity != 0:
                    adapter.move_velocity(ServoAxis.TOOL_REVOLUTION, pose_revolution.velocity)
                else:
                    adapter.stop_axis(ServoAxis.TOOL_REVOLUTION)

                # 명령 후 즉시 에러 체크
                err_rev = adapter.is_servo_error_active(ServoAxis.TOOL_REVOLUTION)
                if err_rev['error']:
                    EVENT_BUS.log.message.emit(f"Axis 1 에러 발생! ID: {err_rev['id']}", "ERROR")

                # [Axis 2] Tool 자전 (속도 제어)
                pose_rotation = ServoPoseModel.create_for_axis(row, KEY_TOOL_ROT_RPM)
                EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] pose_rotation 생성: {pose_rotation}", "DEBUG")
                if pose_rotation.velocity != 0:
                    adapter.move_velocity(ServoAxis.TOOL_ROTATION, pose_rotation.velocity)
                else:
                    adapter.stop_axis(ServoAxis.TOOL_ROTATION)

                # 명령 후 즉시 에러 체크
                err_rot = adapter.is_servo_error_active(ServoAxis.TOOL_ROTATION)
                if err_rot['error']:
                    EVENT_BUS.log.message.emit(f"Axis 2 에러 발생! ID: {err_rot['id']}", "ERROR")

                # [Axis 3] 턴테이블 (위치 제어)
                EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] pose_turntable 생성: {pose_turntable}", "DEBUG")
                if should_move_turntable:
                    adapter.move_absolute(ServoAxis.TURNTABLE, pose_turntable.angle, pose_turntable.velocity)

                # (D) 대기 (Stop-and-Go)
                # 각 스텝의 이동이 완료될 때까지 대기 (Stop-and-Go 방식)
                # 단, 이동 명령을 내린 경우에만 대기함
                if should_move_turntable:
                    if not self._wait_for_turntable_completion(ServoAxis.TURNTABLE, target_pos=pose_turntable.angle):
                        adapter.request_immediate_stop()

                        # 실패 사유 파악 (중단 vs 타임아웃)
                        msg = "작업 중단됨" if self._is_interrupted() else f"턴테이블 응답 없음 또는 시간 초과 ({self.MOVE_TIMEOUT}s)"
                        return False, msg

                # 개발용 로그
                feedback_revolution = adapter.read_current_servo_motion(ServoAxis.TOOL_REVOLUTION)
                feedback_rotation = adapter.read_current_servo_motion(ServoAxis.TOOL_ROTATION)
                feedback_turntable = adapter.read_current_servo_motion(ServoAxis.TURNTABLE)

                EVENT_BUS.log.message.emit(
                    f"[{self.__class__.__name__}] 툴 공전 (RPM) 완료: 목표={pose_revolution.velocity:.1f}, 현재={feedback_revolution['velocity']:.1f}", "DEBUG"
                )
                EVENT_BUS.log.message.emit(
                    f"[{self.__class__.__name__}] 툴 자전 (RPM) 완료: 목표={pose_rotation.velocity:.1f}, 현재={feedback_rotation['velocity']:.1f}", "DEBUG"
                )
                EVENT_BUS.log.message.emit(
                    f"[{self.__class__.__name__}] 턴테이블 (deg & RPM) 완료: 목표={pose_turntable.angle:.1f} & {pose_turntable.velocity:.1f}, 현재={feedback_turntable['position']:.1f} & {feedback_turntable['velocity']:.1f}", "DEBUG"
                )

                # (E) 스텝 완료 방송
                EVENT_BUS.data.progress_updated.emit(step_idx, total_steps, TaskStatus.PROCESSED)

            return True, "모든 서보 시퀀스 작업이 완료되었습니다."

        except Exception as e:
            try:
                adapter.request_immediate_stop()
            except Exception:
                pass # 에러 처리 중 발생한 에러는 무시(원래 발생한 에러가 더 중요함)
                
            return False, f"[{self.__class__.__name__}] 오류 발생: {str(e)}"

        finally:
            # 3. 종료 처리 (Teardown)
            EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] 종료 절차: 서보모터 정지 및 전원 차단을 시도합니다...", "DEBUG")

            # MOVE_TIMEOUT을 통해 충분한 감속시간 확보
            is_safely_shutdown = adapter.shutdown_all_with_power_off(timeout=self.MOVE_TIMEOUT)

            if is_safely_shutdown:
                EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] 모든 서보모터가 안전하게 종료되었습니다. ", "INFO")
            else:
                EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] 경고: 정지 대기 시간 초과({self.MOVE_TIMEOUT}s). 되었거나 종료 절차 중 오류가 발생하였습니다.", "WARNING")


    def _wait_for_turntable_completion(self, axis_idx: int, target_pos: Optional[float] = None) -> bool:
        EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] {axis_idx}축 이동 완료 대기 중...", "DEBUG")
        """
        턴테이블 이동 완료 대기 (Busy Check + Timeout)
        Returns: True(완료), False(실패/중단)
        """
        try:
            # -------------------------------------------------------------
            # Phase 1: Busy 신호가 뜰 때까지 대기 (최대 BUSY_TIMEOUT 초)
            # -------------------------------------------------------------
            # 명령을 보내자마자 바로 읽으면 아직 Busy가 False일 수 있음
            start_wait = time.time()
            busy_detected = False

            while time.time() - start_wait < self.BUSY_TIMEOUT:
                
                # (A) 움직임 여부 체크 (속도 기준)
                moving = self.servo.is_servo_moving_physically(axis_idx)
                
                if moving:
                    busy_detected = True
                    EVENT_BUS.data.servo_busy_status.emit({'is_servo_moving': True})
                else:
                    # 이미 목표 위치 부근이라면, 이동 명령이 무시된(No-op) 것으로 간주하고 성공 반환
                    if target_pos is not None:
                        current_pos = self.servo.read_current_servo_motion(axis_idx)['position']
                        if abs(current_pos - target_pos) < 0.05: # 0.05도 오차 허용
                            EVENT_BUS.log.message.emit(
                                f"[{self.__class__.__name__}] 축 {axis_idx}가 이미 목표 위치({target_pos:.3f})에 있으므로 대기를 종료합니다.", 
                                "DEBUG"
                            )
                            return True
                
                # (B) 움직임이 감지된 이후 -> 멈출 때까지 대기
                if busy_detected and not moving:
                    # 움직이다가 멈췄으면 -> 완료 확인
                    feedback = self.servo.read_current_servo_motion(axis_idx)
                    actual_pos = feedback['position']
                    EVENT_BUS.log.message.emit(
                        f"[{self.__class__.__name__}] Axis {axis_idx} 이동 완료: CSV목표={target_pos:.3f}, 현재위치={actual_pos:.3f}", 
                        "DEBUG"
                    )
                    return True

                # (C) 시퀀스 완전 종료 체크 (PLC 쪽에서 강제 종료 시)
                if self._is_interrupted():
                    return False

                time.sleep(0.1)
            
            # 만약 루프가 종료됐고 바쁨이 여전히 감지되지 않았다면 바쁨 신호가 제대로 전달되지 않았다는 의미
            if not busy_detected:
                EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] 축 {axis_idx} 반응 없음 (Busy Timeout)", "ERROR")
                return False

            # -------------------------------------------------------------
            # Phase 2: 멈출 때까지 대기 (최대 MOVE_TIMEOUT 초)
            # -------------------------------------------------------------
            move_start_time = time.time()

            # 이동중 - 멈출 때까지 대기
            #   타임아웃을 길게 잡거나 없애야 함 (이동이 10초 걸릴 수도 있으니까)
            while self.servo.is_servo_moving_physically(axis_idx):
                # 중단 요청 체크
                if self._is_interrupted(): return False

                # 타임아웃 체크 (무한 대기 방지)
                if time.time() - move_start_time > self.MOVE_TIMEOUT:
                    EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] 축 {axis_idx} 이동 시간 초과 ({self.MOVE_TIMEOUT}초)", "ERROR")
                    return False

            feedback = self.servo.read_current_servo_motion(axis_idx)
            actual_pos = feedback['position']
            EVENT_BUS.log.message.emit(
                f"[{self.__class__.__name__}] Axis {axis_idx} 이동 완료: CSV목표={target_pos:.3f}, 현재위치={actual_pos:.3f}", 
                "DEBUG"
            )
            return True
        
        finally:
            # 성공/실패 여부에 상관없이 마지막에는 바쁨 신호를 해제
            EVENT_BUS.data.servo_busy_status.emit({'is_servo_moving': False})

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
    """
    CSV 파일 형식 (로봇 + 턴테이블 통합 제어)
    """
    def can_execute(self, sample_data: Dict[str, Any]) -> bool:
        data_keys = set(sample_data.keys())
        # CSV 통합 키: 로봇 키 + 서보 키가 모두 포함되어 있어야 함
        has_robot = not ROBOT_KEYS.isdisjoint(data_keys)
        has_servo = not SERVO_KEYS.isdisjoint(data_keys)
        # 구체적인 키 확인 (오탐지 방지)
        has_specific_key = (KEY_TURNTABLE_DEG in data_keys) or (KEY_ROBOT_X in data_keys)
        return has_robot and has_servo and has_specific_key

    def execute(self, sequence_data: List[Dict[str, Any]]) -> tuple[bool, str]:
        """
        [로봇 + 서보 통합 동기화 제어 메인 로직]
        
        [동작 원리: Pipeline Handshake]
        이 함수는 TwinCAT을 허브로 삼아 FANUC 로봇과 Panasonic 서보를 정밀하게 동기화한다
        
        [파이프라인 4단계]
        Loop i:
            1. Wait DO45 (Calc Req): PLC가 "다음 데이터 내놔"라고 할 때까지 대기
            2. Pre-load: 계산된 데이터를 미리 써넣음 (DI43=True, DI44=False)
            3. Wait DO46 (Motion Done): 이전 동작이 완전히 끝날 때까지 대기
            4. Trigger (DI44=True): 로봇과 서보를 동시에 출발시킴
        
        [속도 제어 전략: Turntable Master]
            턴테이블이 T만큼 도는 시간을 기준으로 로봇의 속도 F를 역산하여
            로봇과 턴테이블이 '같은 시간' 동안 움직이도록 제어한다
        """
        EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] CSV 통합 동기화 제어 시작 (데이터 {len(sequence_data)}건)", "INFO")
        EVENT_BUS.data.sequence_data_loaded.emit(sequence_data)

        adapter = self.robot
        servo = self.servo
        
        # 1. 동기화 이벤트 객체 생성 (PLC 알림을 Python에서 처리하기 위한 신호기)
        # '1년 뒤의 나'를 위한 설명:
        # 이 이벤트들은 PLC의 DO45(계산 요청)와 DO46(이동 완료) 신호가 올 때까지 루프를 블락(Stop)하는 역할을 함.
        calculation_request_event = threading.Event()
        robot_motion_done_event = threading.Event()
        
        # 콜백 정의 (PLC 통신 레이어에서 호출됨)
        def _on_calculation_request(n, d): 
            calculation_request_event.set()
        def _on_robot_motion_done(n, d): 
            robot_motion_done_event.set()
        
        h_calc, h_motion = None, None

        try:
            # 2. 초기화 (서보 전원 인가, 로봇 준비 확인, 알림 핸들러 등록)
            adapter.validate_robot_ready()
            
            # 서보 축 전원 ON 확인 (Spindle Revolution, Spindle Rotation, Turntable)
            for axis_idx in range(1, 4):
                if not servo.is_servo_on(axis_idx):
                    servo.set_servo_state(axis_idx, True)
            
            # PLC 신호 감지(Handshake)를 위한 알림 등록
            h_calc = adapter.register_calculation_request_callback(_on_calculation_request)
            h_motion = adapter.register_robot_motion_done_callback(_on_robot_motion_done)
            EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] 동기화(Handshake) 알림 등록 완료", "DEBUG")

            # 3. 로봇 초기 통신 신호 리셋
            adapter.write_initial_signals()
            
            # 4. 루프 제어용 위치 변수 초기화
            current_robot_pose = FANUCPose() # (0,0,0,0,0,0)
            
            # 턴테이블 현재 실제 각도 읽기
            try:
                tt_feedback = servo.read_current_servo_motion(ServoAxis.TURNTABLE_AXIS_3)
                current_turntable_angle = tt_feedback['position']
            except:
                current_turntable_angle = 0.0

            previous_robot_calculated_velocity = 100.0 # 초기 속도 기준값

            # 5. 시퀀스 실행 루프 (정밀 동기화 4단계 모델)
            # ---------------------------------------------------------------------
            # '1년 뒤의 나'를 위한 핵심 로직 설명:
            # 이 루프는 [계산 요청 -> 데이터 매립 -> 완료 대기 -> 동시 트리거]의 4단계 셰이킹을 수행함.
            # ---------------------------------------------------------------------
            num_sequences = len(sequence_data)
            
            for idx, row in enumerate(sequence_data, 1):
                # (A) 안전 중단 체크
                if self._is_interrupted():
                    return False, "사용자에 의해 작업이 중단되었습니다."
                
                adapter.validate_robot_ready()
                current_id = row.get('id') or idx
                EVENT_BUS.data.progress_updated.emit(current_id, num_sequences, "processing")
                
                # --- [Step 1] Wait for Calculation Request (DO45) ---
                # 로봇이 다음 점(Point) 데이터를 가져갈 준비가 되었는지 PLC 신호를 기다린다.
                # (첫 스텝은 즉시 시작하므로 2번째 스텝부터 대기함)
                if idx > 1:
                    if not self._wait_event_with_safety(calculation_request_event, timeout=30.0):
                        return False, "로봇의 다음 스텝 계산 요청(DO45)을 받지 못했습니다. (Timeout 30s)"

                # --- [Step 2] Pre-load Target Data Calculation ---
                # 다음 스텝에서 이동할 위치와 속도를 미리 PLC 레지스터에 써넣는 공동 데이터 매립 단계.
                
                # 1. 로봇 목표 좌표 로드 (CSV 키 매핑 기반)
                # target_x: 반지름, target_z: 포물선 높이 (로봇 베이스 기준)
                target_x = row.get(KEY_ROBOT_X, 0.0)
                target_z = row.get(KEY_ROBOT_Z, 0.0)
                
                # 2. 로봇 이동 포즈 객체 준비
                robot_target = FANUCPose(
                    x=target_x, 
                    y=row.get(KEY_ROBOT_Y, 0.0), 
                    z=target_z,
                    w=row.get(KEY_ROBOT_W, 0.0), 
                    p=row.get(KEY_ROBOT_P, 0.0), 
                    r=row.get(KEY_ROBOT_R, 0.0)
                )
                
                # 3. 서보(턴테이블/스핀들) 목표 값 로드
                # turntable_theta: 턴테이블 회전 각도, turntable_velocity: 턴테이블 이동 속도
                turntable_angle_target = row.get(KEY_TURNTABLE_DEG, 0.0)
                turntable_velocity_target = row.get(KEY_TURNTABLE_FEED_RATE, 10.0)
                
                # 자전(Rotation) / 공전(Revolution) RPM
                spindle_rotation_rpm = row.get(KEY_TOOL_ROT_RPM, 0.0)
                spindle_revolution_rpm = row.get(KEY_TOOL_REV_RPM, 0.0)
                
                # [속도 동기화 로직: Turntable Master Synchronization]
                # 턴테이블이 목표 각도까지 도달하는 시간을 계산하여, 로봇의 F값을 역산한다.
                # 이를 통해 로봇과 턴테이블이 동시에 도착하도록 '시간'을 맞춘다.
                
                # 1) 턴테이블 예상 이동 시간 (dt = distance / velocity)
                tt_delta = abs(turntable_angle_target - current_turntable_angle)
                expected_move_time = tt_delta / turntable_velocity_target if turntable_velocity_target > 0 else 0.0
                
                # 2) 로봇 이동 거리 (dist, mm)
                robot_dist, _ = current_robot_pose.distance_to(robot_target)
                
                # 3) 로봇에 주입할 속도 F 결정 (speed = distance / dt)
                if robot_dist < 0.001: 
                    robot_calculated_velocity = 0.0 # 위치 변화 없음
                elif expected_move_time < 0.001:
                    # 턴테이블이 거의 안 움직이는 경우, 이전 속도를 유지하거나 기본 매뉴얼 속도 사용
                    robot_calculated_velocity = previous_robot_calculated_velocity if previous_robot_calculated_velocity > 0 else 100.0
                else:
                    robot_calculated_velocity = robot_dist / expected_move_time
                    
                # 로봇 속도 물리적 상한선 제한 (안전을 위해 500mm/s로 캡)
                robot_calculated_velocity = min(robot_calculated_velocity, 500.0)

                # 최종 계산된 속도가 포함된 포즈 생성
                robot_target_final = FANUCPose(
                    x=robot_target.x, y=robot_target.y, z=robot_target.z,
                    w=robot_target.w, p=robot_target.p, r=robot_target.r,
                    velocity=robot_calculated_velocity
                )

                # 4. PLC 데이터 매립 (DI43=True: 데이터 준비됨, DI44=False: 아직 출발하지마)
                signals = {
                    'IMSP': True, 'Hold': True, 'SFSP': True, 'Enable': True,
                    'CycleStop': False, 'Start': False, 'RSR2': (idx == 1), 
                    'DI43': True,   # [DATA READY]
                    'DI44': False   # [TRIGGER HELD]
                }

                # 로봇 구조체 생성 및 전송 (Pre-load)
                packet = robot_target_final.to_struct(current_robot_pose, signals)
                adapter.write_command_packet(packet)
                
                # --- [Step 3] Wait for Legacy Motion Done (DO46) ---
                # 이전 스텝의 물리적 이동이 완벽하게 끝났는지 확인한다.
                if idx > 1:
                    if not self._wait_event_with_safety(robot_motion_done_event, timeout=30.0):
                        return False, "이전 동작 완료(DO46) 신호를 받지 못했습니다. (Timeout 30s)"

                # --- [Step 4] Trigger (Atomic Simultaneous Start) ---
                # 모든 장치가 준비되었으므로, 트리거 신호를 동시에 쏴서 출발시킨다.
                
                # [중요] 레이스 컨디션 방지: 트리거 직전에 이벤트 플래그를 비운다.
                calculation_request_event.clear()
                robot_motion_done_event.clear()

                # DI44(트리거)를 1로 세팅하여 로봇 구조체 재전송
                signals['DI44'] = True
                packet_trigger = robot_target_final.to_struct(current_robot_pose, signals)
                adapter.write_command_packet(packet_trigger)

                # 서보 멀티 축 동시 실행 (1, 2, 3축 Batch Write)
                servo.execute_synchronized_motion(
                    turntable_moving_velocity=turntable_velocity_target,
                    turntable_target_position=turntable_angle_target,
                    spindle_rotation_velocity=spindle_rotation_rpm,
                    spindle_revolution_velocity=spindle_revolution_rpm
                )
                
                # 트리거 펄스 리셋 (신호가 1로 계속 유지되지 않도록 다시 0으로 내림)
                time.sleep(0.01) # 아주 짧은 대기 (Pulse 폭 확보)
                signals['DI44'] = False
                packet_reset = robot_target_final.to_struct(current_robot_pose, signals)
                adapter.write_command_packet(packet_reset)

                EVENT_BUS.log.message.emit(f"#{idx} 동시 동기화 트리거 전송 완료.", "DEBUG")
                
                # 다음 스텝을 위해 위치 정보 갱신
                current_robot_pose = robot_target_final
                current_turntable_angle = turntable_angle_target
                previous_robot_calculated_velocity = robot_calculated_velocity
                
                EVENT_BUS.data.progress_updated.emit(current_id, num_sequences, "processed")

            # 루프 종료 후 로봇 신호 정리
            adapter.set_finish_signals()
            return True, "동기화 시퀀스 작업 완료"

        except Exception as e:
            try:
                adapter.set_emergency_stop()
                servo.request_immediate_stop()
            except: pass
            return False, f"[{self.__class__.__name__}] 에러: {e}"
            
        finally:
            if h_calc: adapter.remove_notification(h_calc)
            if h_motion: adapter.remove_notification(h_motion)

    def _wait_event_with_safety(self, event: threading.Event, timeout: float) -> bool:
        """안전장치(중단 요청 확인)가 포함된 이벤트 대기 함수"""
        start = time.time()
        while time.time() - start < timeout:
            if (t := QThread.currentThread()) and t.isInterruptionRequested():
                return False
            if event.wait(0.1):
                return True
        return False

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
        EVENT_BUS.log.message.emit(f"[{self.__class__.__name__}] 레거시 파일 모드로 실행 (데이터 {len(sequence_data)}건)", "INFO")

        # 처리할 전체 시퀀스 데이터 방송
        EVENT_BUS.data.sequence_data_loaded.emit(sequence_data)        

        return True, "레거시 파일 모드 실행 완료 -> TODO: 로직 만들어야 된다"



class TwinCATCommander(QObject):
    # =========================================================
    # 3. 게이트웨이 (The Commander)
    # =========================================================
    def __init__(self, connector: TwinCATConnector, fanuc: FanucAdapter, servo: ServoAdapter):
        super().__init__()                                  # QObject 초기화
        self._log_prefix = f"[{self.__class__.__name__}]"   # 로그 머릿말(발생 위치)
        self.connector = connector                          # 주입받은 TwinCAT 연결 저장
        
        # 하위 장치 컨트롤러 - 주입받은 것을 저장해서 사용
        self.robot = fanuc
        self.servo = servo

        # 등록된 실행기들 (우선순위 순서대로)
        # INTEGRATED(가장 구체적) -> ONLY(일반적) 순으로 배치
        self.executors: List[BaseExecutor] = [
            IntegratedExecutor(self.robot, self.servo),         # CSV 통합
            LegacyIntegratedExecutor(self.robot, self.servo),   # TXT 레거시 통합
            FanucOnlyExecutor(self.robot, self.servo),          # 로봇 단독
            ServoOnlyExecutor(self.robot, self.servo)           # 서보 단독
        ]

    def execute_sequence_with_executor(self, sequence_data: List[Dict[str, Any]]) -> tuple[bool, str]:
        """
        데이터 형식에 따라 적절한 Executor를 선택하여 실행하는 [게이트웨이]
            1. 데이터의 첫 줄을 샘플로 채취하여 적절한 실행기를 찾는다
            2. 찾은 Executor를 실행한다
        """
        
        if not sequence_data:
            return False, "데이터가 비어있습니다."

        sample_row = sequence_data[0]
        print(f"입력된 자료에 맞는 Excutor 선택을 위한 샘플 데이터(sequence_data[0]): {sample_row}")

        # 1. 적절한 Executor 찾기
        target_executor = None
        for executor in self.executors:
            if executor.can_execute(sample_row):
                target_executor = executor
                break

        # 2. 찾은 Executor에게 실행 위임
        if target_executor:
            return target_executor.execute(sequence_data)
        else:
            return False, "지원하지 않는 데이터 형식입니다."



    # ================================= #
    # --- 로봇에게 내리는 명령들 --- #
    # ================================= #
    def apply_user_feed_rate_when_moving_robot(self, feed_rate: float) -> str | None:
        """TargetPositionWidget 에서 사용자가 입력한 Feed Rate 값을 FANUC에 적용"""

        # 로봇이 움직이고 있는지 확인
        is_robot_moving = self.robot.read_busy_signal()

        if is_robot_moving:
            # FANUC의 이동속도 변경
            self.robot.send_instant_feed(feed_rate)

            # FanucAdapter 변수에 저장
            # Executor가 다음 루프부터 참조할 수 있게 하기 위함
            self.robot.override_feed_rate = feed_rate

            msg = f"사용자에 의한 이동 속도 변경: {feed_rate} mm/sec"
            return msg
        else:
            return None

    def are_gagets_busy(self) -> bool:
        """로봇이나 턴테이블 중 하나라도 움직이고 있다면 True(바쁨) 반환"""

        # 로봇 상태 확인
        robot_busy = False
        if self.robot:
            try:
                robot_busy = self.robot.read_busy_signal()
            except Exception:
                # 로봇 연결이 없거나 변수가 없을 때 에러 무시 (False 반환)
                robot_busy = False

        # 서보모터 상태 확인 (모든 3축 확인)
        servo_busy = False
        if self.servo:
            try:
                servo_busy = any(self.servo.is_servo_moving_physically(axis) for axis in ServoAxis)
            except Exception as e:
                # 반복 호출되므로 로그 레벨을 DEBUG로 낮춤
                EVENT_BUS.log.message.emit(f"서보모터 상태 확인 중 오류: {e}", "DEBUG")
                servo_busy = False

        # 둘 중 하나라도 바쁘면 시스템은 바쁜 것
        return robot_busy or servo_busy

    def start_sequence_plc_signals(self) -> tuple[bool, str]:
        """로봇에게 시작 신호(RSR, Loop 등) 전송"""
        if self.robot:
            try:
                self.robot.set_initial_signals()
                return True, "시작 신호 전송 완료"
            except Exception as e:
                # 1808: Symbol not found (Servo Only 모드)
                if "symbol not found" in str(e).lower() or "1808" in str(e):
                    EVENT_BUS.log.message.emit(f"로봇 시작 신호 전송 실패 (변수 없음): {e}", "WARNING")
                    return True, "로봇 연결 없음 (무시됨)"

                return False, f"시작 신호 전송 실패: {e}"
        return False, "로봇이 연결되지 않았습니다."

    def end_sequence_plc_signals(self) -> tuple[bool, str]:
        """로봇에게 종료/정지 신호 전송"""
        if self.robot:
            try:
                self.robot.set_finish_signals()
                return True, "종료 신호 전송 완료"
            except Exception as e:
                # 1808: Symbol not found (Servo Only 모드)
                # 로봇이 없어도 서보 정지 등 후속 작업을 위해 True 반환
                if "symbol not found" in str(e).lower() or "1808" in str(e):
                    EVENT_BUS.log.message.emit(f"로봇 정지 신호 전송 실패 (변수 없음): {e}", "WARNING")
                    return True, "로봇 연결 없음 (무시됨)"

                return False, f"종료 신호 전송 실패: {e}"
        return False, "로봇이 연결되지 않았습니다."



    # ================================= #
    # --- 서보(Panasonic) 제어 명령 --- #
    # ================================= #
    def is_servo_on(self, axis: ServoAxis) -> bool:
        """서보 전원이 켜져 있는지 확인 (브릿지)"""
        if self.servo:
            return self.servo.is_servo_on(axis.value)
        return False

    def set_servo_state(self, axis: ServoAxis, enable: bool):
        """서보 전원 상태 설정 (브릿지)"""
        if self.servo:
            self.servo.set_servo_state(axis.value, enable)

    def shutdown_servos_safely(self) -> tuple[bool, str]:
        """
        [브릿지] 서보를 안전하게 정지시키고 전원을 차단하도록 시킴
        Worker -> Commander -> Adapter 순으로 명령 전달
        """
        if self.servo:
            # Adapter의 '명확한 이름'의 메서드를 호출
            success = self.servo.shutdown_all_with_power_off()
            
            msg = "모든 서보가 안전하게 정지 및 해제되었습니다." if success else "서보 종료 처리 중 오류 발생"
            return success, msg
        
        return False, "서보 어댑터가 연결되지 않았습니다."


    def home_servos_safely(self) -> tuple[bool, str]:
        """
        [브릿지] 서보의 안전 원점 복귀 절차를 실행하도록 시킴
        """
        if not self.servo:
            return False, "서보 어댑터가 연결되지 않았습니다."

        # 원점 복귀 시작 전 바쁨 상태 방송
        EVENT_BUS.data.servo_busy_status.emit({'is_servo_moving': True})

        try:
            # Adapter에게 원점 복귀 절차 위임
            success = self.servo.home_all_safely()
            msg = "서보 원점 복귀 명령 전송 완료" if success else "원점 복귀 중 오류 발생"
            return success, msg
        except Exception as e:
            return False, f"서보 원점 복귀 중 예외 발생: {e}"
        finally:
            # 성공/실패 여부에 상관없이 마지막에는 바쁨 상태 해제
            EVENT_BUS.data.servo_busy_status.emit({'is_servo_moving': False})


    def reset_servos_safely(self) -> tuple[bool, str]:
        """서보 축의 에러 상태 해제"""
        if not self.servo: 
            return False, "서보 어댑터가 연결되지 않았습니다."

        try:
            results = []
            # 모든 축에 대해 에러 리셋 시도
            for axis in ServoAxis:
                # clear_error_pulse는 내부적으로 에러가 있을 때만 리셋 동작을 수행함
                is_cleared = self.servo.clear_error_pulse(axis.value)
                results.append(is_cleared)
            
            if all(results):
                return True, "모든 서보 축의 에러가 리셋되었습니다."
            else:
                return False, "일부 축의 에러 리셋에 실패했습니다."
        except Exception as e:
            return False, f"서보 리셋 중 오류 발생: {e}"