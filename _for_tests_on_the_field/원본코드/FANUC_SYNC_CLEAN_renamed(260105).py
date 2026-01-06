# -*- coding: utf-8 -*-
"""
[Project] FANUC Robot & Turntable Sync System (Refactored)
[Structure]
  1. Config & Globals
  2. Data Structures (Structs)
  3. Hardware Classes (FanucController, MotorController)
  4. Logic Functions (Calculation, Worker)
  5. Main Execution Flow (Sequential)
"""

import pyads
import ctypes
import time
import sys
import threading
import math
from datetime import datetime

# =============================================================================
# 1. Configuration & Global Events
# =============================================================================
# [Connection Info]
AMS_NET_ID = '5.119.154.174.1.1' #'192.168.0.196.1.1'
FANUC_PORT = 852
MOTOR_PORT = 851

# [Symbols]
SYM_ROBOT_COMMAND_STRUCT = "MAIN.Robot1._UI1"
SYM_SYNC_START_TRIGGER   = "MAIN.Robot1._UI1.DI44" # Start Trigger
SYM_CALC_REQUEST         = "MAIN.Robot1._UO1.DO45" # Calc Request
SYM_ROBOT_MOTION_DONE    = "MAIN.Robot1._UO1.DO46" # Motion Done
SYM_TURNTABLE_MOTION_DONE = "MAIN.bDone3"           # Motor Done

# [Events]
event_calculation_request = threading.Event()
event_robot_motion_done   = threading.Event()
sys_stop_event            = threading.Event()

# [Sync Status]
timestamp_start_step = 0.0
timestamp_robot_done = 0.0
timestamp_turntable_done = 0.0

# =============================================================================
# 2. Data Structures
# =============================================================================
class FanucCommandPacket(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("UI_Byte1", ctypes.c_uint8),
        ("UI_Byte2", ctypes.c_uint8),
        ("UI_Byte3", ctypes.c_uint8), # DI44 is Bit 3
        ("Feed_Low", ctypes.c_uint16),
        ("X_High", ctypes.c_uint8), ("X_Low",  ctypes.c_uint16),
        ("Y_High", ctypes.c_uint8), ("Y_Low",  ctypes.c_uint16),
        ("Z_High", ctypes.c_uint8), ("Z_Low",  ctypes.c_uint16),
        ("W_High", ctypes.c_uint8), ("W_Low",  ctypes.c_uint16),
        ("P_High", ctypes.c_uint8), ("P_Low",  ctypes.c_uint16),
        ("R_High", ctypes.c_uint8), ("R_Low",  ctypes.c_uint16),
        ("Check_Bits", ctypes.c_uint8)
    ]

# =============================================================================
# 3. Hardware Controllers (Class Wrapper)
# =============================================================================
class FanucRobotController:
    """Wrapper for Fanuc Robot ADS Connection"""
    def __init__(self, net_id, port):
        self.net_id = net_id
        self.port = port
        self.plc = None
        self.connected = False

    def connect(self):
        try:
            self.plc = pyads.Connection(self.net_id, self.port)
            self.plc.open()
            self.connected = True
            print(f"✓ [Fanuc] Connected to Port {self.port}")
        except Exception as e:
            print(f"❌ [Fanuc] Connection Failed: {e}")
            sys.exit(1)

    def close(self):
        if self.plc: self.plc.close()

    def send_robot_command_packet(self, symbol, payload):
        if self.connected:
            self.plc.write_by_name(symbol, payload, FanucCommandPacket)

    def write_digital_signal(self, symbol, value):
        if self.connected:
            self.plc.write_by_name(symbol, value, pyads.PLCTYPE_BOOL)

    def add_device_notification(self, symbol, callback):
        attr = pyads.NotificationAttrib(ctypes.sizeof(pyads.PLCTYPE_BOOL))
        attr.nTransMode = pyads.ADSTRANS_SERVERONCHA
        attr.nCycleTime = 10000
        attr.nMaxDelay = 0
        return self.plc.add_device_notification(symbol, attr, callback)

    def del_device_notification(self, handle, symbol):
        try: self.plc.del_device_notification(handle, symbol)
        except: pass


class TurntableMotorController:
    """Wrapper for Beckhoff Motor ADS Connection"""
    def __init__(self, net_id, port):
        self.net_id = net_id
        self.port = port
        self.plc = None
        self.connected = False

    def connect(self):
        try:
            self.plc = pyads.Connection(self.net_id, self.port)
            self.plc.open()
            self.connected = True
            print(f"✓ [Motor] Connected to Port {self.port}")
        except Exception as e:
            print(f"❌ [Motor] Connection Failed: {e}")
            sys.exit(1)

    def close(self):
        if self.plc:
            self.stop_all_motors()
            self.plc.close()

    def set_servo_power(self, enabled=True):
        if not self.connected: return
        try:
            self.plc.write_list_by_name({
                'MAIN.bServoOn1': enabled, 'MAIN.bServoOn2': enabled, 'MAIN.bServoOn3': enabled
            })
            time.sleep(0.5)
            print(f"✓ [Motor] Servo {'ON' if enabled else 'OFF'}.")
        except Exception as e: print(f"⚠️ Servo Error: {e}")

    def execute_synchronized_motion(self, turntable_velocity, turntable_target_position, spindle_rotation_velocity, spindle_revolution_velocity):
        if not self.connected: return
        try:
            # 1. Reset Execute Bits
            self.plc.write_list_by_name({
                'MAIN.bMoveVel1': False, 'MAIN.bMoveVel2': False, 'MAIN.bMoveAbs3': False,
                'MAIN.bStop1': False, 'MAIN.bStop2': False, 'MAIN.bStop3': False
            })
            # 2. Set Values & Execute
            self.plc.write_list_by_name({
                'MAIN.vel3': float(turntable_velocity), 'MAIN.pos3': float(turntable_target_position), 'MAIN.bMoveAbs3': True,
                'MAIN.vel2': float(spindle_rotation_velocity)*6.0, 'MAIN.bMoveVel2': True,
                'MAIN.vel1': float(spindle_revolution_velocity)*6.0, 'MAIN.bMoveVel1': True
            })
        except Exception as e: print(f"⚠️ Motion Error: {e}")

    def stop_all_motors(self):
        if not self.connected: return
        try:
            self.plc.write_list_by_name({
                'MAIN.bMoveVel1': False, 'MAIN.bMoveVel2': False, 'MAIN.bMoveAbs3': False,
                'MAIN.bStop1': True, 'MAIN.bStop2': True, 'MAIN.bStop3': True
            })
        except: pass
    
    def add_device_notification(self, symbol, callback):
        attr = pyads.NotificationAttrib(ctypes.sizeof(pyads.PLCTYPE_BOOL))
        attr.nTransMode = pyads.ADSTRANS_SERVERONCHA
        attr.nCycleTime = 10000
        attr.nMaxDelay = 0
        return self.plc.add_device_notification(symbol, attr, callback)

    def del_device_notification(self, handle, symbol):
        try: self.plc.del_device_notification(handle, symbol)
        except: pass

# =============================================================================
# 4. Logic & Helpers
# =============================================================================
def load_sequence_file(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f.readlines()]
        if lines and lines[0] and not lines[0][0].isdigit() and not lines[0][0] == '-':
             lines = lines[1:]
        print(f"✓ [File] Loaded {len(lines)} steps.")
        return lines
    except Exception as e:
        print(f"❌ [File] Load Error: {e}"); return []

def parse_sequence_line(line):
    try:
        values = line.split()
        if len(values) >= 10:
            return {
                'turntable_velocity': float(values[0]), 
                'turntable_target_position': float(values[1]), 
                'robot_x': float(values[2]), 'robot_y': float(values[3]), 'robot_z': float(values[4]),
                'robot_w': float(values[5]), 'robot_p': float(values[6]), 'robot_r': float(values[7]), 
                'spindle_rotation_velocity': float(values[8]), 
                'spindle_revolution_velocity': float(values[9])
            }
    except: pass
    return None

def calculate_dynamic_robot_velocity(current, target, previous_robot_velocity, signals):
    # 1. Calculate Speed & Deltas
    dx, dy, dz = target['robot_x'] - current['robot_x'], target['robot_y'] - current['robot_y'], target['robot_z'] - current['robot_z']
    distance = math.sqrt(dx**2 + dy**2 + dz**2)
    delta_turntable = abs(target['turntable_target_position'] - current['turntable_target_position'])
    
    if distance < 0.001: 
        robot_velocity = 0.0
    elif delta_turntable <= 0.001: 
        robot_velocity = previous_robot_velocity if previous_robot_velocity > 0 else 100.0
    else:
        # Move time is based on turntable rotation time
        move_time = delta_turntable / target['turntable_velocity'] if target['turntable_velocity'] > 0 else 1.0
        robot_velocity = distance / max(move_time, 0.001)

    deltas = {
        'X': dx, 'Y': dy, 'Z': dz, 
        'W': target['robot_w'] - current['robot_w'], 
        'P': target['robot_p'] - current['robot_p'], 
        'R': target['robot_r'] - current['robot_r']
    }

    # 2. Pack Structure
    packet = FanucCommandPacket()
    byte1, byte2, byte3 = 0, 0, 0
    
    # Base Signals
    if signals.get('IMSP', True): byte1 |= (1<<0)
    if signals.get('Hold', True): byte1 |= (1<<1)
    if signals.get('SFSP', True): byte1 |= (1<<2)
    if signals.get('Enable', True): byte1 |= (1<<7)
    
    # RSR
    if signals.get('RSR2', False): byte2 |= (1<<1)
    
    # Trigger Signals
    if signals.get('DataReady', False): byte3 |= (1<<2) # Data Ready
    if signals.get('StartTrigger', False): byte3 |= (1<<3) # Start Trigger (Struct Embedded)
    
    # Speed & Coords
    raw_velocity = int(abs(round(robot_velocity, 3) * 1000))
    byte3 |= ((raw_velocity >> 16) & 0x0F) << 4
    
    packet.UI_Byte1 = byte1; packet.UI_Byte2 = byte2; packet.UI_Byte3 = byte3
    packet.Feed_Low = raw_velocity & 0xFFFF
    
    for i, axis in enumerate(['X','Y','Z','W','P','R']):
        val = int(abs(round(deltas.get(axis, 0), 3) * 1000))
        setattr(packet, f"{axis}_High", (val >> 16) & 0xFF)
        setattr(packet, f"{axis}_Low", val & 0xFFFF)
        if deltas.get(axis, 0) < 0: packet.Check_Bits |= (1 << i)
        
    return packet, robot_velocity

# Callbacks
def handle_calculation_request(notification, data): 
    if notification.contents.data == 1: event_calculation_request.set()
def handle_robot_motion_done(notification, data): 
    global timestamp_robot_done
    if notification.contents.data == 1: timestamp_robot_done = time.time(); event_robot_motion_done.set()
def handle_turntable_motion_done(notification, data): 
    global timestamp_turntable_done; now = time.time()
    if notification.contents.data == 1 and now > timestamp_start_step: timestamp_turntable_done = now

# =============================================================================
# 5. Sequence Logic (Worker)
# =============================================================================
def sequence_worker_thread(sequence_lines, robot_controller, motor_controller):
    global timestamp_start_step, timestamp_robot_done, timestamp_turntable_done
    print("--- [Worker] Sequence Started ---")
    
    current_pose = {
        'turntable_target_position': 0, 'robot_x': 0, 'robot_y': 0, 'robot_z': 0, 
        'robot_w': 0, 'robot_p': 0, 'robot_r': 0
    }
    previous_robot_velocity = 0.0
    handshake_signals = {
        'IMSP': True, 'Hold': True, 'SFSP': True, 'Enable': True, 
        'RSR2': True, 'DataReady': False, 'StartTrigger': False
    }

    # --- Step 1: Immediate Start (No DI44 Trigger Pulse) ---
    if sequence_lines:
        target_pose = parse_sequence_line(sequence_lines[0])
        handshake_signals['DataReady'] = True
        handshake_signals['StartTrigger'] = False # No Trigger for Step 1
        
        try:
            # 1. Send Robot Data
            packet, velocity = calculate_dynamic_robot_velocity(current_pose, target_pose, 0.0, handshake_signals)
            robot_controller.send_robot_command_packet(SYM_ROBOT_COMMAND_STRUCT, packet)
            
            # 2. Start Synchronized Servo Motion
            motor_controller.execute_synchronized_motion(
                target_pose['turntable_velocity'], 
                target_pose['turntable_target_position'], 
                target_pose['spindle_rotation_velocity'], 
                target_pose['spindle_revolution_velocity']
            )
            print("[Init] Step 1 Started (Immediate).")
            
            current_pose, previous_robot_velocity = target_pose, velocity
        except Exception as e: print(f"Init Fail: {e}"); return

    # --- Step 2+: Pipeline Loop (DI44 Trigger Handshake) ---
    for index in range(1, len(sequence_lines)):
        if sys_stop_event.is_set(): break
        
        # 1. Wait for Calculation Request (DO45)
        if not event_calculation_request.wait(30.0): print("❌ Timeout DO45 (Calculation Request)"); break
        event_calculation_request.clear()
        
        # 2. Pre-load Data (Trigger=False)
        target_pose = parse_sequence_line(sequence_lines[index])
        handshake_signals['DataReady'], handshake_signals['StartTrigger'] = True, False
        packet, velocity = calculate_dynamic_robot_velocity(current_pose, target_pose, previous_robot_velocity, handshake_signals)
        robot_controller.send_robot_command_packet(SYM_ROBOT_COMMAND_STRUCT, packet)
        print(f"[{index+1}] Target Pre-loaded.")

        # 3. Wait for Robot Motion Done (DO46)
        timestamp_start_step = time.time(); timestamp_robot_done = None; timestamp_turntable_done = None
        if not event_robot_motion_done.wait(30.0): print("❌ Timeout DO46 (Robot Motion Done)"); break
        event_robot_motion_done.clear()

        # 4. Check Turntable/Motor Sync
        if timestamp_turntable_done is None:
            t0 = time.time()
            while timestamp_turntable_done is None and (time.time()-t0 < 3.0): time.sleep(0.005)
            if timestamp_turntable_done is None: print("⚠️ Turntable/Motor Sync Timeout!")

        # 5. Trigger Simultaneous Start (Trigger=True + Motor Execute)
        handshake_signals['StartTrigger'] = True
        packet_trigger, _ = calculate_dynamic_robot_velocity(current_pose, target_pose, previous_robot_velocity, handshake_signals)
        robot_controller.send_robot_command_packet(SYM_ROBOT_COMMAND_STRUCT, packet_trigger) # Trigger
        
        motor_controller.execute_synchronized_motion(
            target_pose['turntable_velocity'], 
            target_pose['turntable_target_position'], 
            target_pose['spindle_rotation_velocity'], 
            target_pose['spindle_revolution_velocity']
        )
        
        # Pulse Reset
        robot_controller.write_digital_signal(SYM_SYNC_START_TRIGGER, False) 
        
        print(f" -> Step {index+1} Triggered.")
        current_pose, previous_robot_velocity = target_pose, velocity

    # --- Finish ---
    if not sys_stop_event.is_set():
        print("--- All Sequences Finished ---")
        handshake_signals.update({'RSR2':False, 'DataReady':False, 'StartTrigger':False})
        packet_finish, _ = calculate_dynamic_robot_velocity(current_pose, {k:0 for k in current_pose}, 0, handshake_signals)
        robot_controller.send_robot_command_packet(SYM_ROBOT_COMMAND_STRUCT, packet_finish)
        robot_controller.write_digital_signal(SYM_SYNC_START_TRIGGER, False)

# =============================================================================
# 6. Main Execution Flow
# =============================================================================
def main():
    # 1. Initialize Objects
    print("\n[1] Initializing Handshake System...")
    robot = FanucRobotController(AMS_NET_ID, FANUC_PORT)
    motor = TurntableMotorController(AMS_NET_ID, MOTOR_PORT)
    
    # 2. Connect All
    print("[2] Connecting Hardware Connections...")
    robot.connect()
    motor.connect()
    
    # 3. Setup & Load
    print("[3] Sequence Setup...")
    motor.set_servo_power(True)
    sequence_lines = load_sequence_file("Fanuc_seq.txt")
    if not sequence_lines: return

    # 4. Setup Notifications (Handshake Monitoring)
    handle_calc = robot.add_device_notification(SYM_CALC_REQUEST, handle_calculation_request)
    handle_motion = robot.add_device_notification(SYM_ROBOT_MOTION_DONE, handle_robot_motion_done)
    handle_turntable = motor.add_device_notification(SYM_TURNTABLE_MOTION_DONE, handle_turntable_motion_done)

    # 5. Start Worker Thread
    worker = threading.Thread(target=sequence_worker_thread, args=(sequence_lines, robot, motor), daemon=True)
    worker.start()
    
    print("\n✅ Synchronization System Running. Press Ctrl+C to STOP.\n")

    # 6. Monitor Loop (E-Stop)
    try:
        while worker.is_alive(): time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n!!! EMERGENCY STOP TRIGGERED !!!")
        sys_stop_event.set()
        event_calculation_request.set(); event_robot_motion_done.set()
        
        # Stop Commands
        estop_signals = {'IMSP':True, 'Enable':False, 'CycleStop':True, 'RSR2':False}
        # Zero payload for safety
        estop_payload = FanucCommandPacket() 
        estop_payload.UI_Byte1 = 0b00001111 # IMSP, Hold, SFSP, CycleStop
        robot.send_robot_command_packet(SYM_ROBOT_COMMAND_STRUCT, estop_payload)
        robot.write_digital_signal(SYM_SYNC_START_TRIGGER, False)
        motor.stop_all_motors()
        
        worker.join(1.0)

    # 7. Cleanup Hardware
    finally:
        robot.del_device_notification(handle_calc, SYM_CALC_REQUEST)
        robot.del_device_notification(handle_motion, SYM_ROBOT_MOTION_DONE)
        motor.del_device_notification(handle_turntable, SYM_TURNTABLE_MOTION_DONE)
        robot.close()
        motor.close()
        print("Hardware Disconnected.")

if __name__ == '__main__':
    main()
