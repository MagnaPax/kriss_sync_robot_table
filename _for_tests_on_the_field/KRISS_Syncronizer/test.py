"""
리턴값:
    List[Dict[str, Any]]: 아래 구조를 가진 딕셔너리들의 리스트
    
    [데이터 키 - CSV 기준]
    - 'turntable_feed_rate' (float):        턴테이블 이동 속도
    - 'polar_coord_theta' (float):          극좌표계 각도(Theta, deg). 턴테이블 회전량으로 사용됨.
    - 'polar_coord_radius' (float):         극좌표계 반지름(Radius, mm). 로봇의 수평 이동 거리(X).
    - 'paraboloid_height' (float):          쌍곡포물면 높이(Z, mm). 로봇의 수직 높이(Z).
    - 'tool_stroke_rpm' (float):            툴 스트로크(B) 속도
"""


from robot_sequence_loader import load_robot_sequence

sequence = load_robot_sequence("sequence_sample.csv")
print(sequence)
