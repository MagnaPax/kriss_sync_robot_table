# workers/monitor_worker.py
import time
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from core.event_bus import EVENT_BUS
from models.servo_pose_model import ServoPose
from models.servo_pose_key import ServoAxis
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from communication.twincat_commander import TwinCATCommander

class MonitorWorker(QObject):
    """
    [백그라운드] 실시간 상태 모니터링 전담 워커
    UI 스레드 방해 없이 10Hz(0.1초) 주기로 PLC 데이터를 읽어옴
    """
    finished = pyqtSignal()

    def __init__(self, commander: "TwinCATCommander"):
        super().__init__()
        self.commander = commander
        self._is_running = True
        self._is_robot_active = True
        self._is_servo_active = True

    @pyqtSlot()
    def run(self):
        """스레드 진입점 (무한 루프)"""
        while self._is_running:
            try:
                # 연결 끊기면 루프 종료
                if not self.commander.connector.is_connected:
                    break

                # 1. 로봇 상태 읽기
                self._check_robot()

                # 2. 서보 상태 읽기
                self._check_servo()

                # 3. CPU 과부하 방지 (10Hz)
                time.sleep(0.1) # QThread.msleep(100)과 동일 효과

            except Exception as e:
                EVENT_BUS.log.message.emit(f"모니터링 스레드 에러: {e}", "ERROR")
                time.sleep(1.0) # 에러 나면 잠시 쉬었다 재시도

        self.finished.emit()

    def stop(self):
        """외부에서 루프 종료 요청"""
        self._is_running = False

    def _check_robot(self):
        if not self._is_robot_active: return
        try:
            world_pose = self.commander.robot.read_current_world_pose()
            EVENT_BUS.control.robot_current_pose.emit(world_pose)
        except Exception as e:
            if "1808" in str(e) or "not found" in str(e).lower():
                self._is_robot_active = False # 변수 없으면 모니터링 끔

    def _check_servo(self):
        if not self._is_servo_active: return
        try:
            servo_states = {}
            for axis in ServoAxis:
                # 어댑터가 Thread-Safe하지 않을 수 있으나, Read 작업은 보통 충돌이 적음
                # 만약 충돌 발생 시 Lock 처리 필요
                raw_data = self.commander.servo.read_current_servo_motion(axis)
                servo_states[axis] = ServoPose(
                    angle=raw_data['position'],
                    velocity=raw_data['velocity']
                )
            
            if servo_states:
                EVENT_BUS.control.servo_current_motion.emit(servo_states)
            
            # Busy 상태 방송
            is_busy = self.commander.are_gagets_busy()
            EVENT_BUS.data.servo_busy_status.emit({'is_busy': is_busy})

        except Exception as e:
            if "1808" in str(e) or "not found" in str(e).lower():
                self._is_servo_active = False
