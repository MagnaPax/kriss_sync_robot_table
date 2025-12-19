"""
1219_panasonic
Python으로 Servo Motor Control(3)
Turn Table용 모터 컨트롤
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
            CurPos3 = plc.read_by_name('MAIN.Act_pos3', pyads.PLCTYPE_LREAL)
            CurVel3 = plc.read_by_name('MAIN.Act_vel3', pyads.PLCTYPE_LREAL)
            current_status3_pos = f"현재 위치(3): {round(CurPos3, 3)}"
            current_status3_vel = f"현재 속도(3): {abs(round(CurVel3, 3))}"

            with print_lock:
                sys.stdout.write(current_status3_pos + '\n')
                sys.stdout.write(current_status3_vel + '\n')
                sys.stdout.flush()
        
        except pyads.pyads_ex.ADSError as e:
            with print_lock:
                sys.stdout.write(f"데이터 읽기 실패: {e}\n")
                sys.stdout.flush()

        time.sleep(0.5)

        # q 입력 시 일시 정지
        if msvcrt.kbhit():
            if msvcrt.getch() == b's':
                plc.write_by_name('MAIN.bStop3', True, pyads.PLCTYPE_BOOL)
                plc.write_by_name('MAIN.bMoveAbs3', False, pyads.PLCTYPE_BOOL)
                time.sleep(0.5)
                plc.write_by_name('MAIN.bStop3', False, pyads.PLCTYPE_BOOL)


def input_position(plc):
    """모터의 목표 위치(deg) 입력"""
    while True:
        try:
            # 모터가 회전 중이면 '모터 이동 중...' 출력
            busy3 = plc.read_by_name('MAIN.Busy3', pyads.PLCTYPE_BOOL)

            if busy3:
                with print_lock:
                    print("\r모터 이동 중...\n", end='', flush=True)

                time.sleep(0.5)
                continue
            
            # 모터가 정지 상태이면 현재 위치를 출력하고 목표 위치 및 속도 입력
            with print_lock:
                current_pos3 = plc.read_by_name('MAIN.Act_pos3', pyads.PLCTYPE_LREAL)
                print(f"\n현재 좌표: {round(current_pos3, 3)}")
                InputPos = float(input("(3)이동할 좌표(deg)를 입력하세요: "))
                InputVel = float(input("(3)이동할 속도(deg/s)를 입력하세요: "))

            plc.write_by_name('MAIN.pos3', InputPos, pyads.PLCTYPE_LREAL)
            plc.write_by_name('MAIN.vel3', InputVel, pyads.PLCTYPE_LREAL)
            plc.write_by_name('MAIN.bMoveAbs3', True, pyads.PLCTYPE_BOOL)

        except pyads.pyads_ex.ADSError as e:
            with print_lock:
                print(f"데이터 읽기 실패: {e}")

        except KeyboardInterrupt:
            raise


def Servo_Read(plc, bool):
    """서보 및 위치 읽기 On/Off"""
    plc.write_by_name('MAIN.bServoOn3', bool, pyads.PLCTYPE_BOOL)
    plc.write_by_name('MAIN.bReadPos3', bool, pyads.PLCTYPE_BOOL)
    plc.write_by_name('MAIN.bReadVel3', bool, pyads.PLCTYPE_BOOL)


def clear_screen():
    """출력 창 Clear"""
    os.system('cls' if os.name == 'nt' else 'clear')


def monitor_threading():
    """현재 위치 읽기 함수 Threading"""
    monitor_thread = threading.Thread(target=monitor_position, args=(plc,), daemon=True)
    monitor_thread.start()


# def Homing(plc):
#     # Homing(원점으로 이동)
#     plc.write_by_name('MAIN.bHome3', True, pyads.PLCTYPE_BOOL)
#     BusyHome = plc.read_by_name('MAIN.BusyHome3', pyads.PLCTYPE_BOOL)

#     while BusyHome:
#         print("\nHoming중...\n")
#         time.sleep(1.0)
        

if __name__ == "__main__":
    clear_screen()

    plc = connect_plc()

    Servo_Read(plc, True)

    monitor_threading()

    try:
        input_position(plc)

    except KeyboardInterrupt:
        with print_lock:
            Servo_Read(plc, False)
            print("\r사용자에 의해 종료됨.", flush=True)
            
    finally:
        if plc.is_open:
            plc.close()
            
        sys.exit(0)