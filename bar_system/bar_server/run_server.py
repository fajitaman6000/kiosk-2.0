# bar_server/run_server.py
import sys
from PyQt5.QtWidgets import QApplication
from app_main_window import BarManagerWindow
import signal

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = QApplication(sys.argv)
    window = BarManagerWindow()
    window.show()
    sys.exit(app.exec_())