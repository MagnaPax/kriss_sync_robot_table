# core/startup.py
import sys
import time
from PyQt6.QtWidgets import QApplication, QMessageBox
from typing import Optional, TYPE_CHECKING

from core.event_bus import EVENT_BUS
from utils.dll_loader import load_pyads_dll
from ui.launch_screen import LaunchScreen



# 타입 체크(VS Code, PyCharm) 시점에만 임포트
#   실제 실행 시에는 건너뜀 -> pyads가 로드되지 않아 에러가 안 남
if TYPE_CHECKING:
    from communication.twincat_connector import TwinCATConnector


class StartupManager:
    """
    애플리케이션 시작 프로세스 관리자
    
    역할:
    - 스플래시 스크린 표시
    - 필수 컴포넌트 로드 (DLL 등)
    - 로딩 상태 피드백 (성공/실패/재시도)
    - 메인 윈도우 실행 전환
    """
    
    def run(self):
        """부팅 시나리오 실행"""
        
        # 1. 스플래시 화면 표시
        splash = LaunchScreen()
        splash.show()

        # ---------------------------------------------------------
        # [Phase 1]: 시스템 드라이버(DLL) 로드
        # ---------------------------------------------------------
        driver = self._load_driver(splash)

        if not driver:
            splash.close()
            sys.exit(1)

        # 잠시 대기 (사용자가 성공 메시지를 인식할 시간)
        time.sleep(0.5)

        # ---------------------------------------------------------
        # [Phase 2]: TwinCAT 연결
        # ---------------------------------------------------------
        connector = self._connect_twincat(splash)

        if not connector:
            splash.close()
            sys.exit(1)

        # ---------------------------------------------------------
        # [Phase 3]: 부팅 완료 및 메인 윈도우 진입
        # ---------------------------------------------------------
        splash.close()

        # ---------------------------------------------------------
        # [Phase 4]: 메인 윈도우 로드 (Lazy Import)
        #   이 시점은 초기화가 모두 성공한 뒤이므로 안전함
        # ---------------------------------------------------------
        from ui.main_window import MainWindow
        
        window = MainWindow()
        window.show()
        
        # 여기서 window 객체를 반환하거나 유지해야 GC되지 않음 (main함수 변수에 할당됨)
        return window


    def _load_driver(self, splash: LaunchScreen) -> bool:
        """
        [Phase 1] DLL 로드 및 접속 재시도 로직
        """
        max_retries = 3
        
        for i in range(1, max_retries + 1):
            try:
                # 상태 업데이트 (0% ~ 30%)
                splash.update_status(f"시스템 드라이버 로드 중... ({i}/{max_retries})", 10 + (i * 5))
                QApplication.processEvents()
                
                # DLL 로드 시도 (실제 로직)
                # time.sleep(0.5) # 연출용 딜레이 (필요 시 주석 해제)
                load_pyads_dll()
                
                # 성공 피드백
                splash.update_status("드라이버 로드 완료.", 40)
                EVENT_BUS.system_info.emit("TwinCAT 통신 모듈(DLL) 로드 성공")
                
                QApplication.processEvents()
                time.sleep(0.8) # 사용자가 성공 메시지를 볼 수 있게 잠시 대기
                return True

            except Exception as e:
                EVENT_BUS.ui_log_message.emit(f"드라이버 로드 시도({i}) 실패: {e}", "ERROR")
                
                if i < max_retries:
                    splash.update_status(f"드라이버 로드 실패. 재시도 중...", 10)
                    time.sleep(1.0)
                else:
                    self._show_critical_error(splash, "시스템 드라이버 로드 실패", str(e))
                    return False
        return False


    # 리턴 타입에 따옴표("")를 붙여서 문자열로 적음 (Forward Reference)
    def _connect_twincat(self, splash: LaunchScreen) -> Optional["TwinCATConnector"]:
        """
        [Phase 2] TwinCAT 연결 시도
        """
        # 실제 동작 시에는 여기서 임포트 (Lazy Import)
        #   DLL 로드가 끝난 시점이므로 안전함
        from communication.twincat_connector import TwinCATConnector

        max_retries = 3

        for i in range(1, max_retries + 1):

            # try 블록 밖에서 미리 계산 (안전하게 scope 확보)
            progress = 40 + (i * 15)

            try:
                # 상태 업데이트 (40% ~ 90%)
                splash.update_status(f"TwinCAT 연결 시도 중... ({i}/{max_retries})", progress)
                QApplication.processEvents()
                
                # 연결 객체 생성 및 접속 시도
                connector = TwinCATConnector()
                connector.connect() # 실패 시 내부에서 ConnectionError 발생시킴
                
                # 성공
                splash.update_status("TwinCAT 연결 성공! 시스템을 시작합니다.", 100)
                EVENT_BUS.system_info.emit("PLC 연결 성공")
                QApplication.processEvents()
                time.sleep(0.8) # 성공 메시지 보여줄 시간
                
                return connector

            except Exception as e:
                EVENT_BUS.ui_log_message.emit(f"PLC 접속 실패({i}): {e}", "ERROR")
                
                if i < max_retries:
                    splash.update_status(f"접속 실패. 재시도 대기 중...", progress)
                    # UI 멈춤 방지하며 대기
                    end_time = time.time() + 1.0
                    while time.time() < end_time:
                        QApplication.processEvents()
                else:
                    self._show_critical_error(splash, "TwinCAT 연결 실패", str(e))
                    return None
                
            time.sleep(0.5) # 다음 시도 전 살짝 기다리기
        return None


    def _show_critical_error(self, parent, title, error_msg):
        """치명적 에러 처리"""
        msg = f"{title}: {error_msg}"
        EVENT_BUS.ui_log_message.emit(msg, "CRITICAL")

        QMessageBox.critical(
            parent, 
            title, 
            f"초기화 과정에서 오류가 발생했습니다.\n\n원인: {error_msg}\n\n"
            "관리자에게 문의하십시오."
        )
