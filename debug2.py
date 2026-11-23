import sys
import os
print("Python path:", sys.executable)
print("Working dir:", os.getcwd())
sys.path.insert(0, r'C:\Users\iniha\OneDrive\Documents\AI\Otomatisasi AutoCAD')
print("Path inserted OK")

from app.main_window import MainWindow
print("MainWindow imported OK")
win = MainWindow()
print("MainWindow created OK")
win.show()
print("SUCCESS: MainWindow opened")