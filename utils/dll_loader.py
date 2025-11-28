# utils/dll_loader.py
"""
pyads 라이브러리를 사용하기 위한 DLL 로더

운영체제가 윈도우일 때 Beckhoff 社의 TcAdsDll.dll 파일 필요
macOS 에는 필요 없다

LogListener 생성 전에 호출되므로 로거를 직접 사용
"""
import os
import ctypes
import platform
from pathlib import Path
from config.paths import TC_ADS_DLL_PATH



def load_pyads_dll():
    """
    TcAdsDll.dll 읽기 함수
    
    동작:
        - Windows가 아니면 패스(macOS에서는 dll 필요 없음)
        - DLL 파일이 없으면 FileNotFoundError 발생
        - 로드 실패 시 OSError 발생
    """
    
    # OS 체크
    if platform.system() != 'Windows':
        return
    
    # 파일이 있는지 확인
    if not TC_ADS_DLL_PATH.exists():
        raise FileNotFoundError(f"DLL 파일을 찾을 수 없습니다: {TC_ADS_DLL_PATH}")
    

    # DLL 파일 읽기 시도
    try:
        dll_directory = Path(TC_ADS_DLL_PATH).parent
        os.add_dll_directory(str(dll_directory))
        ctypes.windll.LoadLibrary(str(TC_ADS_DLL_PATH))

    except Exception as e:
        raise OSError(f"DLL 로드 실패: {e}")





# =============================================================================
# Smoke Test
# python -m utils.dll_loader
# =============================================================================
if __name__ == "__main__":
    print("\n" + "="*70)
    print("DLL Loader Smoke Test")
    print("="*70 + "\n")

    # 1. 환경 정보 출력
    print(f"🖥️  현재 운영체제: {platform.system()}")
    print(f"📂  타겟 DLL 경로: {TC_ADS_DLL_PATH}")
    
    # 2. 파일 존재 여부 사전 체크 (디버깅용)
    if TC_ADS_DLL_PATH.exists():
        print("✅  파일이 해당 경로에 실제로 존재합니다.")
    else:
        print("ℹ️  파일을 찾을 수 없습니다. (Windows라면 FileNotFoundError 예상)")

    print("\n" + "-"*30 + " 함수 실행 " + "-"*30 + "\n")

    # 3. 함수 실행 및 결과 확인
    try:
        load_pyads_dll()
        
        # 예외가 발생하지 않고 여기까지 왔다면 성공
        print("✅  [성공] 함수가 에러 없이 종료되었습니다.")
        
        if platform.system() == 'Windows':
            print("   -> (Windows) DLL이 정상적으로 로드되었습니다.")
        else:
            print("   -> (Non-Windows) OS 체크 후 로드 로직을 건너뛰었습니다 (정상 동작).")

    except FileNotFoundError as e:
        print(f"\n⚠️  [확인] FileNotFoundError가 발생했습니다.")
        print(f"   -> 원인: {e}")
        print("   -> (해설) DLL 파일이 없어서 발생한 것으로, 의도된 예외입니다.")

    except OSError as e:
        print(f"\n⚠️  [확인] OSError가 발생했습니다.")
        print(f"   -> 원인: {e}")
        print("   -> (해설) 파일은 있지만 로드에 실패했습니다 (비트수 불일치, 손상 등).")

    except Exception as e:
        print(f"\n❌  [실패] 예상치 못한 예외가 발생했습니다: {type(e).__name__}")
        print(f"   -> 메시지: {e}")

    print("\n" + "="*70)
