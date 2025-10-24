> [!note] 질문
> `update_data` 와 `safe_update_data` 차이가 뭐야?

<br>

`update_data`와 `safe_update_data`는 "작업자"와 "안전 관리자"의 관계입니다.

* `update_data` (작업자 👷‍♀️): **실제로 UI를 변경하는** 코드.
* `safe_update_data` (안전 관리자 🛡️): 작업자가 **안전하게** 일할 수 있도록 확인하고, 문제가 생기면 **처리**하는 코드.

프로그램의 다른 부분(예: 메인 컨트롤러)은 **항상 "안전 관리자"(`safe_update_data`)만 호출**해야 합니다.

---

### ## `update_data` (the "Worker" 👷‍♀️)

* **역할:** 위젯 개발자(사용자)가 **직접 코드를 짜야 하는** 부분입니다. (`@abstractmethod`)
* **기능:** `data`를 받아서 `self.label.setText(data)`처럼 실제 UI를 업데이트하는 "알맹이" 로직입니다.
* **특징:** 이 메서드 자체에는 에러 처리나 상태 확인 기능이 없습니다. 만약 `data`가 `None`인데 `data.value`를 호출하려 하면 프로그램이 멈출 수 있습니다.

**당신이 할 일:** `StatusIndicator`, `TurntableGauge` 등 모든 위젯에서 이 메서드를 **재정의(override)**하여 UI 변경 코드를 작성해야 합니다.

---

### ## `safe_update_data` (the "Manager" 🛡️)

* **역할:** `BaseWidget`에 **이미 완성되어 있는** 메서드입니다.
* **기능:** "안전 관리자"로서, "작업자"(`update_data`)를 호출하기 전후로 2가지 안전장치를 확인합니다.
* **특징:**
    1.  **활성화 확인:** `if not self._is_enabled:` 위젯이 비활성화 상태면, "작업자"를 부르지 않고 즉시 작업을 거부(return `False`)합니다.
    2.  **에러 처리:** `try...except` 블록으로 "작업자"의 작업을 감시합니다.
        * **성공 시 (`try`):** `update_data`를 실행하고, 데이터를 저장하며, `data_updated` 시그널을 보냅니다.
        * **실패 시 (`except`):** "작업자"가 에러를 내도 프로그램이 죽지 않습니다. 대신, `error_occurred` 시그널을 보내고 에러를 기록합니다.

**당신이 할 일:** 이 메서드는 **호출(call)**해서 사용합니다. (예: `my_widget.safe_update_data(...)`)

---

### ## 작동 방식 요약

**1. 호출 (Call):**
   `Controller` ➡️ `safe_update_data(data)`

**2. 관리자(`safe_update_data`)의 확인:**
   "위젯이 활성화되어 있나?" (Yes)
   "이제 `try` 블록으로 작업자(`update_data`)를 호출하자."

**3. 작업자(`update_data`)의 실행:**
   `self.label.setText(data)` (실제 UI 변경)

**4. 관리자의 마무리:**
   "작업 성공! `data_updated` 시그널 방출!" (또는 "작업 실패! `error_occurred` 시그널 방출!")

| 구분 | `update_data` | `safe_update_data` |
| :--- | :--- | :--- |
| **누가 만드나?** | **위젯 개발자 (당신)** | `BaseWidget` (이미 완성됨) |
| **누가 호출하나?** | `safe_update_data` (내부적으로) | **컨트롤러 (외부에서)** |
| **역할** | UI 변경 (실제 작업) | 에러 처리, 상태 확인 (안전 관리) |
| **필수 여부** | **반드시 재정의(override) 해야 함** | 재정의(override) 하면 안 됨 |

---
---

<br>
<br>
<br>


> [!note] 질문
> safe_update_data 를 외부 컨트롤러에서 호출한다는 것이 이해가 잘 안 된다. 내 코드 `./main.py`, `/ui/main_window.py` 에서 호출 한다는거야? 아니면 다른 곳에서 호출 하는건가?

<br>

네, 정확한 질문입니다. '외부 컨트롤러'가 무엇인지, 그리고 `main.py`나 `main_window.py`와 무슨 관계인지 혼란스러우실 수 있습니다.

**결론부터 말씀드리면, `safe_update_data`는 `main.py`나 `main_window.py`에서 직접 호출하는 것이 아닙니다.**

'외부 컨트롤러'는 이 UI(화면)와 실제 로직(데이터)을 **연결해 줄 "두뇌" 역할의 객체**이며, **아직 만들지 않은 부분**입니다.

---

### ## 1. 지금 하신 작업 (View - 화면)

`main.py` -> `MainWindow` -> `LeftPanel` -> `StatusIndicatorBox`

지금까지의 작업은 UI 뼈대를 만들고, 위젯이라는 부품을 조립하는 **"화면(View)"** 작업이었습니다. `safe_update_data`는 이 부품(위젯)들이 데이터를 받을 수 있도록 "안전한 문(API)"을 만들어 둔 것입니다.

### ## 2. 앞으로 하실 작업 (Controller - 제어)

이제 이 "문"을 **누가, 언제 두드릴지** 정해야 합니다. 그 "누가"가 바로 **"컨트롤러(Controller)"** 또는 **"뷰-모델(ViewModel)"**입니다.

사용자님의 프로젝트 구조(`kriss_sync_robot_turn_table`)에 따르면, 이 컨트롤러의 역할은 다음과 같습니다.

1.  **데이터 수신:** `communication/twincat_client.py`를 사용해 PLC로부터 실제 로봇 데이터(예: 각도, 상태)를 주기적으로 받아옵니다.
2.  **데이터 가공:** 받아온 데이터를 UI 위젯이 이해할 수 있는 형태(예: `dict`)로 가공합니다.
3.  **데이터 전달:** **`MainWindow`가 가지고 있는** 각 위젯에 접근하여, `safe_update_data(data)`를 **호출**합니다.

### ## 3. 데이터 흐름 (예상)

`safe_update_data`가 호출되는 흐름은 다음과 같을 것입니다.

**[PLC 장비]**
&nbsp;&nbsp;⬇️
**1. `twincat_client.py` (통신 계층)**
   - "PLC에서 데이터 'angle=30.5' 받음!"
&nbsp;&nbsp;⬇️
**2. `MainController.py` (새로 만들 '컨트롤러' 🧠)**
   - `twincat_client`로부터 "angle=30.5" 신호를 받음.
   - "이 데이터는 `TurntableGauge` 위젯이 필요하군."
   - `self.main_window.left_panel.turntable_widget.safe_update_data({'angle': 30.5})` **<-- 💥 여기서 호출!**
&nbsp;&nbsp;⬇️
**3. `base_widget.py` (`safe_update_data`)**
   - "위젯 활성화 상태인가? (O)"
   - "에러 없이 `update_data`를 호출하자."
&nbsp;&nbsp;⬇️
**4. `turntable_gauge.py` (`update_data`)**
   - "데이터 30.5로 화살표 각도를 돌리자." (UI 변경)

### ## 요약

* `main.py`, `main_window.py`는 위젯을 **생성하고 조립**합니다.
* **'외부 컨트롤러'** (새로 만들 파일, 예: `MainController.py`)는 `twincat_client` 같은 곳에서 데이터를 받아와, `main_window`에 조립된 위젯들의 `safe_update_data`를 **호출(Call)**합니다.