# bar_client/run_client.py
import sys
from PyQt5.QtWidgets import QApplication
from app_client_window import AppClientWindow
import signal

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = QApplication(sys.argv)
    window = AppClientWindow()
    window.show()
    sys.exit(app.exec_())