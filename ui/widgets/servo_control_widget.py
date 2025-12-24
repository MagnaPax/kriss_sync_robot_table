# ui/widgets/servo_control_widget.py
from ui.widgets.base_widget import BaseWidget
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from view_models.servo_control_viewmodel import ServoControlViewModel



class ServoControlWidget(BaseWidget):
    """서보모터 제어용 위젯"""
