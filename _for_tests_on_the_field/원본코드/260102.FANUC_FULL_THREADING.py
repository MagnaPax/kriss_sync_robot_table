"""
FANUC Robot Control via Beckhoff ADS (Rising Edge Trigger)
- Feature: Triggers only when DO45 changes from FALSE to TRUE (Rising Edge).
- Fixes: 'Parameter size' error and 'Event object' error included.
"""

import pyads
import ctypes
import time
import msvcrt
import sys
import threading
import math

# [전역 변수] 이벤트 객체
move_next_event = threading.Event()

# =============================================================================
# 1. 구조체 정의 (Padding 제거됨 - 24Byte)
# =============================================================================
class FanucUI1Struct(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("UI_Byte1", ctypes.c_uint8),
        ("UI_Byte2", ctypes.c_uint8),
        ("UI_Byte3", ctypes.c_uint8),
        ("Feed_Low", ctypes.c_uint16),
        ("X_High", ctypes.c_uint8), ("X_Low",  ctypes.c_uint16),
        ("Y_High", ctypes.c_uint8), ("Y_Low",  ctypes.c_uint16),
        ("Z_High", ctypes.c_uint8), ("Z_Low",  ctypes.c_uint16),
        ("W_High", ctypes.c_uint8), ("W_Low",  ctypes.c_uint16),
        ("P_High", ctypes.c_uint8), ("P_Low",  ctypes.c_uint16),
        ("R_High", ctypes.c_uint8), ("R_Low",  ctypes.c_uint16),
        ("Check_Bits", ctypes.c_uint8)
        # ("Padding", ctypes.c_uint8 * 8) # 삭제됨 (24바이트 맞춤)
    ]

# =============================================================================
# 2. 헬퍼 함수
# =============================================================================
def calculate_distance(current_pos, target_pos):
    if current_pos is None: return 0.0, 0.0
    dx = target_pos['X'] - current_pos['X']
    dy = target_pos['Y'] - current_pos['Y']
    dz = target_pos['Z'] - current_pos['Z']
    dist_xyz = math.sqrt(dx**2 + dy**2 + dz**2)
    dw = abs(target_pos['W'] - current_pos['W'])
    dp = abs(target_pos['P'] - current_pos['P'])
    dr = abs(target_pos['R'] - current_pos['R'])
    rot_max = max(dw, dp, dr)
    return dist_xyz, rot_max

def load_file(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f.readlines()[1:]]
        print(f"✓ File Loaded: {len(lines)} steps.")
        return lines
    except Exception as e:
        print(f"❌ File Load Error: {e}")
        return []

def parse_line(line):
    try:
        v = line.split()
        if len(v) >= 7:
            return {'F': float(v[0]), 'X': float(v[1]), 'Y': float(v[2]),
                    'Z': float(v[3]), 'W': float(v[4]), 'P': float(v[5]), 'R': float(v[6])}
    except ValueError:
        pass
    return None

def pack_fanuc_payload(coords, deltas, signals):
    payload = FanucUI1Struct()
    
    b1 = 0
    if signals.get('IMSP', True):      b1 |= (1 << 0)
    if signals.get('Hold', True):      b1 |= (1 << 1)
    if signals.get('SFSP', True):      b1 |= (1 << 2)
    if signals.get('CycleStop', False): b1 |= (1 << 3)
    if signals.get('FaultReset', False):b1 |= (1 << 4)
    if signals.get('Start', False):     b1 |= (1 << 5)
    if signals.get('Home', False):      b1 |= (1 << 6)
    if signals.get('Enable', True):     b1 |= (1 << 7)
    payload.UI_Byte1 = b1

    b2 = 0
    if signals.get('RSR1', False): b2 |= (1 << 0)
    if signals.get('RSR2', False): b2 |= (1 << 1)
    payload.UI_Byte2 = b2

    b3 = 0
    if signals.get('PNSStrobe', False): b3 |= (1 << 0)
    if signals.get('ProdStart', False): b3 |= (1 << 1)
    if signals.get('DI43', False):      b3 |= (1 << 2)
    if signals.get('DI44', False):      b3 |= (1 << 3)
    raw_F = int(abs(round(coords.get('F', 0), 3) * 1000))
    feed_high = (raw_F >> 16) & 0x0F
    b3 |= (feed_high << 4)

    payload.UI_Byte3 = b3
    payload.Feed_Low = raw_F & 0xFFFF

    axes = ['X', 'Y', 'Z', 'W', 'P', 'R']
    check_byte = 0
    for i, axis in enumerate(axes):
        val = deltas.get(axis, 0.0)
        int_val = int(abs(round(val, 3) * 1000))
        setattr(payload, f"{axis}_High", (int_val >> 16) & 0xFF)
        setattr(payload, f"{axis}_Low", int_val & 0xFFFF)
        if val < 0: check_byte |= (1 << i)
    payload.Check_Bits = check_byte
    return payload

# =============================================================================
# [핵심 수정] Rising Edge(False->True) 감지 로직 추가
# =============================================================================
def on_handshake_change(notification, data):
    """
    PLC 신호가 변경될 때 호출됨.
    notification.contents.data 값이 1(True)일 때만 이벤트를 발생시킴.
    """
    # notification.contents.data는 c_ubyte 타입이므로 값(0 또는 1)을 직접 확인
    current_value = notification.contents.data
    
    if current_value == 1: # TRUE (Rising Edge)
        move_next_event.set()
    else:
        # FALSE (Falling Edge) - 무시함
        pass

# =============================================================================
# 3. 메인 실행
# =============================================================================
def main():
    AMS_NET_ID = '192.168.0.196.1.1' #5.119.154.174.1.1
    STRUCT_SYMBOL = "MAIN.Robot1._UI1"
    HANDSHAKE_SYMBOL = "MAIN.Robot1._UO1.DO45"
    
    LIMIT_XYZ_MM = 150.0 
    LIMIT_WPR_DEG = 30.0

    print(f"Connecting to {AMS_NET_ID}...")
    try:
        plc = pyads.Connection(AMS_NET_ID, 852)
        plc.open()
        print(f"✓ Connected. State: {plc.read_state()}")
    except Exception as e:
        print(f"❌ Connection Failed: {e}")
        sys.exit(1)

    lines = load_file("Fanuc_seq.txt")
    if not lines:
        plc.close()
        sys.exit(1)

    # --- Notification Setup ---
    print("Setting up ADS Notification (Rising Edge)...")
    attr = pyads.NotificationAttrib(ctypes.sizeof(pyads.PLCTYPE_BOOL))
    attr.nTransMode = pyads.ADSTRANS_SERVERONCHA
    attr.nCycleTime = 100000 
    attr.nMaxDelay = 0

    try:
        # user_handle 제거됨 (전역 변수 사용)
        h_notify = plc.add_device_notification(HANDSHAKE_SYMBOL, attr, on_handshake_change)
    except Exception as e:
        print(f"❌ Notification Setup Failed: {e}")
        plc.close()
        sys.exit(1)

    print("\n--- Initializing Robot ---")
    current_coords = {'F': 0}
    prev_coords = {'F': 0, 'X': 0.0, 'Y': 0.0, 'Z': 0.0, 'W': 0.0, 'P': 0.0, 'R': 0.0}
    zero_deltas = {k:0.0 for k in ['X','Y','Z','W','P','R']}
    
    base_signals = {
        'IMSP': True, 'Hold': True, 'SFSP': True, 'Enable': True,
        'CycleStop': False, 'Start': False, 'RSR2': False, 'DI43': False
    }
    
    init_payload = pack_fanuc_payload(current_coords, zero_deltas, base_signals)
    
    # 3번째 인자(구조체 타입) 필수
    plc.write_by_name(STRUCT_SYMBOL, init_payload, FanucUI1Struct)
    
    time.sleep(1.0)

    print("--- Sequence Start (Ctrl+C to Stop) ---")
   

    try:
        for i, line in enumerate(lines, 1):
            target_coords = parse_line(line)
            if not target_coords: continue

            if prev_coords is None:
                move_deltas = zero_deltas.copy()
            else:
                dist, rot = calculate_distance(prev_coords, target_coords)
                if dist > LIMIT_XYZ_MM or rot > LIMIT_WPR_DEG:
                    print(f"\n❌ SAFETY STOP: Jump too large ({dist:.1f}mm)")
                    raise KeyboardInterrupt
                move_deltas = {k: target_coords[k] - prev_coords[k] for k in zero_deltas}

            signals = base_signals.copy()
            signals['DI43'] = True 
            if i == 1: signals['RSR2'] = True

            payload = pack_fanuc_payload(target_coords, move_deltas, signals)
            
            # 구조체 타입 명시
            plc.write_by_name(STRUCT_SYMBOL, payload, FanucUI1Struct)
            
            print(f"[{i}/{len(lines)}] Sent F:{target_coords['F']} | Wait for Rising Edge...", end="")
            sys.stdout.flush()

            # Rising Edge(True)가 될 때까지 대기
            if move_next_event.wait(timeout=20.0): # 타임아웃 넉넉하게 20초
                move_next_event.clear()
                print(" -> OK")
            else:
                print(" -> ❌ TIMEOUT! (No Rising Edge detected)")
                break

            prev_coords = target_coords

            if i == 1:
                signals['RSR2'] = False
                payload = pack_fanuc_payload(target_coords, move_deltas, signals)
                plc.write_by_name(STRUCT_SYMBOL, payload, FanucUI1Struct)

    except KeyboardInterrupt:
        print("\n\n!!! EMERGENCY STOP !!!")
        estop_signals = base_signals.copy()
        estop_signals['CycleStop'] = True
        estop_signals['DI43'] = False
        estop_signals['Enable'] = False
        
        estop_payload = pack_fanuc_payload({'F':0}, zero_deltas, estop_signals)
        plc.write_by_name(STRUCT_SYMBOL, estop_payload, FanucUI1Struct)
        
        print(">> Cycle Stop Command Sent.")

    finally:
        print("Cleaning up...")
        try:
            plc.del_device_notification(h_notify, HANDSHAKE_SYMBOL)
        except:
            pass
        plc.close()
        print("Disconnected.")

if __name__ == '__main__':
    main()