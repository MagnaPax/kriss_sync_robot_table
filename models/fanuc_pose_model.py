# models/fanuc_pose_model.py
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Dict, Any


@dataclass(frozen=True, slots=True)
class FANUCPose:
    """
    FANUC 로봇 좌표 데이터 모델 (앱 도메인 모델)

        목적:
            로봇 포즈를 사람이 이해하기 좋은 형태로 표현한 값
            실제 로봇 포즈 저장
            
        용도:
            내부 로직용: ViewModel, Service, Worker 사이에서 데이터를 주고받을 때 사용

        역할:
            데이터 모델

        동작:
            좌표 데이터가 상태(state)
        
        Attributes:
            x (float): X축 좌표 (mm) - 로봇 베이스 기준 전후
            y (float): Y축 좌표 (mm) - 로봇 베이스 기준 좌우
            z (float): Z축 좌표 (mm) - 로봇 베이스 기준 상하
            w (float): W (Yaw) - X축 기준 회전 각도 (deg)
            p (float): P (Pitch) - Y축 기준 회전 각도 (deg)
            r (float): R (Roll) - Z축 기준 회전 각도 (deg)
            f (float): Feed Rate - 이동 속도 (mm/sec)
    """
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    w: float = 0.0
    p: float = 0.0
    r: float = 0.0
    f: float = 0.0  # 속도 정보

    def to_dict_with_meaningful_names(self) -> Dict[str, float]:
        return {"feed_rate":self.f, "axis_x": self.x, "axis_y": self.y, "axis_z": self.z, "yaw_w": self.w, "pitch_p": self.p, "roll_r": self.r}
    
    def to_dict_preserving_key_names(self) -> Dict[str, Any]:
        # dataclasses.asdict를 쓰면 자동으로 딕셔너리가 된다(키값은 똑같음)
        return asdict(self)


class FANUCPoseModel:
    """
    FANUCPose 객체 생성을 담당하는 팩토리(Factory) 및 검증 클래스
    
    역할:
        1. 외부 데이터(JSON, Dict)의 유효성 검사 (Validation)
        2. 안전한 타입 변환 (str -> float)
        3. 도메인 객체(FANUCPose) 생성 및 반환
        
    이 클래스는 상태를 가지지 않으므로(Stateless), 모든 메서드는 정적(@staticmethod)이다
    """

    def do_task(self) -> str:
        msg: str = "Hello, MVVM"
        return msg
    

    @staticmethod
    def parse_poses_from_data(data: Dict[str, Any]) -> Dict[str, FANUCPose]:
        """
        매크로 파일 내용(Dict)을 파싱하여 FANUCPose 객체들의 딕셔너리로 변환

        설명:
            파일에서 읽어온 Raw Data를 
            앱에서 안전하게 쓸 수 있는 객체(Object)로 대량 변환
            그 과정에서 데이터 구조가 올바른지 검사

        Args:
            data (Dict[str, Any]): JSON 파일에서 로드한 원본 데이터
                                예: {'Macro_1': {'x': 100, ...}, ...}

        Returns:
            Dict[str, FANUCPose]: 변환된 매크로 ID와 포즈 객체의 맵
                                예: {'Macro_1': FANUCPose(...), ...}

        Raises:
            TypeError: 입력받은 데이터가 딕셔너리가 아닐 때
            ValueError: 내부 데이터 구조가 잘못되었거나, 데이터가 비어있을 때
        """

        result: Dict[str, FANUCPose] = {}

        for macro_id, macro_data in data.items():
            if not isinstance(macro_data, dict):
                raise ValueError(f"매크로 '{macro_id}'의 데이터 형식이 올바르지 않습니다 (dict여야 함).")

            # 개별 포즈 생성 위임
            pose = FANUCPoseModel._create_pose(macro_data, macro_id)
            result[macro_id] = pose

        if not result:
            raise ValueError("로드된 매크로 데이터가 없습니다 (빈 파일).")

        return result

    @staticmethod
    def _create_pose(macro_data: Dict[str, Any], macro_id: str) -> FANUCPose:
        """
        (내부 헬퍼) 단일 딕셔너리 데이터를 FANUCPose 객체로 변환한다

        설명:
            - 필수 키(x, y, z, w, p, r)가 모두 있는지 검사
            - 값이 숫자로 변환 가능한지 확인 (문자열 "10.5" -> 실수 10.5)
            - 하나라도 문제가 있으면 즉시 에러를 발생시켜 잘못된 데이터가 흐르는 것을 방지

        Args:
            macro_data (Dict): 매크로 하나의 데이터 (예: {'x': 10, 'y': 20 ...})
            macro_id (str): 에러 메시지에 표시할 매크로 ID

        Returns:
            FANUCPose: 생성된 불변(Frozen) 데이터 객체
        """
        def get_float(key: str) -> float:
            value = macro_data.get(key)
            if value is None:
                raise KeyError(f"매크로 '{macro_id}' 데이터에 필수 키 '{key}'가 누락되었습니다.")
            try:
                return float(value)
            except (TypeError, ValueError):
                raise ValueError(f"매크로 '{macro_id}'의 '{key}' 값이 숫자가 아닙니다: {value}")

        # f(Feed)는 필수가 아니므로 get을 사용 (기본값 0.0)
        feed_val = macro_data.get('f', 0.0)
        try:
            feed_val = float(feed_val)
        except:
            feed_val = 0.0

        return FANUCPose(
            x=get_float("x"),
            y=get_float("y"),
            z=get_float("z"),
            w=get_float("w"),
            p=get_float("p"),
            r=get_float("r"),
            f=feed_val
        )

    @staticmethod
    def get_pose(macros: Dict[str, FANUCPose], macro_id: str) -> FANUCPose:
        """
        변환된 매크로 목록에서 특정 ID의 포즈를 안전하게 가져온다

        설명:
            단순히 macros[id]를 하는 것보다, 
            찾는 키가 없을 때 더 명확한 에러 메시지를 제공하기 위해 사용

        Args:
            macros (Dict): 파싱이 완료된 FANUCPose 딕셔너리
            macro_id (str): 찾고 싶은 매크로 ID

        Returns:
            FANUCPose: 해당 ID의 포즈 객체

        Raises:
            KeyError: 해당 ID가 존재하지 않을 때
        """
        try:
            return macros[macro_id]
        except KeyError:
            raise KeyError(f"요청한 매크로 ID '{macro_id}'를 찾을 수 없습니다.")





# ==========================================================
# Smoke Test
"""
실행 명령어
python -m models.pose_model
"""
# ==========================================================
if __name__ == '__main__':
    
    print("=" * 70)
    print("FANUCPoseModel 단독 실행 테스트")
    print("=" * 70)

    # --- 테스트용 샘플 데이터 ---
    # (MacroSettingsDialog가 생성하는 JSON 파일의 내용과 유사)
    sample_json_data = {
        "Macro_1": {
            "macro_id": "Macro_1", 
            "name": "매크로 1 이름", 
            "x": 100.1, 
            "y": 200.2, 
            "z": 0.0, 
            "w": 0.0, 
            "p": 0.0, 
            "r": 10.0
        },
        "Macro_2": {
            "macro_id": "Macro_2", 
            "name": "매크로 2 이름", 
            "x": 111.0, 
            "y": 222.0, 
            "z": 333.0, 
            "w": 44.0, 
            "p": 55.0, 
            "r": 66.0
        }
    }

    # 파싱 결과를 담을 변수를 미리 초기화한다
    poses: Dict[str, FANUCPose] = {}

    # 1. 파싱 성공 테스트
    print("\n1️⃣  파싱 성공 테스트:")
    try:
        poses = FANUCPoseModel.parse_poses_from_data(sample_json_data)
        print(f"   ✅ 파싱 성공. {len(poses)}개 매크로 로드됨.")
        print(f"   Macro_1 FANUCPose: {poses['Macro_1']}")
        print(f"   Macro_2 FANUCPose: {poses['Macro_2']}")
        
        # 2. 특정 FANUCPose 가져오기 테스트
        print("\n2️⃣  get_pose() 성공 테스트:")
        pos1 = FANUCPoseModel.get_pose(poses, "Macro_1")
        print(f"   ✅ 'Macro_1' 가져오기 성공: {pos1}")
        assert pos1.x == 100.1
        
    except (TypeError, ValueError, KeyError) as e:
        print(f"   ❌ 테스트 실패: {e}")

    # 3. 파싱 실패 테스트 (필수 키 누락)
    print("\n3️⃣  파싱 실패 테스트 (필수 키 'x' 누락):")
    invalid_data_missing_key = {
        "Macro_Bad": { "y": 1.0, "z": 1.0, "w": 0, "p": 0, "r": 0 }
    }
    try:
        FANUCPoseModel.parse_poses_from_data(invalid_data_missing_key)
    except KeyError as e:
        print(f"   ✅ 의도된 예외 발생(KeyError): {e}") #
    except Exception as e:
        print(f"   ❌ 잘못된 예외 발생: {type(e).__name__}: {e}")

    # 4. 파싱 실패 테스트 (잘못된 값 타입)
    print("\n4️⃣  파싱 실패 테스트 (잘못된 값 타입):")
    invalid_data_bad_type = {
        "Macro_Bad2": { "x": "NotANumber", "y": 1, "z": 1, "w": 0, "p": 0, "r": 0 }
    }
    try:
        FANUCPoseModel.parse_poses_from_data(invalid_data_bad_type)
    except ValueError as e:
        print(f"   ✅ 의도된 예외 발생(ValueError): {e}") #
    except Exception as e:
        print(f"   ❌ 잘못된 예외 발생: {type(e).__name__}: {e}")
        
    # 5. get_pose 실패 테스트
    print("\n5️⃣  get_pose() 실패 테스트 (없는 ID):")
    try:
        FANUCPoseModel.get_pose(poses, "Macro_99")
    except KeyError as e:
        print(f"   ✅ 의도된 예외 발생(KeyError): {e}") #
    except Exception as e:
        print(f"   ❌ 잘못된 예외 발생: {type(e).__name__}: {e}")

    print("\n" + "=" * 70)
    print("테스트 완료")
    print("=" * 70)