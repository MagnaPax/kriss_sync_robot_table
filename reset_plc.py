
import pyads
import time
import configparser
from pathlib import Path
from utils.dll_loader import load_pyads_dll

def reset_plc():

    # DLL 로드 (이게 없어서 접속 실패했음)
    try:
        load_pyads_dll()
        print("DLL Loaded.")
    except Exception as e:
        print(f"DLL Load Failed: {e}")
        return

    # 1. settings.ini에서 접속 정보 읽기
    config = configparser.ConfigParser()
    config_path = Path("config/settings.ini")
    
    if not config_path.exists():
        print(f"Error: {config_path} not found.")
        return

    config.read(config_path, encoding='utf-8')
    try:
        ams_net_id = config.get("TwinCAT", "AMS_NET_ID")
        port = config.getint("TwinCAT", "PORT")
    except Exception as e:
        print(f"Error reading settings.ini: {e}")
        return



    # 3. PLC 연결
    print(f"Connecting to PLC ({ams_net_id}:{port})...")
    try:
        plc = pyads.Connection(ams_net_id, port)
        plc.open()
        
        axes = [1, 2, 3]
        
        print("\n[Step 1] Stopping all movements...")
        for i in axes:
            try:
                # 이동 신호 해제
                plc.write_by_name(f"MAIN.bMoveVel{i}", False, pyads.PLCTYPE_BOOL)
                plc.write_by_name(f"MAIN.bMoveAbs{i}", False, pyads.PLCTYPE_BOOL)
                # 정지 신호 인가 (Symbol이 없을 수 있으므로 try-except)
                try:
                    plc.write_by_name(f"MAIN.bStop{i}", True, pyads.PLCTYPE_BOOL)
                except:
                    pass
                print(f"Axis {i} Stop command sent.")
            except Exception as e:
                print(f"Axis {i} Stop failed: {e}")

        time.sleep(0.5)

        # 정지 신호 해제 (다시 움직일 수 있는 상태로 만듦)
        for i in axes:
            try:
                plc.write_by_name(f"MAIN.bStop{i}", False, pyads.PLCTYPE_BOOL)
            except:
                pass

        print("\n[Step 2] Turning OFF Servo Power...")
        for i in axes:
            try:
                # 서보 전원 끄기
                plc.write_by_name(f"MAIN.bServoOn{i}", False, pyads.PLCTYPE_BOOL)
                # 읽기 기능들 끄기
                plc.write_by_name(f"MAIN.bReadPos{i}", False, pyads.PLCTYPE_BOOL)
                plc.write_by_name(f"MAIN.bReadVel{i}", False, pyads.PLCTYPE_BOOL)
                print(f"Axis {i} Servo Power OFF.")
            except Exception as e:
                print(f"Axis {i} Servo OFF failed: {e}")

        print("\nReset Completed successfully.")
        plc.close()

    except Exception as e:
        print(f"Connection Failed: {e}")

if __name__ == "__main__":
    reset_plc()
