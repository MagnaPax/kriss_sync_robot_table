# ui/widgets/current_state_widget.py
import sys
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QGridLayout
)
from PyQt6.QtCore import Qt, QTimer

from ui.widgets.base_widget import BaseWidget
from ui.widgets.status_indicator_box import StatusIndicatorBox



# ==========================================================
# 1. 현재 상태 위젯 (Current State)
# ==========================================================
class CurrentStateWidget(BaseWidget):
    """
    Current State 위젯
    - BaseWidget을 상속받아 update_data 인터페이스 구현
    - RPM/Speed 라벨과 상태 표시줄(StatusIndicatorBox) 조립
    """

    def _init_ui(self):
        """BaseWidget의 _init_ui를 재정의하여 UI를 구성"""

        # 위젯 이름
        self.setObjectName("current_state_widget")
        
        # 메인 수직 레이아웃
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        main_layout.setContentsMargins(10, 5, 10, 5) # 위젯 내부 여백
        main_layout.setSpacing(10) # 섹션 간 간격


        # --- 1. RPM/Speed 섹션 ---
        
        # 1-1. 그리드 레이아웃 생성 (3열 배치용)
        rpm_speed_layout = QGridLayout()
        rpm_speed_layout.setSpacing(15) # 라벨 간 간격

        # 1-2. 라벨 생성 및 변수 저장
        self.m1_rpm_label = QLabel("M1 RPM 00")
        self.m2_rpm_label = QLabel("M2 RPM 00")
        self.robot_speed_label = QLabel("ROBOT Speed 00")

        # 1-3. 라벨 이름 설정
        self.m1_rpm_label.setObjectName("rpm_speed_label")
        self.m2_rpm_label.setObjectName("rpm_speed_label")
        self.robot_speed_label.setObjectName("rpm_speed_label")

        # 1-4. 그리드 레이아웃에 라벨 배치
        rpm_speed_layout.addWidget(self.m1_rpm_label, 0, 0) # 0행 0열 - M1 RPM
        rpm_speed_layout.addWidget(self.m2_rpm_label, 0, 1) # 0행 1열 - M2 RPM
        rpm_speed_layout.addWidget(self.robot_speed_label, 0, 2) # 0행 2열 - Robot Speed

        # 1-5. 메인 레이아웃에 RPM/Speed 섹션 추가
        main_layout.addLayout(rpm_speed_layout)


        # --- 2. 상태 표시줄 섹션 ---
        
        # 2-1. 수평 레이아웃 생성 (2개 배치용)
        status_layout = QHBoxLayout()
        status_layout.setSpacing(10) # 상태창 간 간격

        # 2-2. StatusIndicatorBox 생성 및 변수 저장
        self.turntable_status = StatusIndicatorBox("1. TurnTable", led_size=10)
        self.robot_status = StatusIndicatorBox("2. ROBOT", led_size=10)
        
        # 2-3. 수평 레이아웃에 상태창 배치
        status_layout.addWidget(self.turntable_status)
        status_layout.addWidget(self.robot_status)
        
        # 2-4. 메인 레이아웃에 상태 표시줄 섹션 추가
        main_layout.addLayout(status_layout)
        
        # 2-5. 초기 상태 설정
        self.clear_widget()

    def update_data(self, data: dict):
        """
        BaseWidget의 추상 메서드(update_data) 구현
        
        Args:
            data (dict): {
                            'm1_rpm': int, 
                            'm2_rpm': int, 
                            'robot_speed': int,
                            'turntable_state': str, 
                            'robot_state': str
                         } 형태의 딕셔너리 기대
        """
        # 1. RPM/Speed 값 추출 및 라벨 업데이트
        m1_rpm = data.get('m1_rpm', 0)
        m2_rpm = data.get('m2_rpm', 0)
        robot_speed = data.get('robot_speed', 0)
        
        self.m1_rpm_label.setText(f"M1 RPM {m1_rpm:02d}")
        self.m2_rpm_label.setText(f"M2 RPM {m2_rpm:02d}")
        self.robot_speed_label.setText(f"ROBOT Speed {robot_speed:02d}")

        # 2. 상태 값 추출 및 StatusIndicatorBox 업데이트
        turntable_state = data.get('turntable_state', 'off')
        robot_state = data.get('robot_state', 'off')

        # StatusIndicatorBox는 {'state': ..., 'title': ...} 형태의 dict를 받음
        self.turntable_status.safe_update_data({
            'state': turntable_state,
            'title': self.turntable_status._title_text # 기존 제목 유지
        })
        self.robot_status.safe_update_data({
            'state': robot_state,
            'title': self.robot_status._title_text # 기존 제목 유지
        })

    def clear_widget(self):
        """위젯을 초기 상태(0, off)로 리셋합니다."""
        self.update_data({
            'm1_rpm': 0,
            'm2_rpm': 0,
            'robot_speed': 0,
            'turntable_state': 'off',
            'robot_state': 'off'
        })
        super().clear_widget()





# ==========================================================
# 2. 단독 실행 (테스트용)
"""
python -m ui.widgets.current_state_widget
"""
# ==========================================================
if __name__ == '__main__':
    from styles.theme import load_and_apply_stylesheet


    app = QApplication(sys.argv)

    
    qss_file = "styles/dark_stylesheet.qss"
    load_and_apply_stylesheet(app, qss_file)


    main_window = QWidget()
    main_layout = QVBoxLayout(main_window)
    
    test_widget = CurrentStateWidget()
    main_layout.addWidget(test_widget)
    main_window.setWindowTitle("CurrentStateWidget 단독 테스트")
    # main_window.resize(400, 150) # 크기는 자동으로 조절될 것임
    main_window.show()

    # 테스트용 데이터
    test_data = {
        'm1_rpm': 0,
        'm2_rpm': 0,
        'robot_speed': 0,
        'turntable_state': 'running',
        'robot_state': 'waiting'
    }
    
    # 상태 순환용 리스트
    tt_states = ['running', 'waiting', 'off', 'error']
    robot_states = ['waiting', 'running', 'disconnected', 'connected']
    tt_idx = 0
    robot_idx = 0

    def update_test():
        global tt_idx, robot_idx
        
        # RPM/Speed 값 업데이트 (0~99 사이 랜덤)
        test_data['m1_rpm'] = (test_data['m1_rpm'] + 7) % 100
        test_data['m2_rpm'] = (test_data['m2_rpm'] + 13) % 100
        test_data['robot_speed'] = (test_data['robot_speed'] + 3) % 100
        
        # 상태 업데이트 (리스트 순환)
        test_data['turntable_state'] = tt_states[tt_idx]
        test_data['robot_state'] = robot_states[robot_idx]
        
        tt_idx = (tt_idx + 1) % len(tt_states)
        robot_idx = (robot_idx + 1) % len(robot_states)

        test_widget.safe_update_data(test_data)

    timer = QTimer()
    timer.timeout.connect(update_test)
    timer.start(500) # 0.5초마다 업데이트

    sys.exit(app.exec())