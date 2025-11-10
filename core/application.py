# core/application.py


class Application:
    """
    앱 엔진(Application Wrapper)
    QApplication 환경을 감싸(wrpper) 클래스

    목적:
        - 앱 전체에서 QApplication 인스턴스가 하나만 존재하도록 보장 (싱글톤)
        - 전역 예외 처리, 테마 적용, 로깅 초기화, 종료 신호 처리 등을 담당
        - 앱의 “부트스트랩(시작점)” 역할
    """