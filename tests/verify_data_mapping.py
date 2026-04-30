import sys
import os

# 프로젝트 루트 경로 추가 (모듈 임포트를 위해)
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from config.data_formats import CSV_SCHEMA, KEY_ROBOT_X, KEY_ROBOT_Z, KEY_TURNTABLE_DEG, KEY_TOOL_REV_RPM, KEY_TOOL_ROT_RPM
from parsers.sequence_parser import SequenceCsvParser

def test_csv_mapping():
    print("=== Testing CSV Mapping ===")
    
    # Test Data: Header + Row
    # U=90, X=500, Z=200, B=1500, C=300
    row_data = [
        'PRLINE', '1', 
        'U', '90.0', 
        'X', '500.0', 
        'Z', '200.0', 
        'B', '1500.0', 
        'C', '300.0'
    ]
    
    # Wrap in list of lists as parser expects
    data = [row_data]
    
    parser = SequenceCsvParser()
    try:
        parsed_result = parser.parse(data)
        print("Parsing Successful.")
        
        # Parser uses string keys for IDs usually
        item = parsed_result.get("1") or parsed_result.get(1)
        if item is None:
            # Fallback: print keys to see what happened
            print(f"Keys found: {list(parsed_result.keys())}")
            raise KeyError("ID '1' not found in parsed result")
            
        print(f"Parsed Item: {item}")
        
        # Verify Mappings
        assert item[KEY_TURNTABLE_DEG] == 90.0, f"U Mapping Failed: {item.get(KEY_TURNTABLE_DEG)}"
        assert item[KEY_ROBOT_X] == 500.0, f"X Mapping Failed: {item.get(KEY_ROBOT_X)}"
        assert item[KEY_ROBOT_Z] == 200.0, f"Z Mapping Failed: {item.get(KEY_ROBOT_Z)}"
        assert item[KEY_TOOL_REV_RPM] == 1500.0, f"B Mapping Failed: {item.get(KEY_TOOL_REV_RPM)}"
        assert item[KEY_TOOL_ROT_RPM] == 300.0, f"C Mapping Failed: {item.get(KEY_TOOL_ROT_RPM)}"
        
        print("All assertions passed!")
        print("Mapping is CORRECT.")
        return True
    except Exception as e:
        print(f"Test Failed: {e}")
        return False

if __name__ == "__main__":
    test_csv_mapping()
