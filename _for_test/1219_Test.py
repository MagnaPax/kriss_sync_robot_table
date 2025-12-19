"""
1219_panasonic
Python으로 Servo Motor Control(1, 2)
Tool의 공전, 자전용 모터 컨트롤
"""

import pyads
import time
import threading
import sys
import os
import msvcrt

print_lock = threading.Lock()
printing_allowed = threading.Event()
printing_allowed.set()

def connect_plc():
    """PLC 연결"""
    try:
        plc = pyads.Connection('5.143.171.16.1.1', pyads.PORT_TC3PLC1)  # CX-5240에 따라 주소 다름(표준연 컨트롤 박스 CX-5240 : 5.119.154.174.1.1)
        plc.open()
        plc.read_state() # 연결 확인
        print("✓ PLC 연결")
        return plc
    except Exception as e:
        print(f"❌ PLC 연결 실패: {e}")
        exit(1)


def monitor_position(plc):
    """모터의 현재 위치(deg) 읽기"""
    while True:
        printing_allowed.wait()

        try:
            CurPos1 = plc.read_by_name('MAIN.Act_pos1', pyads.PLCTYPE_LREAL)
            CurVel1 = plc.read_by_name('MAIN.Act_vel1', pyads.PLCTYPE_LREAL)
            Con_CurVel1 = CurVel1 / 6   # deg/s를 RPM으로 변환
            CurPos2 = plc.read_by_name('MAIN.Act_pos2', pyads.PLCTYPE_LREAL)
            CurVel2 = plc.read_by_name('MAIN.Act_vel2', pyads.PLCTYPE_LREAL)
            Con_CurVel2 = CurVel2 / 6   # deg/s를 PRM으로 변환
            current_status1_pos = f"현재 위치(1): {round(CurPos1, 3)}deg"
            current_status1_vel = f"현재 속도(1): {round(Con_CurVel1, 3)}RPM"
            current_status2_pos = f"현재 위치(2): {round(CurPos2, 3)}deg"
            current_status2_vel = f"현재 속도(2): {round(Con_CurVel2, 3)}RPM"

            with print_lock:
                sys.stdout.write(current_status1_pos + '\n')
                sys.stdout.write(current_status1_vel + '\n')
                sys.stdout.write(current_status2_pos + '\n')
                sys.stdout.write(current_status2_vel + '\n')
                sys.stdout.flush()
        
        except pyads.pyads_ex.ADSError as e:
            with print_lock:
                sys.stdout.write(f"데이터 읽기 실패: {e}\n")
                sys.stdout.flush()

        time.sleep(0.5)

        # q 입력 시 일시 정지
        if msvcrt.kbhit():
            if msvcrt.getch() == b's':
                plc.write_by_name('MAIN.bStop1', True, pyads.PLCTYPE_BOOL)
                plc.write_by_name('MAIN.bStop2', True, pyads.PLCTYPE_BOOL)
                plc.write_by_name('MAIN.bMoveVel1', False, pyads.PLCTYPE_BOOL)
                plc.write_by_name('MAIN.bMoveVel2', False, pyads.PLCTYPE_BOOL)
                time.sleep(0.5)
                plc.write_by_name('MAIN.bStop1', False, pyads.PLCTYPE_BOOL)
                plc.write_by_name('MAIN.bStop2', False, pyads.PLCTYPE_BOOL)


def input_position(plc):
    """모터의 목표 위치(deg) 입력"""
    while True:
        try:
            # 모터가 회전 중이면 '모터 이동 중...' 출력
            busy1 = plc.read_by_name('MAIN.Busy1', pyads.PLCTYPE_BOOL)
            busy2 = plc.read_by_name('MAIN.Busy2', pyads.PLCTYPE_BOOL)

            if busy1 and busy2:
                with print_lock:
                    print("\r모터 이동 중...\n", end='', flush=True)

                time.sleep(0.5)
                continue
            
            # 모터가 정지 상태이면 현재 위치를 출력하고 목표 위치 및 속도 입력
            with print_lock:
                current_pos1 = plc.read_by_name('MAIN.Act_pos1', pyads.PLCTYPE_LREAL)
                current_pos2 = plc.read_by_name('MAIN.ACt_pos2', pyads.PLCTYPE_LREAL)
                print(f"현재 좌표(1): {round(current_pos1, 3)}\n현재 좌표(2): {round(current_pos2, 3)}")
                # InputPos = float(input("이동할 좌표(deg)를 입력하세요: "))
                InputVel1 = float(input("(1)이동할 속도(RPM)를 입력하세요: "))
                InputVel2 = float(input("(2)이동할 속도(RPM)를 입력하세요: "))

                convert_InputVel1 = InputVel1 * 6   # RPM을 deg/s로 변환하여 입력
                convert_InputVel2 = InputVel2 * 6   # RPM을 deg/s로 변환하여 입력

            # plc.write_by_name('MAIN.position', InputPos, pyads.PLCTYPE_LREAL)
            plc.write_by_name('MAIN.vel1', convert_InputVel1, pyads.PLCTYPE_LREAL)
            plc.write_by_name('MAIN.vel2', convert_InputVel2, pyads.PLCTYPE_LREAL)
            plc.write_by_name('MAIN.bMoveVel1', True, pyads.PLCTYPE_BOOL)
            plc.write_by_name('MAIN.bMoveVel2', True, pyads.PLCTYPE_BOOL)

        except pyads.pyads_ex.ADSError as e:
            with print_lock:
                print(f"데이터 읽기 실패: {e}")

        except KeyboardInterrupt:
            raise


def Servo_Read_On(plc, bool):
    """서보 및 위치 읽기 On/Off"""
    plc.write_by_name('MAIN.bServoOn1', bool, pyads.PLCTYPE_BOOL)
    plc.write_by_name('MAIN.bServoOn2', bool, pyads.PLCTYPE_BOOL)
    plc.write_by_name('MAIN.bReadPos1', bool, pyads.PLCTYPE_BOOL)
    plc.write_by_name('MAIN.bReadVel1', bool, pyads.PLCTYPE_BOOL)
    plc.write_by_name('MAIN.bReadPos2', bool, pyads.PLCTYPE_BOOL)
    plc.write_by_name('MAIN.bReadVel2', bool, pyads.PLCTYPE_BOOL)


def clear_screen():
    """출력 창 Clear"""
    os.system('cls' if os.name == 'nt' else 'clear')


def monitor_threading():
    """현재 위치 읽기 함수 Threading"""
    monitor_thread = threading.Thread(target=monitor_position, args=(plc,), daemon=True)
    monitor_thread.start()


if __name__ == "__main__":
    clear_screen()

    plc = connect_plc()

    Servo_Read_On(plc, True)

    monitor_threading()

    try:
        input_position(plc)

    except KeyboardInterrupt:
        with print_lock:
            Servo_Read_On(plc, False)
            print("\r사용자에 의해 종료됨.", flush=True)
            
    finally:
        if plc.is_open:
            plc.close()
            
        sys.exit(0)