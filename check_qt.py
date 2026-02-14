import sys
try:
    from PyQt6.QtWidgets import QApplication, QLabel
    print("PyQt6 imported successfully")
    app = QApplication(sys.argv)
    label = QLabel("Hello World")
    print("QApplication and QLabel created successfully")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
