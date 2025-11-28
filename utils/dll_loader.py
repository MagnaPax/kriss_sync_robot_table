# utils/dll_loader.py
"""
pyads 라이브러리를 사용하기 위한 DLL 로더

운영체제가 윈도우일 때 Beckhoff 社의 TcAdsDll.dll 파일 필요
macOS 에는 필요 없다

LogListener 생성 전에 호출되므로 로거를 직접 사용
"""
import os
import sys
import ctypes
import platform
from pathlib import Path
from utils.logger import get_logger
from config.paths import TC_ADS_DLL_PATH

logger = get_logger(__name__)



def load_pyads_dll():
    """
    libs 폴더의 TcAdsDll.dll을 로드하여 pyads 실행 환경 구성
        pyads 임포트 전 사용
        Windows OS 전용(macOS는 dll파일 필요 없음)
    """
    
    # 운영체제 확인: Windows 가 아니면 DLL 로드 필요 없음
    if platform.system() != 'Windows':
        logger.info(f"윈도우즈 OS가 아닙니다. DLL 로드를 건너뜁니다. 현재 운영체제: {platform.system()}")
        return

    # DLL 파일 읽기 시도
    dll_directory = Path(TC_ADS_DLL_PATH).parent
    dll_name = Path(TC_ADS_DLL_PATH).name

    logger.info(f"DLL 경로: {dll_directory} / DLL 파일명: {dll_name}")

    os.add_dll_directory(str(dll_directory))

    try:
        ctypes.windll.LoadLibrary(str(TC_ADS_DLL_PATH))
        logger.info("pyads용 DLL 파일 읽기 성공")

    except Exception as e:
        logger.critical(f"pyads DLL 읽기 실패: {e}", exc_info=True)
        sys.exit(1)





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
    print(f"📂  설정된 DLL 경로: {TC_ADS_DLL_PATH}")
    
    # 2. 파일 존재 여부 사전 체크 (디버깅용)
    if TC_ADS_DLL_PATH.exists():
        print("✅  파일이 해당 경로에 실제로 존재합니다.")
    else:
        print("❌  파일을 찾을 수 없습니다. (Windows라면 로드 실패 예상)")

    print("\n" + "-"*30 + " 함수 실행 " + "-"*30 + "\n")

    # 3. 함수 실행 및 결과 확인
    try:
        load_pyads_dll()
        print("\n✅  [성공] 함수가 정상적으로 종료되었습니다.")
        
        if platform.system() == 'Windows':
            print("   -> Windows 환경에서 DLL 로드에 성공했거나, 이미 로드되어 있습니다.")
        else:
            print("   -> Windows가 아니므로 로드를 건너뛰었습니다.")

    except SystemExit as e:
        print(f"\n⚠️  [종료] 함수가 시스템 종료를 요청했습니다. (Exit Code: {e.code})")
        print("   -> DLL 파일이 없거나 로드 중 에러가 발생하여 안전하게 종료되었습니다.")
        print("   -> 위쪽의 [CRITICAL] 로그 내용을 확인하세요.")
    except Exception as e:
        print(f"\n❌  [실패] 예상치 못한 예외 발생: {e}")

    print("\n" + "="*70)
