# workers/monitor_worker.py
import time
from typing import Dict, TYPE_CHECKING
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from core.event_bus import EVENT_BUS
from models.servo_pose_model import ServoPose
from models.servo_pose_key import ServoAxis
from models.fanuc_pose_model import FANUCPose

if TYPE_CHECKING:
    from communication.twincat_commander import TwinCATCommander

class MonitorWorker(QObject):
    finished = pyqtSignal()

    def __init__(self, commander: 'TwinCATCommander'):
        super().__init__()
        self.commander = commander
        self._is_running = True
        
        # [최적화 1] 이전 데이터를 저장할 변수 (캐시)
        self._last_robot_pose: FANUCPose | None = None
        self._last_servo_states: Dict[ServoAxis, ServoPose] | None = None
        
        # [최적화 2] 변화 감지 임계값 (이보다 작게 변하면 무시)
        self.ROBOT_THRESHOLD = 0.01  # 0.01mm (또는 deg) 이상 변해야 전송
        self.SERVO_THRESHOLD = 0.01  # 0.01도 이상 변해야 전송

    def stop(self):
        """모니터링 루프 중단 (PLCService에서 호출됨)"""
        self._is_running = False

    @pyqtSlot()
    def run(self):
        while self._is_running:
            try:
                if not self.commander.connector.is_connected:
                    time.sleep(1.0)
                    continue

                # 1. 로봇 상태 읽기 (변화 체크 포함)
                self._check_robot_optimized()

                # 2. 서보 상태 읽기 (변화 체크 포함)
                self._check_servo_optimized()

                time.sleep(0.1) 

            except Exception:
                # 에러 로그도 너무 자주 찍히지 않게 조절 가능
                time.sleep(1.0)

        self.finished.emit()

    def _check_robot_optimized(self):
        try:
            current_pose = self.commander.robot.read_current_world_pose()
            
            # [핵심 로직] 이전 값과 비교해서 변화가 없으면 리턴 (Emit 안함)
            if not self._is_robot_diff(self._last_robot_pose, current_pose):
                return 

            # 변화가 큼 -> 방송 및 캐시 업데이트
            EVENT_BUS.control.robot_current_pose.emit(current_pose)
            self._last_robot_pose = current_pose
            
        except Exception:
            pass

    def _check_servo_optimized(self):
        try:
            current_states: Dict[ServoAxis, ServoPose] = {}
            for axis in ServoAxis:
                raw = self.commander.servo.read_current_servo_motion(axis)
                current_states[axis] = ServoPose(raw['position'], raw['velocity'])
            
            # [핵심 로직] 서보 데이터 변화 체크
            if not self._is_servo_diff(self._last_servo_states, current_states):
                return

            # 변화가 큼 -> 방송 및 캐시 업데이트
            EVENT_BUS.control.servo_current_motion.emit(current_states)
            self._last_servo_states = current_states
            
        except Exception:
            pass

    # --- 비교 함수들 ---
    
    def _is_robot_diff(self, old: FANUCPose | None, new: FANUCPose) -> bool:
        """로봇 좌표가 임계값 이상 변했는지 검사"""
        if old is None: return True # 처음이면 무조건 전송
        
        # X, Y, Z, W, P, R 중 하나라도 임계값 이상 차이나면 True
        return (abs(old.x - new.x) > self.ROBOT_THRESHOLD or
                abs(old.y - new.y) > self.ROBOT_THRESHOLD or
                abs(old.z - new.z) > self.ROBOT_THRESHOLD or
                abs(old.w - new.w) > self.ROBOT_THRESHOLD or
                abs(old.p - new.p) > self.ROBOT_THRESHOLD or
                abs(old.r - new.r) > self.ROBOT_THRESHOLD)

    def _is_servo_diff(self, old: Dict[ServoAxis, ServoPose] | None, new: Dict[ServoAxis, ServoPose]) -> bool:
        """서보 상태가 임계값 이상 변했는지 검사"""
        if old is None: return True
        
        for axis, new_pose in new.items():
            old_pose = old.get(axis)
            
            if old_pose is None: return True
            
            # 각도나 속도 중 하나라도 변했으면 True
            if (abs(old_pose.angle - new_pose.angle) > self.SERVO_THRESHOLD or
                abs(old_pose.velocity - new_pose.velocity) > self.SERVO_THRESHOLD):
                return True
                
        return False