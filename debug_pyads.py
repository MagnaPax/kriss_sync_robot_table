
print("--- Debug Start ---")
try:
    import pyads
    print(f"pyads imported successfully: {pyads}")
except ImportError as e:
    print(f"pyads Import failed: {e}")
except Exception as e:
    print(f"An unexpected error occurred during pyads import: {e}")

try:
    from communication.twincat_connector import TwinCATConnector
    print("TwinCATConnector imported successfully")
    connector = TwinCATConnector()
    print(f"TwinCATConnector instance created. Demo Mode: {connector._is_demo}")
    print("Attempting to connect...")
    # connector.connect() # This might fail with NameError if pyads is missing but Connector loaded
except NameError as e:
    print(f"Caught NameError: {e}")
except Exception as e:
    print(f"Caught Exception: {e}")
print("--- Debug End ---")
