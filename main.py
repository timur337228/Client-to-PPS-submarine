import sys
import time
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QLabel, QPushButton, QTextEdit,
                               QTabWidget, QListWidget, QFrame, QSplitter, QComboBox)
from PySide6.QtCore import Qt, QTimer, QRegularExpression
from PySide6.QtGui import QFont

from network import UDPListener
from highlighter import ScriptHighlighter
from styles import STYLE_SHEET


class AuvControlStation(QMainWindow):
    def __init__(self):
        # Переменные
        self.auv_value = 0
        self.is_connected = False
        self.script_commands_pending = 0

        super().__init__()
        self.setWindowTitle("AUV Control Station")
        self.resize(1280, 800)

        self.mono_font = QFont("Consolas", 11)
        self.sans_font = QFont("Segoe UI", 10)

        self.init_ui()
        self.setStyleSheet(STYLE_SHEET)

        self.udp_thread = UDPListener()
        self.udp_thread.command_response.connect(self.handle_response)
        self.udp_thread.error_occurred.connect(self.handle_udp_error)
        self.udp_thread.start()

        # Настройка таймеров
        self.timer_auv_data = QTimer(self)
        self.timer_auv_data.timeout.connect(self.get_auv_telemetry)
        self.timer_auv_data.start(400)
        # self.get_auv_telemetry()

        self.start_time = time.time()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_timers)
        self.timer.start(1000)

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # --- А. ВЕРХНЯЯ ПАНЕЛЬ (Header) ---
        header_layout = QHBoxLayout()
        self.auv = QComboBox()
        self.auv.addItems(["1", "2", "3"])
        self.auv.currentTextChanged.connect(self.select_auv)

        self.lbl_status = QLabel("🟢 UDP CONNECTED")
        self.lbl_status.setFont(self.sans_font)

        self.lbl_timer = QLabel("MISSION TIME: 00:00:00")
        self.lbl_timer.setFont(self.mono_font)
        self.lbl_timer.setAlignment(Qt.AlignCenter)

        self.btn_emergency = QPushButton("EMERGENCY SURFACE")
        self.btn_emergency.setObjectName("btn_emergency")
        self.btn_emergency.clicked.connect(self.trigger_emergency)

        header_layout.addWidget(self.auv)
        header_layout.addStretch()
        header_layout.addWidget(self.lbl_status)
        header_layout.addStretch()
        header_layout.addWidget(self.lbl_timer)
        header_layout.addStretch()
        header_layout.addWidget(self.btn_emergency)

        # --- СРЕДНЯЯ ЗОНА (Разделитель на 3 колонки) ---
        splitter = QSplitter(Qt.Horizontal)

        # --- Б. ЛЕВЫЙ БЛОК (Primary Telemetry) ---
        left_panel = QFrame()
        left_panel.setObjectName("glass_panel")
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(QLabel("PRIMARY TELEMETRY"))

        self.lbl_depth = QLabel("DEPTH: -- m")
        self.lbl_depth.setFont(self.mono_font)
        self.lbl_yaw = QLabel("HEADING (YAW): --°")
        self.lbl_yaw.setFont(self.mono_font)
        self.lbl_pitch = QLabel("PITCH: --°")
        self.lbl_pitch.setFont(self.mono_font)
        self.lbl_roll = QLabel("ROLL: --°")
        self.lbl_roll.setFont(self.mono_font)
        self.lbl_speed = QLabel("SPEED: --°")
        self.lbl_speed.setFont(self.mono_font)
        self.lbl_x = QLabel("X: -- m")
        self.lbl_x.setFont(self.mono_font)
        self.lbl_y = QLabel("Y: -- m")
        self.lbl_y.setFont(self.mono_font)

        left_layout.addWidget(self.lbl_depth)
        left_layout.addWidget(self.lbl_yaw)
        left_layout.addWidget(self.lbl_pitch)
        left_layout.addWidget(self.lbl_roll)
        left_layout.addStretch()
        splitter.addWidget(left_panel)

        # --- В. ЦЕНТРАЛЬНЫЙ БЛОК (The Stage) ---
        center_panel = QFrame()
        center_layout = QVBoxLayout(center_panel)
        self.tabs = QTabWidget()

        # Вкладка Скриптов
        tab_script_widget = QWidget()
        script_layout = QVBoxLayout(tab_script_widget)
        self.text_script = QTextEdit()
        self.text_script.setFont(self.mono_font)
        self.text_script.setPlainText("set_motor_speed(motor_id=1, force=50) # force указывается в процентах")
        self.highlighter = ScriptHighlighter(self.text_script.document())

        self.btn_execute = QPushButton("EXECUTE MISSION")
        self.btn_execute.setObjectName("btn_execute")
        self.btn_execute.clicked.connect(self.execute_script)

        script_layout.addWidget(self.text_script)
        script_layout.addWidget(self.btn_execute)

        self.tabs.addTab(tab_script_widget, "MISSION SCRIPT")
        center_layout.addWidget(self.tabs)
        splitter.addWidget(center_panel)

        # --- Г. ПРАВЫЙ БЛОК (Sensors) ---
        right_panel = QFrame()
        right_panel.setObjectName("glass_panel")
        right_layout = QVBoxLayout(right_panel)  # Оставляем лайаут как контейнер для сплиттера
        right_layout.setContentsMargins(0, 0, 0, 0)  # Убираем отступы, чтобы сплиттер был в край

        # Создаем ВЕРТИКАЛЬНЫЙ сплиттер
        self.sensor_splitter = QSplitter(Qt.Vertical)

        self.view_camera = QLabel("CAMERA (2x2m)")
        self.view_camera.setObjectName("sensor_view")
        self.view_camera.setAlignment(Qt.AlignCenter)

        self.view_sonar = QLabel("SIDESCAN SONAR")
        self.view_sonar.setObjectName("sensor_view")
        self.view_sonar.setAlignment(Qt.AlignCenter)

        self.view_echo = QLabel("ECHO SOUNDER (1024 pts)")
        self.view_echo.setObjectName("sensor_view")
        self.view_echo.setAlignment(Qt.AlignCenter)

        # Добавляем виджеты В СПЛИТТЕР, а не в лайаут
        self.sensor_splitter.addWidget(self.view_camera)
        self.sensor_splitter.addWidget(self.view_sonar)
        self.sensor_splitter.addWidget(self.view_echo)


        # Добавляем сам сплиттер в лайаут панели
        right_layout.addWidget(self.sensor_splitter)
        splitter.addWidget(right_panel)

        # Настраиваем пропорции колонок (левая 1, центр 3, правая 1)
        splitter.setSizes([200, 630, 170])

        # --- Д. НИЖНЯЯ ПАНЕЛЬ (Logger) ---
        self.logger = QListWidget()
        self.logger.setFont(self.mono_font)
        self.logger.setMaximumHeight(150)
        self.log_message("System Initialized. Awaiting UDP connection...")

        # Сборка главного Layout
        main_layout.addLayout(header_layout)
        main_layout.addWidget(splitter)
        main_layout.addWidget(self.logger)

    def log_message(self, text):
        timestamp = time.strftime("%H:%M:%S")
        self.logger.addItem(f"[{timestamp}] {text}")
        self.logger.scrollToBottom()

    def update_timers(self):
        elapsed = int(time.time() - self.start_time)
        mins, secs = divmod(elapsed, 60)
        hours, mins = divmod(mins, 60)
        self.lbl_timer.setText(f"MISSION TIME: {hours:02d}:{mins:02d}:{secs:02d}")

    def select_auv(self, value):
        self.auv_value = int(value) - 1



    def get_auv_telemetry(self):
        try:
            self.udp_thread.send_command("get_telemetry", {"auv_id": self.auv_value})
        except Exception as e:
            print(e)

    def trigger_emergency(self):
        self.log_message("⚠️ EMERGENCY SURFACE INITIATED!")
        # Отправляем команду всплытия на все аппараты
        for i in range(1, 4):
            self.udp_thread.send_command("set_depth", {"auv_id": self.auv_value, "cor": 0.0})

    def execute_script(self):
        try:
            script_text = self.text_script.toPlainText()
            lines = script_text.split('\n')
            auv_id = self.auv_value
            self.script_commands_pending = len(lines)
            for line in lines:
                clean_line = line.split("#")[0].strip()
                if not clean_line:
                    continue
                parts = clean_line.split("(")
                command = parts[0].strip()
                values = {"auv_id": auv_id}
                if len(parts) > 1:
                    args_val = parts[1].replace(")", "").replace(" ", "").split(",")
                    if args_val and args_val != [""]:
                        for value in args_val:
                            key, val = value.split("=")
                            try:
                                if "." in val:
                                    values[key] = float(val)
                                else:
                                    values[key] = int(val)
                            except ValueError:
                                values[key] = val
                values["_from_script"] = True
                self.udp_thread.send_command(command, {**values})
            self.tabs.setCurrentIndex(0)
        except Exception as e:
            self.log_message("SyntaxError")

    def update_telemetry(self, data):
        try:
            self.lbl_depth.setText(f"DEPTH: {data.get('depth', 0):.2f} m")
            self.lbl_yaw.setText(f"HEADING: {data.get('yaw', 0):.1f}°")
            self.lbl_pitch.setText(f"PITCH: {data.get('pitch', 0):.1f}°")
            self.lbl_roll.setText(f"ROLL: {data.get('roll', 0):.1f}°")
            self.lbl_speed.setText(f"SPEED: {data.get('speed', 0):.1f}m/s")
            self.lbl_x.setText(f"X: {data.get('x', 0):.1f}")
            self.lbl_y.setText(f"Y: {data.get('y', 0):.1f}")
        except Exception as e:
            return

    def handle_udp_error(self, error_msg):
        if self.is_connected:
            self.is_connected = False
            self.log_message(f"⚠️ UDP Error: {error_msg}")
            self.lbl_status.setText("🔴 UDP ERROR")
            self.lbl_status.setStyleSheet("color: red;")


    def handle_response(self, response):
        sent_values = response.get("values", {})
        if sent_values.get("_from_script") or response.get("request") in ["set_motor_speed", "set_depth"]:
            if self.script_commands_pending > 0:
                self.script_commands_pending -= 1
        if self.script_commands_pending > 0:
            self.script_commands_pending -= 1
            if self.script_commands_pending == 0:
                self.log_message("✅ Mission Script Executed Successfully!")
        if not self.is_connected:
            self.is_connected = True
            self.lbl_status.setText("🟢 UDP CONNECTED")
        if response[("status")] != 200:
            self.handle_udp_error(response["message"])
            return
        if "result" in response:
            if "status" not in response["result"] :
                self.update_telemetry(response["result"])
                return
        self.log_message("Success command!")


    def closeEvent(self, event):
        self.timer_auv_data.stop()
        self.timer.stop()
        self.udp_thread.stop()
        self.udp_thread.wait(1000)
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AuvControlStation()
    window.show()
    sys.exit(app.exec())
