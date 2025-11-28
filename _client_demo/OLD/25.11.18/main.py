# main.py
import sys, os
from PyQt6.QtWidgets import QApplication, QMessageBox
from fanuc_logger import logger 



def load_pyads_dll() -> bool:
    """
    pyads 동작에 필요한 TcAdsDll.dll의 경로를 설정하고 모듈을 읽는다
    이 함수는 애플리케이션 시작 시 !!!가장 먼저!!!! 호출되어야 한다
    """
    try:
        # 현재 파일이 위치한 폴더의 절대 경로 저장
        script_dir = os.path.dirname(os.path.abspath(__file__))
        # Windows가 DLL을 검색하는 경로 목록에 이 폴더를 추가
        os.add_dll_directory(script_dir)

        # 이 함수가 성공하면, 이후 'import pyads'는 정상 동작
        import pyads
        logger.info("pyads DLL 경로 설정 및 임포트 성공") #
        return True

    except (ImportError, OSError, FileNotFoundError) as e:
        logger.critical(f"DLL 로드 또는 pyads 임포트 실패: {e}", exc_info=True) #
        return False

    except Exception as e:
        # os.add_dll_directory는 Python 3.8 이상에서만 지원됩니다.
        logger.critical(f"알 수 없는 오류로 DLL 로드 실패: {e}", exc_info=True) #
        return False



if __name__ == "__main__":
    
    logger.info("--- 애플리케이션 시작 ---") #

    # 가장 먼저 DLL 로드 시도
    if not load_pyads_dll():
        app = QApplication(sys.argv) # 메시지 박스를 표시하려면 QApplication이 필요하기 때문
        QMessageBox.critical(None, "DLL 로드 실패", 
                            "TcAdsDll.dll 파일을 찾을 수 없거나 호환되지 않습니다.\n"
                            "프로그램 폴더에 DLL 파일이 있는지 확인하세요.")
        sys.exit(1)
    
    # DLL 파일을 읽은 뒤 나머지 모듈 임포트
    from fanuc_logger import logger
    from fanuc_logic import FanucController
    from mock_model import MockFanucController
    from viewmodel import FanucViewModel
    from demo_view import FanucDemoApp

    app = QApplication(sys.argv)
    logger.info("PyQt Application 객체 생성 완료") #

    # Model, ViewModel, View 생성 (의존성 주입)
    try:
        real_model = FanucController()
        mock_model = MockFanucController()
        
        viewmodel = FanucViewModel(real_model, mock_model)
        
        view = FanucDemoApp(viewmodel)
        
        # 초기 상태 설정 (View가 표시되기 전)
        viewmodel.set_demo_mode(True) 
        
        # 앱 실행
        logger.info("UI 표시 및 애플리케이션 이벤트 루프 진입")
        view.show()
        exit_code = app.exec()
        logger.info(f"--- 애플리케이션 종료. 종료 코드: {exit_code} ---")
        sys.exit(exit_code)
        
    except Exception as e:
        # pyads 임포트 실패 등 치명적 오류 처리
        logger.critical(f"애플리케이션 초기화 중 치명적인 오류 발생: {e}", exc_info=True)
        QMessageBox.critical(None, "초기화 실패", f"애플리케이션 실행 중 오류가 발생했습니다:\n{e}")
        sys.exit(1)
