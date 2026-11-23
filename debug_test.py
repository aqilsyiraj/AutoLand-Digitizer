import sys
import traceback

sys.path.insert(0, r'C:\Users\iniha\OneDrive\Documents\AI\Otomatisasi AutoCAD')

try:
    from app.main_window import MainWindow
    win = MainWindow()
    win.show()
    print('SUCCESS: MainWindow opened')
except Exception as e:
    traceback.print_exc()