# communication/turntable_adapter.py
"""[Model] 테이블 제어용 로직"""



class TurntableAdapter:
    """테이블 제어용 로직"""

    def __init__(self, connector):
        self.connector = connector
