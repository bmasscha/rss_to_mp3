import os
import sys
import ctypes

print("--- Diagnosis Start ---")
print(f"Python Executable: {sys.executable}")
print(f"CWD: {os.getcwd()}")
print(f"Python Version: {sys.version}")

# Check Env Vars
print("\nEnvironment Variables:")
env_vars = ['PATH', 'QT_PLUGIN_PATH', 'QT_QPA_PLATFORM_PLUGIN_PATH', 'QML2_IMPORT_PATH', 'CONDA_PREFIX']
for key in env_vars:
    print(f"{key}: {os.environ.get(key, 'Not Set')}")

# Helpers to find the package
import importlib.util
try:
    spec = importlib.util.find_spec("PyQt6")
    if spec and spec.submodule_search_locations:
        pyqt_path = spec.submodule_search_locations[0]
        print(f"\nPyQt6 Location: {pyqt_path}")
        
        qt_bin_path = os.path.join(pyqt_path, 'Qt6', 'bin')
        print(f"Expected Qt6 Bin Path: {qt_bin_path}")
        
        dll_name = 'Qt6Core.dll'
        dll_path = os.path.join(qt_bin_path, dll_name)
        
        if os.path.exists(dll_path):
            print(f"DLL found at: {dll_path}")
            
            # Try loading via ctypes
            print("Attempting to load Qt6Core.dll via ctypes...")
            try:
                # We need to add the dir to DLL search path for dependencies
                os.add_dll_directory(qt_bin_path)
                lib = ctypes.cdll.LoadLibrary(dll_path)
                print("SUCCESS: Qt6Core.dll loaded via ctypes.")
            except Exception as e:
                print(f"FAILURE: ctypes load failed: {e}")
        else:
            print(f"DLL NOT found at: {dll_path}")
            
    else:
        print("\nPyQt6 package not found via importlib.")
except Exception as e:
    print(f"\nError finding spec: {e}")

print("\nAttempting Imports:")
try:
    from PyQt6 import QtCore
    print("SUCCESS: import PyQt6.QtCore")
except ImportError as e:
    print(f"FAILURE: import PyQt6.QtCore: {e}")

try:
    from PyQt6 import QtWidgets
    print("SUCCESS: import PyQt6.QtWidgets")
except ImportError as e:
    print(f"FAILURE: import PyQt6.QtWidgets: {e}")

print("--- Diagnosis End ---")
