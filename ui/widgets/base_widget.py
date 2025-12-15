# ui/widgets/base_widget.py
"""
모든 커스텀 위젯의 베이스 클래스
- KRISS Robot Polishing Machine UI의 모든 위젯이 상속
- 데이터 업데이트 인터페이스 통일
- 에러 처리 및 활성화/비활성화 기능 제공
"""

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import pyqtSignal
from typing import Any, Optional
from abc import ABC, abstractmethod

class BaseWidget(QWidget):
    """
    모든 커스텀 위젯의 베이스 클래스
    
    역할:
    1. 공통 인터페이스 정의 (update_data)
    2. 안전한 업데이트 메커니즘 (safe_update_data)
    3. 활성화/비활성화 제어
    4. 에러 처리 및 시그널 발생
    
    사용 예시:
        class MyWidget(BaseWidget):
            def _init_ui(self):
                # UI 구성
                pass
            
            def update_data(self, data):
                # 데이터로 UI 업데이트
                self.my_label.setText(str(data))
    
    주의사항:
    - update_data()는 서브클래스에서 반드시 구현해야 함
    - UI 구성은 _init_ui()에서 수행 (생성자에서 자동 호출됨)
    """
    
    # 시그널 정의
    error_occurred = pyqtSignal(str)      # 에러 발생: (error_message)
    data_updated = pyqtSignal(object)     # 데이터 업데이트 완료: (data)
    
    def __init__(self, parent=None):
        """
        BaseWidget 초기화
        
        Args:
            parent: 부모 위젯 (None이면 독립 창)
        """
        super().__init__(parent)

        # 모든 자식 위젯이 공통으로 사용할 로그 말머리
        # self.__class__.__name__은 자식 클래스의 이름이 들어가게 된다
        self.log_prefix = f"[{self.__class__.__name__}]"
        
        # 내부 상태
        self._is_enabled = True       # 위젯 활성화 상태
        self._last_data = None        # 마지막 업데이트 데이터
        
        # UI 초기화 (서브클래스에서 구현)
        self._init_ui()
    
    def _init_ui(self):
        """
        UI 초기화 (서브클래스에서 오버라이드)
        
        이 메서드에서:
        - 레이아웃 생성
        - 위젯 배치
        - 초기 스타일 적용
        """
        pass
    
    # 추상클래스: 메서드의 목록만 가진 클래스. @abstractmethod가 붙은 모든 추상 메서드를 상속받는 클래스에서 구현하도록 강제
    # ➡️ BaseWidget 자체가 추상 클래스가 됨. 미구현 위젯은 인스턴스화 자체가 불가능해짐
    @abstractmethod
    def update_data(self, data: Any):
        """
        데이터 업데이트 (서브클래스에서 반드시 구현)
        
        Args:
            data: 업데이트할 데이터
            
        Raises:
            NotImplementedError: 서브클래스에서 구현하지 않은 경우
            
        예시:
            def update_data(self, data):
                self.label.setText(f"값: {data.value}")
                self.update()  # QPainter 사용 시 필요
        """
        raise NotImplementedError(
            f"{self.__class__.__name__}에서 update_data()를 구현해야 합니다"
        )
    
    def safe_update_data(self, data: Any) -> bool:
        """
        안전한 데이터 업데이트 (에러 처리 포함)

        완성된 코드. 호출해서 사용하기만 하면 됨.
        Controller 혹은 ViewModel 에서 호출
        
        MainViewModel에서 이 메서드를 호출하여
        모든 위젯에 안전하게 데이터를 전달
        
        Args:
            data: 업데이트할 데이터
            
        Returns:
            bool: 업데이트 성공 여부
            
        예시:
            # MainViewModel에서
            if widget.safe_update_data(new_data):
                print("업데이트 성공")
        """
        # 비활성화 상태면 업데이트 안함
        if not self._is_enabled:
            return False
        
        try:
            # 서브클래스의 update_data() 호출
            self.update_data(data)
            
            # 성공 시 저장 및 시그널 방출(emit)
            self._last_data = data
            self.data_updated.emit(data)
            
            return True
            
        except Exception as e:
            # 에러 발생 시 처리
            error_msg = f"{self.__class__.__name__} 업데이트 실패: {str(e)}"
            self.error_occurred.emit(error_msg)
            print(f"❌ {error_msg}")    # 나중에 `./utils/logger.py` 사용
            
            # 디버깅용 상세 정보
            import traceback
            traceback.print_exc()       # 나중에 `./utils/logger.py` 사용
            
            return False
    
    def get_last_data(self) -> Optional[Any]:
        """
        마지막으로 업데이트된 데이터 반환
        
        Returns:
            마지막 데이터 (없으면 None)
            
        예시:
            last_angle = turntable_widget.get_last_data()
        """
        return self._last_data
    
    def set_enabled(self, enabled: bool):
        """
        위젯 활성화/비활성화
        
        비활성화 시:
        - safe_update_data() 호출해도 업데이트 안됨
        - 시각적으로도 disabled 상태 표시
        
        Args:
            enabled: True면 활성화, False면 비활성화
            
        예시:
            # TwinCAT 연결 끊김 시
            for widget in all_widgets:
                widget.set_enabled(False)
        """
        self._is_enabled = enabled
        self.setEnabled(enabled)  # Qt의 기본 활성화/비활성화
    
    def is_widget_enabled(self) -> bool:
        """
        위젯 활성화 상태 확인
        
        Returns:
            bool: 활성화 여부
        """
        return self._is_enabled
    
    def clear_widget(self):
        """
        위젯 초기화 (서브클래스에서 오버라이드)
        
        이 메서드에서:
        - 표시된 데이터 지우기
        - 초기 상태로 복귀
        
        예시:
            def clear_widget(self):
                self.label.setText("데이터 없음")
                self._last_data = None
        """
        self._last_data = None


# ============================================
# 테스트 코드
# 나중에 tests/ 로 옮기기
# ============================================
if __name__ == '__main__':
    import sys
    from PyQt6.QtWidgets import QApplication, QLabel, QVBoxLayout
    
    # 테스트용 위젯
    class TestWidget(BaseWidget):
        def _init_ui(self):
            layout = QVBoxLayout()
            self.label = QLabel("대기 중...")
            self.label.setStyleSheet("font-size: 20px; padding: 20px;")
            layout.addWidget(self.label)
            self.setLayout(layout)
        
        def update_data(self, data):
            """데이터 업데이트 구현"""
            self.label.setText(f"받은 데이터: {data}")
        
        def clear_widget(self):
            """초기화"""
            self.label.setText("초기화됨")
            super().clear_widget()
    
    # 애플리케이션 실행
    app = QApplication(sys.argv)
    
    # 위젯 생성
    widget = TestWidget()
    widget.setWindowTitle("BaseWidget 테스트")
    widget.resize(400, 200)
    widget.show()
    
    # 에러 시그널 연결
    widget.error_occurred.connect(lambda msg: print(f"🔴 에러: {msg}"))
    widget.data_updated.connect(lambda data: print(f"🟢 업데이트 완료: {data}"))
    
    # 테스트 1: 정상 업데이트
    print("\n=== 테스트 1: 정상 업데이트 ===")
    success = widget.safe_update_data("테스트 데이터 123")
    print(f"결과: {'성공' if success else '실패'}")
    
    # 테스트 2: 비활성화 후 업데이트
    print("\n=== 테스트 2: 비활성화 ===")
    widget.set_enabled(False)
    success = widget.safe_update_data("이 데이터는 무시됨")
    print(f"결과: {'성공' if success else '실패 (예상된 동작)'}")
    
    # 테스트 3: 재활성화
    print("\n=== 테스트 3: 재활성화 ===")
    widget.set_enabled(True)
    success = widget.safe_update_data("다시 활성화!")
    print(f"결과: {'성공' if success else '실패'}")
    
    # 테스트 4: 초기화
    print("\n=== 테스트 4: 초기화 ===")
    widget.clear_widget()
    
    sys.exit(app.exec())




## 📋 BaseWidget 핵심 정리
"""
### **1. 역할**
✅ 인터페이스 통일
   - 모든 위젯이 update_data() 구현
   
✅ 안전성 보장
   - safe_update_data()로 에러 처리
   - 비활성화 상태 관리
   
✅ 코드 재사용
   - 공통 기능을 한 곳에
   - 유지보수 용이
"""