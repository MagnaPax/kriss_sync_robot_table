# models/fanuc_pose_model.py
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Dict, Any


@dataclass(frozen=True, slots=True)
class FANUCPose:
    """
    불변 좌표 객체
    로봇이 움직이는 데 필요한 모든 정보
    """
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    w: float = 0.0
    p: float = 0.0
    r: float = 0.0
    feed: float = 0.0  # 속도 정보

    def to_dict(self) -> Dict[str, float]:
        return {"x": self.x, "y": self.y, "z": self.z, "w": self.w, "p": self.p, "r": self.r}
    
    def to_unified_dict(self) -> Dict[str, Any]:
        # dataclasses.asdict를 쓰면 자동으로 딕셔너리가 된다
        return asdict(self)



class FANUCPoseModel:
    """
    순수 비즈니스 로직
    """
    def do_task(self) -> str:
        msg: str = "Hello, MVVM"
        return msg
    

    @staticmethod
    def parse_poses_from_data(data: Dict[str, Any]) -> Dict[str, FANUCPose]:
        """
        매크로 딕셔너리 데이터를 FANUCPose 객체 딕셔너리로 파싱(변환)
        실패 시 예외 발생 → Worker가 잡아야 함
        """
        if not isinstance(data, dict):
            raise TypeError("매크로 데이터는 dict 형식이어야 합니다.")

        result: Dict[str, FANUCPose] = {}

        for macro_id, macro_data in data.items():
            if not isinstance(macro_data, dict):
                raise ValueError(f"매크로 '{macro_id}'의 데이터가 dict가 아닙니다.")

            pose = FANUCPoseModel._create_pose(macro_data, macro_id)
            result[macro_id] = pose

        if not result:
            raise ValueError("로드된 매크로가 하나도 없습니다.")

        return result

    @staticmethod
    def _create_pose(macro_data: Dict[str, Any], macro_id: str) -> FANUCPose:
        """
        단일 매크로에서 FANUCPose 생성
        변환 실패 시 명확한 예외
        """
        def get_float(key: str) -> float:
            value = macro_data.get(key)
            if value is None:
                raise KeyError(f"매크로 '{macro_id}'에 필수 키 '{key}'가 없습니다.")
            try:
                return float(value)
            except (TypeError, ValueError):
                raise ValueError(f"매크로 '{macro_id}'의 '{key}' 값이 숫자가 아닙니다: {value}")

        return FANUCPose(
            x=get_float("x"),
            y=get_float("y"),
            z=get_float("z"),
            w=get_float("w"),
            p=get_float("p"),
            r=get_float("r")
        )

    @staticmethod
    def get_pose(macros: Dict[str, FANUCPose], macro_id: str) -> FANUCPose:
        """
        매크로 ID로 FANUCPose 반환
        없으면 KeyError → Worker가 처리
        """
        try:
            return macros[macro_id]
        except KeyError:
            raise KeyError(f"매크로 '{macro_id}'를 찾을 수 없습니다.")





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

    # 파싱 결과를 담을 변수를 미리 초기화합니다.
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