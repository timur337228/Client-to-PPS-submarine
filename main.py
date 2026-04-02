import sys
import time
import base64

import numpy as np
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QLabel, QPushButton, QTextEdit,
                               QTabWidget, QListWidget, QFrame, QSplitter, QComboBox)
from PySide6.QtCore import Qt, QTimer, QRegularExpression
from PySide6.QtGui import QFont, QImage, QPixmap
import pyqtgraph as pg
from network import UDPListener
from highlighter import ScriptHighlighter
from sonar import SonarPanel
from styles import STYLE_SHEET


class AuvControlStation(QMainWindow):
    def __init__(self):
        # Переменные
        self.auv_value = 0
        self.first_mbes_scan = True
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
        self.timer_auv_data.timeout.connect(self.get_auv_data)
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

        # 1. Создаем общую палитру
        pos = np.array([0.0, 0.5, 1.0])
        color = np.array([[0, 0, 0, 255], [180, 110, 50, 255], [255, 255, 200, 255]], dtype=np.ubyte)
        cmap = pg.ColorMap(pos, color)
        lut = cmap.getLookupTable()

        # 2. Контейнер для двух окон сонара
        sonar_container = QWidget()
        sonar_h_layout = QHBoxLayout(sonar_container)
        sonar_h_layout.setContentsMargins(0, 0, 0, 0)
        sonar_h_layout.setSpacing(4)

        # Левый сонар
        self.sonar_panel_l = SonarPanel("LEFT SONAR", accent_color="#459FED", flip=True)
        self.sonar_panel_r = SonarPanel("RIGHT SONAR", accent_color="#6BDBBF", flip=False)

        sonar_h_layout.addWidget(self.sonar_panel_l)
        sonar_h_layout.addWidget(self.sonar_panel_r)


        self.view_echo = pg.PlotWidget(title="MULTIBEAM ECHO SOUNDER")
        self.view_echo.setBackground("#000000")
        self.view_echo.showGrid(x=True, y=True, alpha=0.3)
        self.view_echo.getPlotItem().invertY(True)
        self.view_echo.setAspectLocked(True)

        self.view_echo.setRange(xRange=[-20, 20], yRange=[0, 30], padding=0.1)
        self.view_echo.getViewBox().setMouseEnabled(x=True, y=True)
        self.view_echo.enableAutoRange(axis='xy', enable=False)

        self.mbes_scatter = pg.ScatterPlotItem(
            size=4,
            pen=pg.mkPen(None),
            brush=pg.mkBrush(0, 255, 100, 200)
        )
        self.view_echo.addItem(self.mbes_scatter)

        # Добавляем виджеты В СПЛИТТЕР, а не в лайаут
        self.sensor_splitter.addWidget(self.view_camera)
        self.sensor_splitter.addWidget(sonar_container)
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

    def update_camera_visualizer(self, base64_data):
        try:
            image_bytes = base64.b64decode(base64_data)

            qimg = QImage.fromData(image_bytes)
            pixmap = QPixmap.fromImage(qimg)

            self.view_camera.setPixmap(pixmap.scaled(
                self.view_camera.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            ))
        except Exception as e:
            self.log_message(f"Camera decode error: {e}")

    def get_auv_data(self):
        try:
            self.udp_thread.send_command("get_telemetry", {"auv_id": self.auv_value})
            self.udp_thread.send_command("get_mbes", {"auv_id": self.auv_value})
            self.udp_thread.send_command("get_camera", {"auv_id": self.auv_value})
            self.udp_thread.send_command("get_side_sonar", {"auv_id": self.auv_value})
        except Exception as e:
            print(e)

    def trigger_emergency(self):
        self.udp_thread.send_command("reset_auv", {"auv_id": self.auv_value})

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
        if response.get("status") != 200:
            self.handle_udp_error(response.get("message", "Unknown Error"))
            return

        result = response.get("result")
        if not result:
            return
        request = response.get("request")
        # 1. Проверяем на наличие точек (MBES)
        if "points_x" in result:
            self.update_mbes_visualizer(result["points_x"], result["points_y"])
        elif "camera_image" in result:
            self.update_camera_visualizer(result["camera_image"])

        elif "depth" in result:
            self.update_telemetry(result)
        elif request == "get_side_sonar":

            result = response.get("result", {})
            self.last_sonar_max_range = result.get("max_range", 200.0)
            self.update_sonar_visualizer(result.get("left", []), result.get("right", []))
        elif request == "reset_auv":
            self.log_message("success restart")
        # 3. Логика статуса подключения
        if not self.is_connected:
            self.is_connected = True
            self.lbl_status.setText("🟢 UDP CONNECTED")
            self.lbl_status.setStyleSheet("color: #00FF00;")

        # 4. Обработка команд скрипта
        sent_values = response.get("values", {})
        if sent_values.get("_from_script"):
            if self.script_commands_pending > 0:
                self.script_commands_pending -= 1
                if self.script_commands_pending == 0:
                    self.log_message("✅ Mission Script Executed Successfully!")

    def update_mbes_visualizer(self, x_coords, y_coords):
        self.mbes_scatter.setData(x=x_coords, y=y_coords)
        if self.first_mbes_scan and len(x_coords) > 0:
            self.view_echo.autoRange()
            self.first_mbes_scan = False

    def update_sonar_visualizer(self, left_data: list, right_data: list):
        try:
            max_range = float(
                self.last_sonar_max_range if hasattr(self, "last_sonar_max_range") else 200.0
            )
            self.sonar_panel_l.set_data(left_data, max_range)
            self.sonar_panel_r.set_data(right_data, max_range)
        except Exception as e:
            self.log_message(f"Sonar update error: {e}")

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
