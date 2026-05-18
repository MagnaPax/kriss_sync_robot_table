# Korea Research Institute of Standards and Science
## Robot-Turntable Synchronizer

이 프로젝트는 **KRISS 다축 제어기 H/W Upgrade 및 EtherCAT을 이용한 동기화 시스템** 개발에 참여하는 새로운 개발자가 프로젝트를 원활하게 파악하고 이어서 개발할 수 있도록 작성된 가이드 및 설명서입니다.

---

## 1. 환경 설정 및 배포 (`./config/settings.ini`)

애플리케이션의 주요 설정은 하드코딩을 피하고 `settings.ini` 파일을 통해 관리됩니다. 개발 및 배포 환경에 따라 다음 항목들을 반드시 확인하고 수정해야 합니다.

*   **앱 실행 모드 설정**
    *   `DEBUG`: 개발 중에는 상세 로그 확인을 위해 `True`로 설정하고, 배포 시에는 성능과 로그 가독성을 위해 `False`로 변경합니다.
*   **TwinCAT 통신 설정**
    *   `AMS_NET_ID`: 연결하려는 TwinCAT PLC의 네트워크 ID입니다. 환경에 따라 주석 처리된 부분을 활성화하여 사용합니다.
    *   `DEMO_MODE`: 실제 PLC 하드웨어 없이 UI나 로직 단독 테스트 시 `True`로 설정합니다. 배포나 실제 장비 연동 시에는 반드시 `False`로 변경해야 합니다.

---

## 2. 애플리케이션 실행 구조 (`main.py`)

앱의 진입점(Entry Point)은 `main.py`입니다. 앱의 실행 흐름은 UI와 인프라가 엄격히 분리되어 동작합니다.

1.  **`AppEngine` 초기화**: 애플리케이션의 뼈대(인프라)를 구성하는 싱글톤 객체입니다. `sys.argv`를 받아 초기화되며, 예외 처리, 테마 설정, 기본 로깅 디렉터리 등을 설정합니다. (`app.bootstrap()`)
2.  **`LogListener` 연결**: `EventBus`를 통해 시스템 곳곳에서 발생하는 신호들을 수집하여 Logger에 전달하는 중재자를 생성합니다. (가비지 컬렉션을 막기 위해 변수에 할당)
3.  **`StartupManager` 실행**: 애플리케이션의 부팅 시나리오를 전담합니다. 스플래시 화면 출력 -> 장비 통신(TwinCAT) 접속 시도 -> 접속 결과에 따라 메인 윈도우(UI)를 띄우는 일련의 실행 흐름(Flow)을 관장합니다.

---

## 3. 사용자 이벤트 발생 시 흐름 (Event Flow)

애플리케이션 내부 통신은 느슨한 결합(Decoupling)을 위해 **EventBus**(`core.event_bus.EVENT_BUS`)를 적극 활용합니다. 사용자 동작부터 실제 장비 구동까지의 대략적인 흐름은 다음과 같습니다.

1.  **UI 이벤트 발생**: 사용자가 View(GUI)에서 버튼 클릭 (예: "실행" 버튼).
2.  **ViewModel 및 Commander 호출**: View에 바인딩된 ViewModel이 이를 감지하고, 비즈니스 로직 층(`TwinCATCommander` 등)에 명령을 하달합니다.
3.  **Strategy 패턴 선택**: 주어진 데이터 형태(로봇/서보 여부)에 따라 알맞은 `ExecutionStrategy`(예: `IntegratedExecutor`)가 선택됩니다.
4.  **백그라운드 실행**: 장비 제어는 메인 UI가 멈추지(Freeze) 않도록 **별도의 QThread 또는 ThreadPoolExecutor** 내에서 비동기로 수행됩니다.
5.  **EventBus 상태 알림**: 실행 상태, 로그 메시지, 장비 피드백(진행률 등)은 다시 EventBus(`EVENT_BUS.log.message.emit` 등)를 통해 Broadcast 되며, 이를 수신하는 View나 LogListener가 화면을 갱신합니다.

---

## 4. PLC 신호 상수 위치 (Models)

오타를 방지하고 유지보수성을 높이기 위해 장비와 통신하는 모든 PLC 메모리 주소(Tag Name)는 Enum(상수)으로 관리됩니다.

*   **FANUC 로봇 신호**: `models/fanuc_pose_key.py`
    *   `FANUCPoseKey`: 좌표축(X, Y, Z, W, P, R) 상수
    *   `FanucSignal`: 로봇 제어 신호. UO/UI 비트 및 버퍼 송신용 PLC 변수명(예: `MAIN.Robot1._UI1.UI09_RSR1`, `MAIN.send_buffer1_1` 등)
*   **Panasonic 서보 모터 신호**: `models/servo_pose_key.py`
    *   `ServoAxis`: 서보 모터 축 번호 매핑 (1: 턴테이블, 2: 툴 공전, 3: 툴 자전)
    *   `ServoSignal`: 동적 주소 템플릿. `.get_plc_path(axis_index)`를 호출하여 `"MAIN.bServoOn1"`, `"MAIN.lVel2"` 등 축 번호가 조합된 정확한 PLC 변수명을 반환합니다.

---

## 5. 비즈니스 로직 실행부 (`communication/execution_strategies.py`)

주어진 경로 데이터(CSV 등)를 기반으로 기기들을 어떻게 동기화하여 구동할지 결정하는 **"The How"** 로직의 핵심입니다.

*   **`IntegratedExecutor` (로봇-모터 통합 제어)**:
    *   중요한 로직. 로봇과 턴테이블이 완벽히 동기화되어 움직여야 할 때 쓰입니다.
    *   **동작 방식**: `concurrent.futures.ThreadPoolExecutor`를 사용해 로봇 스레드와 서보 스레드를 동시에 구동합니다.
    *   두 스레드가 각각의 초기 버퍼(Pre-load Data)를 장비로 모두 전송(Handshake)할 때까지 대기(Polling)합니다.
    *   장전이 완료되면 메인 스레드가 **동시 출발 Trigger 신호(`RSR1`)** 를 날립니다.
    *   이후 두 스레드는 각자의 버퍼가 고갈되지 않도록 무한 루프를 돌며 남은 데이터를 스트리밍(Streaming)합니다.
*   **`FanucOnlyExecutor`**: 로봇만 단독으로 움직일 때 사용합니다.
*   **`ServoOnlyExecutor`**: 서보 모터만 단독으로 테스트할 때 사용합니다.
*   `BaseExecutor`를 상속받아 구현되어 있으며, 모두 **사용자의 중단 요청(`_is_interrupted()`)**을 주기적으로 감시하여 안전하게 루프를 빠져나오도록 설계되었습니다.

---

## 6. 장비 제어 어댑터 (Adapter Layer)

실제로 `pyads` 라이브러리를 통해 PLC 메모리에 Read/Write를 수행하는 최하단 계층입니다. **스스로 판단하지 않고 Execution Strategy가 지시하는 대로 움직입니다.**

*   **`communication/fanuc_adapter.py`**
    *   파낙 로봇과의 직접적인 통신을 담당합니다.
    *   로봇이 동작 가능한 상태인지(`has_fault()`), 현재 좌표가 어디인지 읽어옵니다.
    *   데이터 버퍼 청크를 쪼개어 PLC로 전송하고(`FR_send_to_plc_group`), Service Code, Class, Instance 정보를 조작하여 로봇 컨트롤러에 Explicit Message를 발생시킵니다.
*   **`communication/servo_adapter.py`**
    *   3축 파나소닉 서보 모터를 제어합니다.
    *   축 번호에 따라 전원 인가, 리셋, Homing 처리를 수행하며 절대 위치 이동(턴테이블)이나 속도 모드(공전/자전) 신호를 전송합니다.
    *   `execute_synchronized_motion()`: 3개 축에 대해 `write_list_by_name`으로 원자적(Atomic) 동시 명령을 내리는 핵심 함수입니다.
    *   `watch_buffer_update()`: PLC에서 버퍼가 비어갈 즈음 하단/상단 버퍼 교체 요청(Req Lower/Upper)을 보내면 이를 감지하여 새로운 500개의 데이터를 올려주는 역할을 수행합니다.

---

## 7. 차기 개발자를 위한 당부 및 팁 (Tip & Tricks)

**안전과 직결된 중단 로직 (Interrupt Handling)**  
    *   `execution_strategies.py`의 루프 로직에는 `if self._is_interrupted(): break` 또는 에러 raise 코드가 곳곳에 배치되어 있습니다. 로봇과 턴테이블이 움직이는 도중 사용자가 [정지] 버튼을 눌렀을 때 즉시 감지하여 멈춰야 하기 때문입니다. 새로운 전략을 짤 때 이 폴링 감시 코드를 절대 누락하지 마세요.  

**예외 처리 릴레이 (Exception Propagation)**  
    *   어댑터 레이어(Fanuc, Servo Adapter)에서 발생한 에러(`ServoBusyError`, `pyads.ADSError` 등)는 내부에서 조용히 처리(swallow)하지 말고 반드시 `raise`하여 `ExecutionStrategy` 레이어까지 끌어올리세요.  
    *   통합 실행부의 최상단 `try-except`에서 에러를 취합하여 EventBus로 알리고 장비에 긴급 정지(Immediate Stop)를 명령하는 구조입니다.  

**타입 힌팅 및 순환 참조 방지**  
    *   `TYPE_CHECKING` 구문을 활용하여 런타임 순환 참조를 방지하면서도 IDE에서 타입 힌트와 자동 완성을 원활하게 받을 수 있도록 구성되어 있습니다. 코드를 확장할 때 이 패턴을 준수하면 유지보수에 큰 도움이 됩니다.  
