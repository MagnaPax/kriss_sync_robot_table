
import pyads
import time
from utils.dll_loader import load_pyads_dll

AMS_NET_ID = "5.143.171.16.1.1" # settings.ini에서 가져옴
PORT = 851

def emergency_stop():
    # DLL 로드 (이게 없어서 접속 실패했음)
    try:
        load_pyads_dll()
        print("DLL Loaded successfully.")
    except Exception as e:
        print(f"DLL Load Failed: {e}")
        return

    print(f"Connecting to PLC ({AMS_NET_ID}:{PORT})...")
    try:
        plc = pyads.Connection(AMS_NET_ID, PORT)
        plc.open()
        
        print("Sending STOP commands...")
        
        axes = [1, 2, 3]
        
        # 1. 모든 동작 정지
        for i in axes:
            try:
                # 이동 신호 끄기 (축별로 분류)
                if i in [1, 2]:
                    plc.write_by_name(f"MAIN.bMoveVel{i}", False, pyads.PLCTYPE_BOOL)
                elif i == 3:
                    plc.write_by_name(f"MAIN.bMoveAbs{i}", False, pyads.PLCTYPE_BOOL)
                
                # 정지 신호 켜기
                plc.write_by_name(f"MAIN.bStop{i}", True, pyads.PLCTYPE_BOOL)
                print(f"Axis {i} Stop Signal Sent.")
            except Exception as e:
                print(f"Axis {i} Stop Failed: {e}")

        time.sleep(0.5)

        # 2. 정지 신호 리셋
        for i in axes:
            try:
                plc.write_by_name(f"MAIN.bStop{i}", False, pyads.PLCTYPE_BOOL)
            except:
                pass

        # 3. 서보 전원 끄기
        print("Turning OFF Servo Power...")
        for i in axes:
            try:
                plc.write_by_name(f"MAIN.bServoOn{i}", False, pyads.PLCTYPE_BOOL)
                print(f"Axis {i} Servo OFF.")
            except Exception as e:
                print(f"Axis {i} Servo OFF Failed: {e}")

        print("Emergency Stop Completed.")
        plc.close()

    except Exception as e:
        print(f"Connection Failed: {e}")

if __name__ == "__main__":
    emergency_stop()
