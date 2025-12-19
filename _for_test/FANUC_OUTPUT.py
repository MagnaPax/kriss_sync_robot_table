"""
FANUC Robot으로부터 좌표값 받아오기(World)
"""

import pyads
import time

# 로봇->PLC(출력) 부호 판별
SIGN_BIT_MAP1 = {
    "X" : "MAIN.Robot1._UO1.X_Check",
    "Y" : "MAIN.Robot1._UO1.Y_Check",
    "Z" : "MAIN.Robot1._UO1.Z_Check",
    "W" : "MAIN.Robot1._UO1.W_Check",
    "P" : "MAIN.Robot1._UO1.P_Check",
    "R" : "MAIN.Robot1._UO1.R_Check",
}
# PLC->로봇(입력력) 부호 판별
SIGN_BIT_MAP2 = {
    "X" : "MAIN.Robot1._UI1.X_Check",
    "Y" : "MAIN.Robot1._UI1.Y_Check",
    "Z" : "MAIN.Robot1._UI1.Z_Check",
    "W" : "MAIN.Robot1._UI1.W_Check",
    "P" : "MAIN.Robot1._UI1.P_Check",
    "R" : "MAIN.Robot1._UI1.R_Check",
}

# PLC 연결
def connect_plc():
    try:
        plc = pyads.Connection('5.119.154.174.1.1', pyads.PORT_TC3PLC1) # 5.119.154.174.1.1 / 192.168.0.196.1.1
        plc.open()
        plc.read_state()
        print("✓ PLC 연결")
        return plc
    except Exception as e:
        print(f"❌ PLC 연결 실패: {e}")
        exit(1)

# 로봇->PLC 출력 좌표 정보 정수화 및 Display
def receive_bits(plc, axis_name):
    axis_name = axis_name.upper()

    if axis_name not in SIGN_BIT_MAP1:
        raise ValueError(f"Unknown axis name: {axis_name}")
    
    sign_bit_name = SIGN_BIT_MAP1[axis_name]

    top_value = 0
    bot_value = 0

    for i in range(8):
        bit = plc.read_by_name(f'MAIN.Robot1._UO1.{axis_name}h{i}', pyads.PLCTYPE_BOOL)
        top_value += (1 << i) * bit
    for j in range(16):
        bit = plc.read_by_name(f'MAIN.Robot1._UO1.{axis_name}l{j}', pyads.PLCTYPE_BOOL)
        bot_value += (1 << j) * bit

    raw_value = (top_value << 16) + bot_value

    sign = plc.read_by_name(sign_bit_name, pyads.PLCTYPE_BOOL)

    axis_value = raw_value / 1000
    if sign:
        axis_value = -axis_value

    return round(axis_value, 3)

# PLC->로봇 입력 좌표 정보 정수화 및 Display
def target_bits(plc, axis_name):
    axis_name = axis_name.upper()

    if axis_name not in SIGN_BIT_MAP2:
        raise ValueError(f"Unknown axis name: {axis_name}")
    
    sign_bit_name = SIGN_BIT_MAP2[axis_name]

    top_value = 0
    bot_value = 0

    for i in range(8):
        bit = plc.read_by_name(f'MAIN.Robot1._UI1.{axis_name}h{i}', pyads.PLCTYPE_BOOL)
        top_value += (1 << i) * bit
    for j in range(16):
        bit = plc.read_by_name(f'MAIN.Robot1._UI1.{axis_name}l{j}', pyads.PLCTYPE_BOOL)
        bot_value += (1 << j) * bit

    raw_value = (top_value << 16) + bot_value

    sign = plc.read_by_name(sign_bit_name, pyads.PLCTYPE_BOOL)

    axis_value = raw_value / 1000
    if sign:
        axis_value = -axis_value

    return round(axis_value, 3)


def main():
    try:
        plc = connect_plc()
        while True:
            # recevie_bits
            X_Value = receive_bits(plc, "X")
            Y_Value = receive_bits(plc, "Y")
            Z_Value = receive_bits(plc, "Z")
            W_Value = receive_bits(plc, "W")
            P_Value = receive_bits(plc, "P")
            R_Value = receive_bits(plc, "R")
            T_X_Value = target_bits(plc, "X")
            T_Y_Value = target_bits(plc, "Y")
            T_Z_Value = target_bits(plc, "Z")
            T_W_Value = target_bits(plc, "W")
            T_P_Value = target_bits(plc, "P")
            T_R_Value = target_bits(plc, "R")

            print(
                f"   World Position\tTarget Position\n"
                f"X: {X_Value:<9}mm\t\t{T_X_Value:<9}mm\n"
                f"Y: {Y_Value:<9}mm\t\t{T_Y_Value:<9}mm\n"
                f"Z: {Z_Value:<9}mm\t\t{T_Z_Value:<9}mm\n"
                f"W: {W_Value:<9}deg\t\t{T_W_Value:<9}deg\n"
                f"P: {P_Value:<9}deg\t\t{T_P_Value:<9}deg\n"
                f"R: {R_Value:<9}deg\t\t{T_R_Value:<9}deg"
            )

            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\n사용자에 의해 종료됨.")

if __name__ == '__main__':
    main()