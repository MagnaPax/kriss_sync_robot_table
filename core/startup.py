# core/startup.py
import sys
import time
from PyQt6.QtWidgets import QApplication, QMessageBox

from core.event_bus import EVENT_BUS
from utils.dll_loader import load_pyads_dll
from ui.splash_screen import SplashScreen



class StartupManager:
    """
    애플리케이션 시작 프로세스 관리자
    
    역할:
    - 스플래시 스크린 표시
    - 필수 컴포넌트 로드 (DLL 등)
    - TwinCAT 연결 상태(PLCService에 위임)
    - 메인 윈도우 실행 전환
    """
    
    def run(self):
        """부팅 시나리오 실행"""
        
        # 1. 스플래시 화면 표시
        splash = SplashScreen()
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


        # --- 여기서부터는 DLL을 읽은 상태 ---
        # 여기서 임포트해야 안전 (Lazy Import)
        from services.plc_service import PLCService


        # ---------------------------------------------------------
        # [Phase 2]: TwinCAT 연결 (Service에 위임)
        # ---------------------------------------------------------
        plc_service = PLCService()  # StartupManager는 PLCService를 잠시 만들어서 연결만 시키고 넘겨줌

        success = plc_service.connect_with_retry(ui_callback=splash.update_status)

        if not success:
            splash.close()
            self._show_critical_error(splash, "TwinCAT 연결 실패", "최종 접속 실패")
            sys.exit(1)


        # ---------------------------------------------------------
        # [Phase 3]: 접속 완료
        # ---------------------------------------------------------
        splash.close()

        # ---------------------------------------------------------
        # [Phase 4]: 메인 윈도우 로드 (Lazy Import)
        #   이 시점은 초기화가 모두 성공한 뒤이므로 안전함
        # ---------------------------------------------------------
        from view_models.main_window_viewmodel import MainViewModel
        from ui.main_window import MainWindow
        
        # 의존성 주입: Service -> ViewModel -> View(Window)
        viewmodel = MainViewModel(plc_service)
        window = MainWindow(viewmodel)

        window.show()
        
        # 여기서 window 객체를 반환하거나 유지해야 GC되지 않음 (main함수 변수에 할당됨)
        return window


    def _load_driver(self, splash: SplashScreen) -> bool:
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
