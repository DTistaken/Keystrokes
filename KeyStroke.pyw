import sys
import time
import threading
import configparser
import psutil
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel
)
from pynput import keyboard, mouse

# Load settings from config file
config = configparser.ConfigParser()
config.read('settings.config')
cpu_stats_enabled = config.getboolean('STATS', 'CPUStats', fallback=True)
gpu_stats_enabled = config.getboolean('STATS', 'GPUStats', fallback=True)
memory_stats_enabled = config.getboolean('STATS', 'MemoryStats', fallback=True)

class KeystrokesOverlay(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Keystrokes Overlay")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(260, 310)

        self.keys = {"W": False, "A": False, "S": False, "D": False, "SPACE": False}
        self.left_clicks = []
        self.right_clicks = []
        self.drag_position = None
        self.buttons = {}

        self.initUI()
        self.start_listeners()

    def initUI(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(2)
        main_layout.setContentsMargins(3, 3, 3, 3)

        # W key
        w_row = QHBoxLayout()
        w_row.addStretch()
        self.buttons["W"] = self.create_button("W", 50)
        w_row.addWidget(self.buttons["W"])
        w_row.addStretch()
        main_layout.addLayout(w_row)

        # A S D keys
        asd_row = QHBoxLayout()
        asd_row.setSpacing(2)
        self.buttons["A"] = self.create_button("A", 50)
        self.buttons["S"] = self.create_button("S", 50)
        self.buttons["D"] = self.create_button("D", 50)
        asd_row.addWidget(self.buttons["A"])
        asd_row.addWidget(self.buttons["S"])
        asd_row.addWidget(self.buttons["D"])
        main_layout.addLayout(asd_row)

        # LMB / RMB
        mouse_row = QHBoxLayout()
        mouse_row.setSpacing(2)
        self.lmb_label = self.create_label("LMB\n0 CPS", 50)
        self.rmb_label = self.create_label("RMB\n0 CPS", 50)
        mouse_row.addWidget(self.lmb_label)
        mouse_row.addWidget(self.rmb_label)
        main_layout.addLayout(mouse_row)

        # Spacebar
        space_row = QHBoxLayout()
        space_row.addStretch()
        self.buttons["SPACE"] = self.create_button("SPACE", 40, width=200)
        space_row.addWidget(self.buttons["SPACE"])
        space_row.addStretch()
        main_layout.addLayout(space_row)

        # Stats
        if cpu_stats_enabled or gpu_stats_enabled or memory_stats_enabled:
            self.cpu_label = self.create_label("CPU:\n0%", 28)
            self.gpu_label = self.create_label("GPU:\n0%", 28)
            self.ram_label = self.create_label("RAM:\n0%", 28)

            stats_layout = QHBoxLayout()
            stats_layout.setSpacing(2)
            stats_layout.addWidget(self.cpu_label)
            stats_layout.addWidget(self.gpu_label)
            stats_layout.addWidget(self.ram_label)
            main_layout.addLayout(stats_layout)

            threading.Thread(target=self.system_stats_updater, daemon=True).start()

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_ui)
        self.timer.start(50)

    def create_button(self, text, height, width=60):
        btn = QPushButton(text)
        btn.setFixedSize(width, height)
        btn.setStyleSheet(self.button_style(False))
        self.buttons[text] = btn
        return btn

    def create_label(self, text, height):
        label = QLabel(text)
        label.setFixedSize(60, height)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("""
            background-color: rgba(100, 100, 100, 150);
            color: white;
            font-size: 10px;
            border-radius: 6px;
            border: 1px solid gray;
        """)
        return label

    def button_style(self, pressed):
        bg = "rgba(100, 100, 100, 150)" if not pressed else "rgba(60, 60, 60, 200)"
        return f"""
            QPushButton {{
                background-color: {bg};
                color: white;
                font-size: 14px;
                border-radius: 6px;
                border: 2px solid gray;
            }}
        """

    def update_ui(self):
        for key, btn in self.buttons.items():
            btn.setStyleSheet(self.button_style(self.keys[key]))

    def start_listeners(self):
        threading.Thread(target=self.keyboard_listener, daemon=True).start()
        threading.Thread(target=self.mouse_listener, daemon=True).start()
        threading.Thread(target=self.cps_updater, daemon=True).start()

    def keyboard_listener(self):
        def on_press(key):
            try:
                k = key.char.upper()
                if k in self.keys:
                    self.keys[k] = True
            except AttributeError:
                if key == keyboard.Key.space:
                    self.keys["SPACE"] = True

        def on_release(key):
            try:
                k = key.char.upper()
                if k in self.keys:
                    self.keys[k] = False
            except AttributeError:
                if key == keyboard.Key.space:
                    self.keys["SPACE"] = False

        with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
            listener.join()

    def mouse_listener(self):
        def on_click(x, y, button, pressed):
            if pressed:
                if button == mouse.Button.left:
                    self.left_clicks.append(time.time())
                elif button == mouse.Button.right:
                    self.right_clicks.append(time.time())

        with mouse.Listener(on_click=on_click) as listener:
            listener.join()

    def cps_updater(self):
        while True:
            now = time.time()
            self.left_clicks = [t for t in self.left_clicks if now - t <= 1]
            self.right_clicks = [t for t in self.right_clicks if now - t <= 1]
            self.lmb_label.setText(f"LMB\n{len(self.left_clicks)} CPS")
            self.rmb_label.setText(f"RMB\n{len(self.right_clicks)} CPS")
            time.sleep(0.1)

    def system_stats_updater(self):
        while True:
            try:
                if cpu_stats_enabled and hasattr(self, 'cpu_label'):
                    cpu = psutil.cpu_percent()
                    self.cpu_label.setText(f"CPU:\n{cpu:.1f}%")
                if memory_stats_enabled and hasattr(self, 'ram_label'):
                    mem = psutil.virtual_memory().percent
                    self.ram_label.setText(f"RAM:\n{mem:.1f}%")
                if gpu_stats_enabled and hasattr(self, 'gpu_label'):
                    try:
                        import GPUtil
                        gpu = GPUtil.getGPUs()[0]
                        self.gpu_label.setText(f"GPU:\n{gpu.load * 100:.1f}%")
                    except:
                        self.gpu_label.setText("GPU:\nN/A")
            except Exception as e:
                print(f"Error updating stats: {e}")
            time.sleep(1)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self.drag_position:
            self.move(event.globalPos() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        self.drag_position = None
        event.accept()

    def run(self):
        self.show()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    overlay = KeystrokesOverlay()
    overlay.run()
    sys.exit(app.exec_())
