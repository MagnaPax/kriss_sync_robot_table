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
SYM_STRUCT     = "MAIN.Robot1._UI1"
SYM_DI44       = "MAIN.Robot1._UI1.DI44" # Start Trigger
SYM_DO45       = "MAIN.Robot1._UO1.DO45" # Calc Request
SYM_DO46       = "MAIN.Robot1._UO1.DO46" # Motion Done
SYM_MOTOR_DONE = "MAIN.bDone3"           # Motor Done

# [Events]
event_calc_req    = threading.Event()
event_motion_done = threading.Event()
sys_stop_event    = threading.Event()

# [Sync Status]
ts_start_step = 0.0
ts_robot_done = 0.0
ts_motor_done = 0.0

# =============================================================================
# 2. Data Structures
# =============================================================================
class FanucUI1Struct(ctypes.Structure):
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
class FanucController:
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

    def write_struct(self, symbol, payload):
        if self.connected:
            self.plc.write_by_name(symbol, payload, FanucUI1Struct)

    def write_bit(self, symbol, value):
        if self.connected:
            self.plc.write_by_name(symbol, value, pyads.PLCTYPE_BOOL)

    def add_notification(self, symbol, callback):
        attr = pyads.NotificationAttrib(ctypes.sizeof(pyads.PLCTYPE_BOOL))
        attr.nTransMode = pyads.ADSTRANS_SERVERONCHA
        attr.nCycleTime = 10000
        attr.nMaxDelay = 0
        return self.plc.add_device_notification(symbol, attr, callback)

    def del_notification(self, handle, symbol):
        try: self.plc.del_device_notification(handle, symbol)
        except: pass


class MotorController:
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
            self.stop_all()
            self.plc.close()

    def servo_on(self, state=True):
        if not self.connected: return
        try:
            self.plc.write_list_by_name({
                'MAIN.bServoOn1': state, 'MAIN.bServoOn2': state, 'MAIN.bServoOn3': state
            })
            time.sleep(0.5)
            print(f"✓ [Motor] Servo {'ON' if state else 'OFF'}.")
        except Exception as e: print(f"⚠️ Servo Error: {e}")

    def execute_motion_batch(self, f, t, m2, m3):
        if not self.connected: return
        try:
            # 1. Reset Execute Bits
            self.plc.write_list_by_name({
                'MAIN.bMoveVel1': False, 'MAIN.bMoveVel2': False, 'MAIN.bMoveAbs3': False,
                'MAIN.bStop1': False, 'MAIN.bStop2': False, 'MAIN.bStop3': False
            })
            # 2. Set Values & Execute
            self.plc.write_list_by_name({
                'MAIN.vel3': float(f), 'MAIN.pos3': float(t), 'MAIN.bMoveAbs3': True,
                'MAIN.vel2': float(m2)*6.0, 'MAIN.bMoveVel2': True,
                'MAIN.vel1': float(m3)*6.0, 'MAIN.bMoveVel1': True
            })
        except Exception as e: print(f"⚠️ Motion Error: {e}")

    def stop_all(self):
        if not self.connected: return
        try:
            self.plc.write_list_by_name({
                'MAIN.bMoveVel1': False, 'MAIN.bMoveVel2': False, 'MAIN.bMoveAbs3': False,
                'MAIN.bStop1': True, 'MAIN.bStop2': True, 'MAIN.bStop3': True
            })
        except: pass
    
    def add_notification(self, symbol, callback):
        attr = pyads.NotificationAttrib(ctypes.sizeof(pyads.PLCTYPE_BOOL))
        attr.nTransMode = pyads.ADSTRANS_SERVERONCHA
        attr.nCycleTime = 10000
        attr.nMaxDelay = 0
        return self.plc.add_device_notification(symbol, attr, callback)

    def del_notification(self, handle, symbol):
        try: self.plc.del_device_notification(handle, symbol)
        except: pass

# =============================================================================
# 4. Logic & Helpers
# =============================================================================
def load_file(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f.readlines()]
        if lines and lines[0] and not lines[0][0].isdigit() and not lines[0][0] == '-':
             lines = lines[1:]
        print(f"✓ [File] Loaded {len(lines)} steps.")
        return lines
    except Exception as e:
        print(f"❌ [File] Load Error: {e}"); return []

def parse_line(line):
    try:
        v = line.split()
        if len(v) >= 10:
            return {'F':float(v[0]), 'T':float(v[1]), 'X':float(v[2]), 'Y':float(v[3]), 'Z':float(v[4]),
                    'W':float(v[5]), 'P':float(v[6]), 'R':float(v[7]), 'M2_Val':float(v[8]), 'M3_Val':float(v[9])}
    except: pass
    return None

def calc_speed_and_pack(current, target, prev_f, signals):
    # 1. Calculate Speed & Deltas
    dx, dy, dz = target['X']-current['X'], target['Y']-current['Y'], target['Z']-current['Z']
    dist = math.sqrt(dx**2 + dy**2 + dz**2)
    dt = abs(target['T'] - current['T'])
    
    if dist < 0.001: robot_f = 0.0
    elif dt <= 0.001: robot_f = prev_f if prev_f > 0 else 100.0
    else:
        move_time = dt / target['F'] if target['F'] > 0 else 1.0
        robot_f = dist / max(move_time, 0.001)

    deltas = {'X':dx, 'Y':dy, 'Z':dz, 'W':target['W']-current['W'], 'P':target['P']-current['P'], 'R':target['R']-current['R']}

    # 2. Pack Structure
    payload = FanucUI1Struct()
    b1, b2, b3 = 0, 0, 0
    
    # Base Signals
    if signals.get('IMSP', True): b1 |= (1<<0)
    if signals.get('Hold', True): b1 |= (1<<1)
    if signals.get('SFSP', True): b1 |= (1<<2)
    if signals.get('Enable', True): b1 |= (1<<7)
    
    # RSR
    if signals.get('RSR2', False): b2 |= (1<<1)
    
    # Trigger Signals
    if signals.get('DI43', False): b3 |= (1<<2) # Data Ready
    if signals.get('DI44', False): b3 |= (1<<3) # Start Trigger (Struct Embedded)
    
    # Speed & Coords
    raw_F = int(abs(round(robot_f, 3) * 1000))
    b3 |= ((raw_F >> 16) & 0x0F) << 4
    
    payload.UI_Byte1 = b1; payload.UI_Byte2 = b2; payload.UI_Byte3 = b3
    payload.Feed_Low = raw_F & 0xFFFF
    
    for i, axis in enumerate(['X','Y','Z','W','P','R']):
        val = int(abs(round(deltas.get(axis,0), 3) * 1000))
        setattr(payload, f"{axis}_High", (val >> 16) & 0xFF)
        setattr(payload, f"{axis}_Low", val & 0xFFFF)
        if deltas.get(axis,0) < 0: payload.Check_Bits |= (1 << i)
        
    return payload, robot_f

# Callbacks
def cb_calc_req(n, d): 
    if n.contents.data == 1: event_calc_req.set()
def cb_motion_done(n, d): 
    global ts_robot_done
    if n.contents.data == 1: ts_robot_done = time.time(); event_motion_done.set()
def cb_motor_done(n, d): 
    global ts_motor_done; now = time.time()
    if n.contents.data == 1 and now > ts_start_step: ts_motor_done = now

# =============================================================================
# 5. Sequence Logic (Worker)
# =============================================================================
def sequence_worker(lines, robot, motor):
    global ts_start_step, ts_robot_done, ts_motor_done
    print("--- [Worker] Sequence Started ---")
    
    curr = {'F':0, 'T':0, 'X':0, 'Y':0, 'Z':0, 'W':0, 'P':0, 'R':0}
    prev_f = 0.0
    sig = {'IMSP':True, 'Hold':True, 'SFSP':True, 'Enable':True, 'RSR2':True, 'DI43':False, 'DI44':False}

    # --- Step 1: Immediate Start (No DI44) ---
    if lines:
        tgt = parse_line(lines[0])
        sig['DI43'] = True
        sig['DI44'] = False # No Trigger for Step 1
        
        try:
            # 1. Send Data
            payload, f = calc_speed_and_pack(curr, tgt, 0.0, sig)
            robot.write_struct(SYM_STRUCT, payload)
            
            # 2. Start Motor Immediately
            motor.execute_motion_batch(tgt['F'], tgt['T'], tgt['M2_Val'], tgt['M3_Val'])
            print("[Init] Step 1 Started (Immediate).")
            
            curr, prev_f = tgt, f
        except Exception as e: print(f"Init Fail: {e}"); return

    # --- Step 2+: Pipeline Loop (DI44 Trigger) ---
    for i in range(1, len(lines)):
        if sys_stop_event.is_set(): break
        
        # 1. Wait for Calc Request (DO45)
        if not event_calc_req.wait(30.0): print("❌ Timeout DO45"); break
        event_calc_req.clear()
        
        # 2. Pre-load Data (DI44=False)
        tgt = parse_line(lines[i])
        sig['DI43'], sig['DI44'] = True, False
        payload, f = calc_speed_and_pack(curr, tgt, prev_f, sig)
        robot.write_struct(SYM_STRUCT, payload)
        print(f"[{i+1}] Pre-loaded.")

        # 3. Wait for Motion Done (DO46)
        ts_start_step = time.time(); ts_robot_done = None; ts_motor_done = None
        if not event_motion_done.wait(30.0): print("❌ Timeout DO46"); break
        event_motion_done.clear()

        # 4. Check Motor Sync
        if ts_motor_done is None:
            t0 = time.time()
            while ts_motor_done is None and (time.time()-t0 < 3.0): time.sleep(0.005)
            if ts_motor_done is None: print("⚠️ Motor Sync Timeout!")

        # 5. Trigger Next Motion (DI44=True + Motor)
        sig['DI44'] = True
        payload, _ = calc_speed_and_pack(curr, tgt, prev_f, sig)
        robot.write_struct(SYM_STRUCT, payload) # Trigger
        motor.execute_motion_batch(tgt['F'], tgt['T'], tgt['M2_Val'], tgt['M3_Val'])
        robot.write_bit(SYM_DI44, False) # Reset Pulse
        
        print(f" -> Step {i+1} Triggered.")
        curr, prev_f = tgt, f

    # --- Finish ---
    if not sys_stop_event.is_set():
        print("--- Finished ---")
        sig.update({'RSR2':False, 'DI43':False, 'DI44':False})
        payload, _ = calc_speed_and_pack(curr, {k:0 for k in curr}, 0, sig)
        robot.write_struct(SYM_STRUCT, payload)
        robot.write_bit(SYM_DI44, False)

# =============================================================================
# 6. Main Execution Flow
# =============================================================================
def main():
    # 1. Initialize Objects
    print("\n[1] Initializing System...")
    robot = FanucController(AMS_NET_ID, FANUC_PORT)
    motor = MotorController(AMS_NET_ID, MOTOR_PORT)
    
    # 2. Connect All
    print("[2] Connecting Hardware...")
    robot.connect()
    motor.connect()
    
    # 3. Setup & Load
    print("[3] Setup...")
    motor.servo_on(True)
    lines = load_file("Fanuc_seq.txt")
    if not lines: return

    # 4. Setup Notifications (Grouped)
    h_n1 = robot.add_notification(SYM_DO45, cb_calc_req)
    h_n2 = robot.add_notification(SYM_DO46, cb_motion_done)
    h_n3 = motor.add_notification(SYM_MOTOR_DONE, cb_motor_done)

    # 5. Start Worker
    worker = threading.Thread(target=sequence_worker, args=(lines, robot, motor), daemon=True)
    worker.start()
    
    print("\n✅ System Running. Press Ctrl+C to STOP.\n")

    # 6. Monitor Loop (E-Stop)
    try:
        while worker.is_alive(): time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n!!! EMERGENCY STOP !!!")
        sys_stop_event.set()
        event_calc_req.set(); event_motion_done.set()
        
        # Stop Commands
        stop_sig = {'IMSP':True, 'Enable':False, 'CycleStop':True, 'RSR2':False}
        zero = {k:0 for k in ['X','Y','Z','W','P','R']}
        
        payload = FanucUI1Struct() # Simplified estop pack
        # (For brevity, assuming calc_speed_and_pack handles basic estop signals correctly)
        # Using manual payload creation for absolute safety in E-Stop
        payload.UI_Byte1 = 0b00001111 # IMSP, Hold, SFSP, CycleStop
        robot.write_struct(SYM_STRUCT, payload)
        robot.write_bit(SYM_DI44, False)
        motor.stop_all()
        
        worker.join(1.0)

    # 7. Cleanup
    finally:
        robot.del_notification(h_n1, SYM_DO45)
        robot.del_notification(h_n2, SYM_DO46)
        motor.del_notification(h_n3, SYM_MOTOR_DONE)
        robot.close()
        motor.close()
        print("Disconnected.")

if __name__ == '__main__':
    main()