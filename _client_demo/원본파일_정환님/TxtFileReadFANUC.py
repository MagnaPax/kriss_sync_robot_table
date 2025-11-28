"""
Fanuc 좌표 자동 전송 - 간소서화 버전
좌표 그 자체를 전송에서 이전 값과의 차이를 보내는 방식으로 변경(TP Program도 차이만큼 이동하도록 변경함).
RSR/ACK 핸드셰이킹으로 좌표 자동 전송 -> RSR신호 ON/OFF 반복은 좋지 못한 방법이므로, 1회의 Pulse를 주고 TP Program 내에서 루프가 실행되도록 수정.
UO10_Busy 신호를 사용하여 좌표 수신과 대기 타이밍 확인.
DI81이 ON이면 루프를 계속 수행하고 DI81이 OFF이면 루프를 탈출하여 TP Program 종료.
"""

import pyads
import time
import threading

# PLC 연결
try:
    plc = pyads.Connection('5.119.154.174.1.1', pyads.PORT_TC3PLC1)
    plc.open()
    plc.read_state()
    print("✓ PLC 연결")
except Exception as e:
    print(f"❌ PLC 연결 실패: {e}")
    exit(1)


def send_bits_to_plc(plc, prefix, lower_value, high_value):
    """비트 전송"""
    for i in range(8):
        plc.write_by_name(f'MAIN.Robot1._UI1.{prefix}l{i}', 
                         (lower_value & (1 << i)) > 0, pyads.PLCTYPE_BOOL)
        plc.write_by_name(f'MAIN.Robot1._UI1.{prefix}h{i}', 
                         (high_value & (1 << i)) > 0, pyads.PLCTYPE_BOOL)


def send_coordinate(input_val, axis_name):
    """좌표 전송 (소숫점 둘째자리까지만)"""
    # 소숫점 둘째자리로 반올림
    rounded_val = round(input_val, 2)
    scaled = int(abs(rounded_val * 100))
    send_bits_to_plc(plc, axis_name, scaled & 0xFF, scaled >> 8)
    plc.write_by_name(f'MAIN.Robot1._UI1.{axis_name}_Check', 
                     rounded_val < 0, pyads.PLCTYPE_BOOL)


def send_feed(input_F):
    """Feed 전송 (소숫점 둘째자리까지만)"""
    # 소숫점 둘째자리로 반올림
    rounded_F = round(input_F, 2)
    scaled_F = int(abs(rounded_F * 100))
    for i in range(8):
        plc.write_by_name(f'MAIN.Robot1._UI1.Fl{i}', 
                         (scaled_F & (1 << i)) > 0, pyads.PLCTYPE_BOOL)
    for i in range(2):
        plc.write_by_name(f'MAIN.Robot1._UI1.Fh{i}', 
                         ((scaled_F >> 8) & (1 << i)) > 0, pyads.PLCTYPE_BOOL)


def load_file(filename):
    """파일 로드"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f.readlines()[1:]]  # 헤더 제외
        print(f"✓ 파일 로드: {len(lines)}줄")
        return lines
    except Exception as e:
        print(f"❌ 파일 오류: {e}")
        exit(1)


def parse_line(line):
    """줄 파싱"""
    values = line.split()
    if len(values) >= 7:
        return {
            'F': float(values[0]), 'X': float(values[1]), 'Y': float(values[2]),
            'Z': float(values[3]), 'W': float(values[4]), 'P': float(values[5]),
            'R': float(values[6])
        }
    return None


def stop_start(stop, start):
    """정지 및 시작"""
    if stop:
        print("Cycle Stop")
        plc.write_by_name('MAIN.Robot1._UI1.UI04_CycleStop', True, pyads.PLCTYPE_BOOL)
        time.sleep(0.1)
        plc.write_by_name('MAIN.Robot1._UI1.UI04_CycleStop', False, pyads.PLCTYPE_BOOL)

    if start:
        print("Cycle Start")
        plc.write_by_name('MAIN.Robot1._UI1.UI06_Start', True, pyads.PLCTYPE_BOOL)
        time.sleep(0.1)
        plc.write_by_name('MAIN.Robot1._UI1.UI06_Start', False, pyads.PLCTYPE_BOOL)


def user_input_thread():
    while True:
        command = input("정지(S), 시작(G): ").strip().upper()
        if command == "S":
            stop_start(True, False)
        elif command == "G":
            stop_start(False, True)
        else:
            print("잘못된 명령")


def main():
    # 파일 로드
    filename = input("파일명 (기본: Fanuc_seq.txt): ").strip() or "Fanuc_seq.txt"
    lines = load_file(filename)
    
    print(f"\n시작 (총 {len(lines)}줄)\n")

    # RSR신호 Pulse
    print("TP Program Start")
    plc.write_by_name('MAIN.Robot1._UI1.UI09_RSR1', True, pyads.PLCTYPE_BOOL)   # MAIN.Robot1._UI1.UI09_RSR1 = RSR0001 / MAIN.Robot1._UI1.UI10_RSR2 = RSR0002
    time.sleep(0.05)
    plc.write_by_name('MAIN.Robot1._UI1.UI09_RSR1', False, pyads.PLCTYPE_BOOL)
    time.sleep(0.05)

    # Loop신호(ON이면 루프 반복, OFF이면 루프 종료)
    plc.write_by_name('MAIN.Robot1._UI1.DI81', True, pyads.PLCTYPE_BOOL)
    
    previous_coords = None

    # stop_start thread
    input_thread = threading.Thread(target=user_input_thread, daemon=True)
    input_thread.start()

    try:
        for i, line in enumerate(lines, 1):
            coords = parse_line(line)
            if not coords:
                continue

            # 이전 값 저장 
            if previous_coords is None:
                deltas = coords.copy()
            else:
                deltas = {key: coords[key] - previous_coords[key] for key in coords.keys()}

            previous_coords = coords
                      
            # Feed를 제외한 이전 값과의 차이를 출력 
            print(f"[{i}/{len(lines)}] F={coords['F']:.2f} ΔX={deltas['X']:.2f} "
                  f"ΔY={deltas['Y']:.2f} ΔZ={deltas['Z']:.2f} ΔW={deltas['W']:.2f} "
                  f"ΔP={deltas['P']:.2f} ΔR={deltas['R']:.2f}", end=" ")

            # 좌표 전송
            send_feed(coords['F'])
            send_coordinate(deltas['X'], "X")
            send_coordinate(deltas['Y'], "Y")
            send_coordinate(deltas['Z'], "Z")
            send_coordinate(deltas['W'], "W")
            send_coordinate(deltas['P'], "P")
            send_coordinate(deltas['R'], "R")
            
            # UO10_Busy신호가 False->True로 될 때까지 기다림 
            while not plc.read_by_name('MAIN.Robot1._UO1.UO10_Busy', pyads.PLCTYPE_BOOL):
                time.sleep(0.005)

            # UO10_Busy신호가 True->False로 될 때까지 기다림 
            while plc.read_by_name('MAIN.Robot1._UO1.UO10_Busy', pyads.PLCTYPE_BOOL):
                time.sleep(0.005)
            
            print("✓")
            time.sleep(0.05)
        
        print(f"\n✓ 완료")
        # Sequence 종료 시 루프 신호 OFF 
        plc.write_by_name('MAIN.Robot1._UI1.DI81', False, pyads.PLCTYPE_BOOL)
        
    except KeyboardInterrupt:
        # 중간에 종료 시 루프 신호 OFF
        plc.write_by_name('MAIN.Robot1._UI1.DI81', False, pyads.PLCTYPE_BOOL)
        print(f"\n\n중단됨")


if __name__ == '__main__':

    main()