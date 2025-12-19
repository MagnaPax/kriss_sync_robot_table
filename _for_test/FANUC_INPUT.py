"""
Fanuc 좌표 자동 전송 - 간소서화 버전
좌표 그 자체를 전송에서 이전 값과의 차이를 보내는 방식으로 변경(TP Program도 차이만큼 이동하도록 변경함).
RSR/ACK 핸드셰이킹으로 좌표 자동 전송 -> RSR신호 ON/OFF 반복은 좋지 못한 방법이므로, 1회의 Pulse를 주고 TP Program 내에서 루프가 실행되도록 수정.
UO10_Busy 신호를 사용하여 좌표 수신과 대기 타이밍 확인.
DI81이 ON이면 루프를 계속 수행하고 DI81이 OFF이면 루프를 탈출하여 TP Program 종료.
"""
import msvcrt
import pyads
import time


def send_bits_to_plc(plc, axis_name, lower_value, high_value):
    """비트 전송"""
    # 24비트 버전    
    # 하위 16비트
    for i in range(16):
        plc.write_by_name(f'MAIN.Robot1._UI1.{axis_name}l{i}', (lower_value & (1 << i)) > 0, pyads.PLCTYPE_BOOL)    
    # 상위 8비트
    for j in range(8):
        plc.write_by_name(f'MAIN.Robot1._UI1.{axis_name}h{j}', (high_value & (1 << j)) > 0, pyads.PLCTYPE_BOOL)


def send_coordinate(plc, input_val, axis_name):
    """좌표 전송 (소숫점 셋째자리까지만)"""
    # 24비트 버전

    rounded_val = round(input_val, 3)
    scaled = int(abs(rounded_val * 1000))
    send_bits_to_plc(plc, axis_name, scaled & 0xFFFF, (scaled >> 16) & 0xFF)
    plc.write_by_name(f'MAIN.Robot1._UI1.{axis_name}_Check', 
                    rounded_val < 0, pyads.PLCTYPE_BOOL)


def send_feed(plc, input_F):
    """Feed 전송 (소숫점 셋째자리까지만)"""        
    # 20비트 버전
    # 소숫점 셋째자리로 반올림
    rounded_F = round(input_F, 3)
    scaled_F = int(abs(rounded_F * 1000))
    # 하위 16비트
    for i in range(16):
        plc.write_by_name(f'MAIN.Robot1._UI1.Fl{i}', (scaled_F & (1 << i)) > 0, pyads.PLCTYPE_BOOL)
    # 상위 4비트
    for j in range(4):
        plc.write_by_name(f'MAIN.Robot1._UI1.Fh{j}', ((scaled_F >> 16) & (1 << j)) > 0, pyads.PLCTYPE_BOOL)


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


# 일시 정지
def pause_process(plc):
    print("Cycle Stop")
    plc.write_by_name('MAIN.Robot1._UI1.UI04_CycleStop', True, pyads.PLCTYPE_BOOL)
    time.sleep(0.1)
    plc.write_by_name('MAIN.Robot1._UI1.UI04_CycleStop', False, pyads.PLCTYPE_BOOL)


# 일시 정지 시점부터 재시작
def resume_process(plc):
    print("Cycle Start")
    plc.write_by_name('MAIN.Robot1._UI1.UI06_Start', True, pyads.PLCTYPE_BOOL)
    time.sleep(0.1)
    plc.write_by_name('MAIN.Robot1._UI1.UI06_Start', False, pyads.PLCTYPE_BOOL)


# 일시 정지 및 재시작 실행 함수
def stop_start(plc, stop, start):
    """정지 및 시작 wrapper"""
    if stop:
        pause_process(plc)

    if start:
        resume_process(plc)


# def user_input_thread(plc):
#     while True:
#         command = input("정지(S), 시작(G): ").strip().upper()
#         if command == "S":
#             stop_start(plc, True, False)
#         elif command == "G":
#             stop_start(plc, False, True)
#         else:
#             print("잘못된 명령")


# =============================================================================
# main 로직 분리 함수들
# ============================================================================

def connect_plc():
    """PLC 연결"""
    try:
        # 원본 IP와 포트 사용 
        plc = pyads.Connection('5.119.154.174.1.1', pyads.PORT_TC3PLC1)
        plc.open()
        plc.read_state() # 연결 확인 
        print("✓ PLC 연결")
        return plc
    except Exception as e:
        print(f"❌ PLC 연결 실패: {e}") # 
        exit(1) # 실패 시 종료 


def get_sequence_lines():
    # 파일 로드
    filename = input("파일명 (기본: Fanuc_seq.txt): ").strip() or "Fanuc_seq.txt"
    lines = load_file(filename)
    
    print(f"\n시작 (총 {len(lines)}줄)\n")

    return lines

def reset_all_axes(plc):
    """모든 축 비트 초기화"""
    for axis in ['X', 'Y', 'Z', 'W', 'P', 'R']:
        send_bits_to_plc(plc, axis, 0, 0)

def start_process(plc):
    # RSR신호 Pulse
    print("TP Program Start")
    plc.write_by_name('MAIN.Robot1._UI1.UI10_RSR2', True, pyads.PLCTYPE_BOOL)   # MAIN.Robot1._UI1.UI09_RSR1 = RSR0001 / MAIN.Robot1._UI1.UI10_RSR2 = RSR0002
    # Loop신호(ON이면 루프 반복, OFF이면 루프 종료)
    plc.write_by_name('MAIN.Robot1._UI1.DI43', True, pyads.PLCTYPE_BOOL)


def initialize_signals(plc):
    # Cycle Stop, RSR2, Loop신호 초기화
    plc.write_by_name('MAIN.Robot1._UI1.UI04_CycleStop', False, pyads.PLCTYPE_BOOL)
    plc.write_by_name('MAIN.Robot1._UI1.UI10_RSR2', False, pyads.PLCTYPE_BOOL)
    plc.write_by_name('MAIN.Robot1._UI1.DI43', False, pyads.PLCTYPE_BOOL)

    # 양수/음수 체크 비트 초기화 
    plc.write_by_name('MAIN.Robot1._UI1.X_Check', False, pyads.PLCTYPE_BOOL)
    plc.write_by_name('MAIN.Robot1._UI1.Y_Check', False, pyads.PLCTYPE_BOOL)
    plc.write_by_name('MAIN.Robot1._UI1.Z_Check', False, pyads.PLCTYPE_BOOL)
    plc.write_by_name('MAIN.Robot1._UI1.W_Check', False, pyads.PLCTYPE_BOOL)
    plc.write_by_name('MAIN.Robot1._UI1.P_Check', False, pyads.PLCTYPE_BOOL)
    plc.write_by_name('MAIN.Robot1._UI1.R_Check', False, pyads.PLCTYPE_BOOL)


def write_move_command(plc, coords, previous_coords, init_done, i, lines) -> tuple[dict, bool]:
    """
    인자 값:
        plc:               TwinCAT 연결 객체
        coords:            현재 스텝에서 이동할 목표 좌표 (F, X, Y, Z, W, P, R)
        previous_coords:   직전 스텝의 좌표 (Delta 계산용)
        init_done:         첫 번째 이동 명령이 수행되었는지 여부 (True/False)
        i:                 현재 처리 중인 라인 번호 (로그 출력용)
        lines:             전체 시퀀스 데이터 리스트 (전체 진행률 표시용)
        
    반환값:
        tuple[dict, bool]:
            - 갱신된 previous_coords (다음 스텝의 기준 좌표)
            - 갱신된 init_done (True로 변경됨)
    """

    # 이전 값 저장 
    if previous_coords is None:
        deltas = coords.copy()
    else:
        deltas = {key: coords[key] - previous_coords[key] for key in coords.keys()}

    previous_coords = coords

    while True:
        # 정지(키보드 입력) 
        if msvcrt.kbhit():
            if msvcrt.getch() == b'q':
                print("비상 정지 ")
                raise KeyboardInterrupt # main의 KeyboardInterrupt로 실행?
            elif msvcrt.getch() == b's':
                print("일시 정지 ")
                stop_start(plc, stop=True, start=False)
            elif plc.read_by_name('MAIN.Robot1._UO1.UO04_PrgPaused', pyads.PLCTYPE_BOOL) and msvcrt.getch() == b'g':
                print("재시작")
                stop_start(plc, stop=False, start=True)

            
        if (not init_done) or plc.read_by_name('MAIN.Robot1._UO1.DO45', pyads.PLCTYPE_BOOL):
            # Feed를 제외한 이전 값과의 차이를 출력 
            if i != 1:
                print("이동 완료")
            print(f"[{i}/{len(lines)}] F={coords['F']:.2f} ΔX={deltas['X']:.2f} "
                f"ΔY={deltas['Y']:.2f} ΔZ={deltas['Z']:.2f} ΔW={deltas['W']:.2f} "
                f"ΔP={deltas['P']:.2f} ΔR={deltas['R']:.2f}", end=" ")
            print("이동 중")
            send_feed(plc, coords['F'])
            send_coordinate(plc, deltas['X'], "X")
            send_coordinate(plc, deltas['Y'], "Y")
            send_coordinate(plc, deltas['Z'], "Z")
            send_coordinate(plc, deltas['W'], "W")
            send_coordinate(plc, deltas['P'], "P")
            send_coordinate(plc, deltas['R'], "R")

            init_done = True
            break

        else:
            continue
    
    # 갱신된 상태값들 반환(튜플)
    return previous_coords, init_done


def stop_process(plc):
    # Sequence 종료 시 RSR 및 Loop 신호 OFF 
    plc.write_by_name('MAIN.Robot1._UI1.UI10_RSR2', False, pyads.PLCTYPE_BOOL)
    plc.write_by_name('MAIN.Robot1._UI1.DI43', False, pyads.PLCTYPE_BOOL)


def emergency_stop_process(plc):
    # 비상 정지
    plc.write_by_name('MAIN.Robot1._UI1.UI10_RSR2', False, pyads.PLCTYPE_BOOL)
    plc.write_by_name('MAIN.Robot1._UI1.DI43', False, pyads.PLCTYPE_BOOL)
    plc.write_by_name('MAIN.Robot1._UI1.UI04_CycleStop', True, pyads.PLCTYPE_BOOL)
    print(f"\n\n중단됨")





def main():

    # PLC 연결
    plc = connect_plc()

    # 파일 로드
    lines = get_sequence_lines()

    # PLC 신호 초기화 -> 시작 전에 초기화 해야됨
    initialize_signals(plc)
    
    reset_all_axes(plc)  # 초기화 한 줄

    # 프로세스 시작 신호 전송
    start_process(plc)



    # 첫 줄 실행 트리거
    init_done = False
    
    previous_coords = None


    try:

        for i, line in enumerate(lines, 1):
            coords = parse_line(line)

            if not coords:
                continue

            # 함수 호출: (현재값, 이전값)을 주고 -> (갱신된 이전값)을 받음
            previous_coords, init_done = write_move_command(plc, coords, previous_coords, init_done, i, lines)


        # Sequence 종료 시 루프 신호 OFF
        stop_process(plc)

    except KeyboardInterrupt:
        emergency_stop_process(plc)


if __name__ == '__main__':

    main()
