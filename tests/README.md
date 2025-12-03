# README

**`pytest`를 사용하여 `./tests/` 폴더 별도로 관리하는 것**이 파이썬 진영의 사실상 표준(De Facto Standard)이자 가장 추천하는 "제대로 된 테스트 구조"입니다.

`if __name__ == "__main__":` 방식은 파일 하나만 톡 건드려볼 때(Smoke Test)는 좋지만, 프로젝트가 커지면 관리가 불가능해집니다.

현업 수준의 \*\*"제대로 된 테스트 구조"\*\*가 무엇인지, 어떻게 세팅해야 하는지 정리해 드립니다.

-----

### **1. 추천 폴더 구조 (Directory Structure)**

프로덕션 코드(`core`, `utils` 등)와 테스트 코드(`tests`)를 물리적으로 완전히 분리합니다.

```text
KRISS_ROBOT_SYNC/
├── config/
├── core/
├── utils/
├── libs/
├── main.py
│
├── tests/                  # [테스트 전용 폴더]
│   ├── __init__.py
│   ├── conftest.py         # [핵심] 공통 설정 및 '픽스처(Fixture)' 정의
│   ├── pytest.ini          # pytest 설정 파일
│   │
│   ├── unit/               # [단위 테스트] : 외부 의존성 없이 로직만 검증 (빠름)
│   │   ├── test_startup.py
│   │   └── test_settings.py
│   │
│   └── integration/        # [통합 테스트] : 실제 파일 I/O나 DB 연결 테스트 (느림)
│       └── test_file_handler.py
```

-----

### **2. 핵심 도구: `pytest`**

`unittest`보다 `pytest`를 강력 추천하는 이유는 다음과 같습니다.

1.  **간결함:** `self.assertEqual(a, b)` 대신 그냥 `assert a == b`라고 쓰면 됩니다.
2.  **픽스처(Fixture):** `setUp`, `tearDown`보다 훨씬 강력하고 유연한 **`conftest.py`** 시스템을 제공합니다.
3.  **플러그인:** `pytest-qt` (Qt GUI 테스트용), `pytest-mock` (모킹용) 등 생태계가 강력합니다.

-----

### **3. 실제 작성 예시**

질문하신 `StartupManager`를 "제대로 된 구조"에서 테스트하는 코드를 보여드릴게요.

#### **(1) 준비: 패키지 설치**

```bash
pip install pytest pytest-mock pytest-qt
```

#### **(2) 공통 설정: `tests/conftest.py`**

테스트할 때마다 `QApplication`을 만들었다 지웠다 하면 에러가 납니다. 이걸 여기서 한 번만 만들어 줍니다.

```python
# tests/conftest.py
import pytest
from PyQt6.QtWidgets import QApplication
import sys

# 모든 테스트가 공유하는 '가짜 앱' 준비물
@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app
```

#### **(3) 개별 테스트 테스트 코드 작성: `tests/test_테스트코드이름.py`**


#### **(4) 실행 방법**

- 전체 실행 방법
  - 터미널에서 명령어 한 줄이면 테스트 폴더 안에 있는 모든 테스트가 돌아갑니다.

```bash
$ pytest
```

- 개별 실행 방법
    - 테스트 파일별 개별 실행
```bash
$ pytest tests/unit/테스트파일이름.py
```
-----

### **4. 왜 이 구조가 좋은가?**

1.  **배포 코드 오염 방지:** `core/startup.py` 파일 안에 테스트 코드가 섞여 있으면, 실제 배포할 때 불필요한 코드가 같이 나갑니다. 분리하는 게 깔끔합니다.
2.  **자동화 (CI/CD):** 나중에 GitHub나 GitLab에 코드를 올릴 때, `pytest` 명령어로 모든 테스트를 자동으로 돌려서 "이 코드가 기존 기능을 망가뜨리지 않았는지" 검증할 수 있습니다.
3.  **가독성:** 비즈니스 로직은 `src`에서, 검증 로직은 `tests`에서 관리하므로 목적이 명확합니다.
