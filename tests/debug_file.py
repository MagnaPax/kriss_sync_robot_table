
import sys
import os

with open("tests/debug_output.txt", "w", encoding="utf-8") as f:
    f.write("Start Debug Imports\n")
    f.flush()
    
    import sys
    import os
    f.write("path imported\n")
    f.flush()
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    f.write("Importing pyads...\n")
    f.flush()
    try:
        import pyads
        f.write("pyads imported\n")
    except ImportError as e:
        f.write(f"pyads failed: {e}\n")
    f.flush()

    f.write("Importing PyQt6...\n")
    f.flush()
    try:
        from PyQt6.QtCore import QCoreApplication
        f.write("PyQt6 imported\n")
    except ImportError as e:
        f.write(f"PyQt6 failed: {e}\n")
    f.flush()

    f.write("Importing utils...\n")
    f.flush()
    try:
        from utils.logger import get_logger
        f.write("utils imported\n")
    except ImportError as e:
        f.write(f"utils failed: {e}\n")
    f.flush()

    f.write("Importing TwinCATCommander...\n")
    f.flush()
    try:
        from communication.twincat_commander import TwinCATCommander
        f.write("TwinCATCommander imported\n")
    except ImportError as e:
        f.write(f"TwinCATCommander failed: {e}\n")
    f.flush()

    f.write("All imports done\n")
    f.flush()
