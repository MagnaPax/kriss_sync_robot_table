"""
Fanuc 좌표 자동 전송 - 간소화 버전
RSR/ACK 핸드셰이킹으로 좌표 자동 전송
"""

import pyads
import time

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


def main():
    # 파일 로드
    filename = input("파일명 (기본: Fanuc_seq.txt): ").strip() or "Fanuc_seq.txt"
    lines = load_file(filename)
    
    print(f"\n시작 (총 {len(lines)}줄)\n")
    
    try:
        for i, line in enumerate(lines, 1):
            coords = parse_line(line)
            if not coords:
                continue
            
            # 좌표 출력
            print(f"[{i}/{len(lines)}] F={coords['F']:.2f} X={coords['X']:.2f} "
                  f"Y={coords['Y']:.2f} Z={coords['Z']:.2f}", end=" ")
            
            # 좌표 전송
            send_coordinate(coords['X'], "X")
            send_coordinate(coords['Y'], "Y")
            send_coordinate(coords['Z'], "Z")
            send_coordinate(coords['W'], "W")
            send_coordinate(coords['P'], "P")
            send_coordinate(coords['R'], "R")
            send_feed(coords['F'])
            
            # RSR ON
            plc.write_by_name('MAIN.Robot1._UI1.UI09_RSR1', True, pyads.PLCTYPE_BOOL)
            
            # ACK ON 대기 (로봇 응답, 최대 40ms)
            timeout = 4  # 10ms × 4 = 40ms
            for _ in range(timeout):
                if plc.read_by_name('MAIN.Robot1._UO1.UO11_ACK1', pyads.PLCTYPE_BOOL):
                    break
                time.sleep(0.01)  # 10ms
            
            # ACK OFF 대기 (동작 완료)
            while plc.read_by_name('MAIN.Robot1._UO1.UO11_ACK1', pyads.PLCTYPE_BOOL):
                time.sleep(0.01)  # 10ms
            
            # RSR OFF
            plc.write_by_name('MAIN.Robot1._UI1.UI09_RSR1', False, pyads.PLCTYPE_BOOL)
            
            print("✓")
            time.sleep(0.05)
        
        print(f"\n✓ 완료")
        
    except KeyboardInterrupt:
        print(f"\n\n중단됨")


if __name__ == '__main__':
    main()