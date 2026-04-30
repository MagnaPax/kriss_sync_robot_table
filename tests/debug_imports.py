
print("Start Debug Imports")
import sys
import os
print("path imported")
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("Importing pyads...")
try:
    import pyads
    print("pyads imported")
except ImportError as e:
    print(f"pyads failed: {e}")

print("Importing PyQt6...")
try:
    from PyQt6.QtCore import QCoreApplication
    print("PyQt6 imported")
except ImportError as e:
    print(f"PyQt6 failed: {e}")

print("Importing utils...")
try:
    from utils.logger import get_logger
    print("utils imported")
except ImportError as e:
    print(f"utils failed: {e}")

print("Importing TwinCATCommander...")
try:
    from communication.twincat_commander import TwinCATCommander
    print("TwinCATCommander imported")
except ImportError as e:
    print(f"TwinCATCommander failed: {e}")

print("All imports done")
