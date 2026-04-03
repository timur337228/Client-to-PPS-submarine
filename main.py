import sys
import time
import base64

import numpy as np
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QLabel, QPushButton, QTextEdit,
                               QTabWidget, QListWidget, QFrame, QSplitter, QComboBox)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QImage, QPixmap
import pyqtgraph as pg
from network import UDPListener
from highlighter import ScriptHighlighter
from sonar import SonarPanel
from styles import STYLE_SHEET


class AuvControlStation(QMainWindow):
    def __init__(self):
        # Переменные
        self.auv_value = None  # Исправлено: 0 блокировало все данные от сервера
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
        self.udp_thread.telemetry_received.connect(self.route_stream_data)
        self.udp_thread.start()

        # ✅ АВТОЗАПРОС СПИСКА ПРИ ЗАПУСКЕ
        self.refresh_auv_list()

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

        # ✅ ВЕРХНИЙ ЛЕВЫЙ УГОЛ: Интерфейс выбора AUV
        auv_selector_layout = QHBoxLayout()
        self.auv_combo = QComboBox()
        self.auv_combo.setFixedWidth(80)
        self.auv_combo.currentTextChanged.connect(self.on_auv_changed)

        self.btn_remove_auv = QPushButton("🗑 Удалить")
        self.btn_remove_auv.setFixedWidth(80)
        self.btn_remove_auv.setObjectName("btn_remove")
        self.btn_remove_auv.clicked.connect(self.remove_current_auv)

        auv_selector_layout.addWidget(QLabel("Target AUV:"))
        auv_selector_layout.addWidget(self.auv_combo)
        auv_selector_layout.addWidget(self.btn_remove_auv)

        header_layout.addLayout(auv_selector_layout)
        header_layout.addStretch()

        self.lbl_status = QLabel("🟢 UDP CONNECTED")
        self.lbl_status.setFont(self.sans_font)
        self.lbl_status.setStyleSheet("color: #00FF00;")

        self.lbl_timer = QLabel("MISSION TIME: 00:00:00")
        self.lbl_timer.setFont(self.mono_font)
        self.lbl_timer.setAlignment(Qt.AlignCenter)

        self.btn_emergency = QPushButton("EMERGENCY SURFACE")
        self.btn_emergency.setObjectName("btn_emergency")
        self.btn_emergency.clicked.connect(self.trigger_emergency)

        header_layout.addWidget(self.lbl_status)
        header_layout.addWidget(self.lbl_timer)
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
        self.lbl_speed = QLabel("SPEED: -- m/s")
        self.lbl_speed.setFont(self.mono_font)
        self.lbl_lati = QLabel("LATITUDE: -- m")
        self.lbl_lati.setFont(self.mono_font)
        self.lbl_long = QLabel("LONGITUDE: -- m")
        self.lbl_long.setFont(self.mono_font)

        left_layout.addWidget(self.lbl_depth)
        left_layout.addWidget(self.lbl_yaw)
        left_layout.addWidget(self.lbl_pitch)
        left_layout.addWidget(self.lbl_roll)
        left_layout.addWidget(self.lbl_speed)
        left_layout.addWidget(self.lbl_lati)
        left_layout.addWidget(self.lbl_long)
        left_layout.addStretch()
        splitter.addWidget(left_panel)

        # --- В. ЦЕНТРАЛЬНЫЙ БЛОК (The Stage) ---
        center_panel = QFrame()
        center_layout = QVBoxLayout(center_panel)
        self.tabs = QTabWidget()

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
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.sensor_splitter = QSplitter(Qt.Vertical)

        self.view_camera = QLabel("CAMERA (2x2m)")
        self.view_camera.setObjectName("sensor_view")
        self.view_camera.setAlignment(Qt.AlignCenter)

        # Палитра для сонара
        pos = np.array([0.0, 0.5, 1.0])
        color = np.array([[0, 0, 0, 255], [180, 110, 50, 255], [255, 255, 200, 255]], dtype=np.ubyte)
        cmap = pg.ColorMap(pos, color)

        sonar_container = QWidget()
        sonar_h_layout = QHBoxLayout(sonar_container)
        sonar_h_layout.setContentsMargins(0, 0, 0, 0)
        sonar_h_layout.setSpacing(4)

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
            size=4, pen=pg.mkPen(None), brush=pg.mkBrush(0, 255, 100, 200)
        )
        self.view_echo.addItem(self.mbes_scatter)

        self.sensor_splitter.addWidget(self.view_camera)
        self.sensor_splitter.addWidget(sonar_container)
        self.sensor_splitter.addWidget(self.view_echo)

        right_layout.addWidget(self.sensor_splitter)
        splitter.addWidget(right_panel)

        splitter.setSizes([200, 630, 170])

        # --- Д. НИЖНЯЯ ПАНЕЛЬ (Logger) ---
        self.logger = QListWidget()
        self.logger.setFont(self.mono_font)
        self.logger.setMaximumHeight(150)

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

    def update_camera_visualizer(self, base64_data):
        try:
            if not base64_data: return
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

    def trigger_emergency(self):
        if self.auv_value is None:
            self.log_message("⚠️ Выберите AUV перед отправкой команды")
            return
        self.udp_thread.send_command("reset_auv", {"auv_id": self.auv_value})

    def execute_script(self):
        try:
            script_text = self.text_script.toPlainText()
            lines = script_text.split('\n')
            auv_id = self.auv_value
            self.script_commands_pending = len([l for l in lines if l.strip() and not l.strip().startswith("#")])

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
                                values[key] = float(val) if "." in val else int(val)
                            except ValueError:
                                values[key] = val
                values["_from_script"] = True
                self.udp_thread.send_command(command, {**values})
        except Exception as e:
            self.log_message(f"Script Error: {e}")

    def update_telemetry(self, data):
        try:
            if self.auv_value is None or data.get("auv_id") != self.auv_value:
                return
            self.lbl_depth.setText(f"DEPTH: {data.get('depth', 0):.2f} m")
            self.lbl_yaw.setText(f"HEADING: {data.get('yaw', 0):.1f}°")
            self.lbl_pitch.setText(f"PITCH: {data.get('pitch', 0):.1f}°")
            self.lbl_roll.setText(f"ROLL: {data.get('roll', 0):.1f}°")
            self.lbl_speed.setText(f"SPEED: {data.get('speed', 0):.1f} m/s")
            self.lbl_lati.setText(f"LATITUDE: {data.get('latitude', 0):.6f}°")
            self.lbl_long.setText(f"LONGITUDE: {data.get('longitude', 0):.6f}°")
        except Exception as e:
            return

    def handle_udp_error(self, error_msg):
        self.is_connected = False
        self.log_message(f"⚠️ UDP Error: {error_msg}")
        self.lbl_status.setText("🔴 UDP ERROR")
        self.lbl_status.setStyleSheet("color: red;")

    def handle_response(self, response):
        if response.get("status") != 200:
            self.handle_udp_error(response.get("message", "Unknown Error"))
            return

        cmd = response.get("request")
        result = response.get("result")

        if cmd == "get_auvs" and isinstance(result, list):
            self.update_auv_list_ui(result)

        if not result:
            return

        # Маршрутизация визуализации
        if "points_x" in result:
            self.update_mbes_visualizer(result["points_x"], result["points_y"])
        elif "camera_image" in result:
            self.update_camera_visualizer(result["camera_image"])
        elif cmd == "get_side_sonar":
            self.last_sonar_max_range = result.get("max_range", 200.0)
            self.update_sonar_visualizer(result.get("left", []), result.get("right", []))
        elif cmd == "reset_auv":
            self.log_message("✅ Emergency Surface / Reset Sent")

        # Статус подключения
        if not self.is_connected:
            self.is_connected = True
            self.lbl_status.setText("🟢 UDP CONNECTED")
            self.lbl_status.setStyleSheet("color: #00FF00;")

        # Обработка скриптов
        sent_values = response.get("values", {})
        if sent_values.get("_from_script") and self.script_commands_pending > 0:
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
            max_range = float(getattr(self, "last_sonar_max_range", 200.0))
            self.sonar_panel_l.set_data(left_data, max_range)
            self.sonar_panel_r.set_data(right_data, max_range)
        except Exception as e:
            self.log_message(f"Sonar update error: {e}")

    def route_stream_data(self, data):
        msg_type = data.get("type")

        if msg_type == "auv_list":
            self.update_auv_list_ui(data.get("ids", []))
            return

        if self.auv_value is None or data.get("auv_id") != self.auv_value:
            return
        self.is_connected = True
        self.lbl_status.setText("🟢 UDP CONNECTED")
        self.lbl_status.setStyleSheet("color: #00FF00;")
        if msg_type == "telemetry":
            self.update_telemetry(data)
        elif msg_type == "mbes":
            self.update_mbes_visualizer(data.get("points_x", []), data.get("points_y", []))
        elif msg_type == "camera":
            self.update_camera_visualizer(data.get("camera_image", ""))
        elif msg_type == "sonar":
            self.last_sonar_max_range = data.get("max_range", 200.0)
            self.update_sonar_visualizer(data.get("left", []), data.get("right", []))

    def on_auv_changed(self, text):
        if text:
            try:
                self.auv_value = int(text)
                self.log_message(f"🎯 Target AUV changed to ID: {self.auv_value}")
            except ValueError:
                self.auv_value = None

    def refresh_auv_list(self):
        """Запрос списка активных AUV с сервера"""
        self.udp_thread.send_command("get_auvs", {})

    def remove_current_auv(self):
        if not self.auv_combo.currentText():
            return
        try:
            auv_id = int(self.auv_combo.currentText())
            self.udp_thread.send_command("remove_auv", {"auv_id": auv_id})
            QTimer.singleShot(500, self.refresh_auv_list)
        except ValueError:
            pass

    def update_auv_list_ui(self, ids):
        new_ids = sorted([str(i) for i in ids])
        current_text = self.auv_combo.currentText()
        existing_items = [self.auv_combo.itemText(i) for i in range(self.auv_combo.count())]

        if new_ids != existing_items:
            self.auv_combo.blockSignals(True)
            self.auv_combo.clear()
            self.auv_combo.addItems(new_ids)

            index = self.auv_combo.findText(current_text)
            if index >= 0:
                self.auv_combo.setCurrentIndex(index)
            elif self.auv_combo.count() > 0:
                self.auv_combo.setCurrentIndex(0)
                self.auv_value = int(self.auv_combo.currentText())
            else:
                self.auv_value = None

            self.auv_combo.blockSignals(False)

    def closeEvent(self, event):
        if hasattr(self, 'timer'):
            self.timer.stop()
        self.udp_thread.stop()
        self.udp_thread.wait(1000)
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AuvControlStation()
    window.show()
    sys.exit(app.exec())