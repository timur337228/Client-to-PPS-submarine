import sys
import json
import socket
import time
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QLabel, QPushButton, QTextEdit,
                               QTabWidget, QListWidget, QFrame, QSplitter)
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QRegularExpression
from PySide6.QtGui import QFont, QColor, QSyntaxHighlighter, QTextCharFormat, QPalette


# --- 1. СЕТЕВОЙ ПОТОК (UDP CLIENT) ---
class UdpListenerThread(QThread):
    # Сигнал для передачи полученного JSON в главный поток GUI
    telemetry_received = Signal(dict)

    def __init__(self, ip="127.0.0.1", port=8080):
        super().__init__()
        self.ip = ip
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.is_running = True

    def run(self):
        # Отправляем пинг для инициализации (чтобы Unity знал наш адрес)
        self.sock.sendto(b'{"auv_id": 1, "command": "ping", "value": 0}', (self.ip, self.port))

        while self.is_running:
            try:
                self.sock.settimeout(1.0)
                data, _ = self.sock.recvfrom(4096)
                msg = json.loads(data.decode('utf-8'))
                self.telemetry_received.emit(msg)
            except socket.timeout:
                continue
            except Exception as e:
                print(f"UDP Error: {e}")

    def send_command(self, auv_id, cmd, val):
        payload = {"auv_id": auv_id, "command": cmd, "value": float(val)}
        self.sock.sendto(json.dumps(payload).encode('utf-8'), (self.ip, self.port))

    def stop(self):
        self.is_running = False
        self.sock.close()


# --- 2. ПОДСВЕТКА СИНТАКСИСА (MISSION SCRIPT) ---
class ScriptHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.highlighting_rules = []

        # Формат для команд
        command_format = QTextCharFormat()
        command_format.setForeground(QColor("#00F0FF"))
        command_format.setFontWeight(QFont.Bold)

        commands = ["move_forward", "move_backward", "rotate", "set_depth", "stop"]
        for cmd in commands:
            pattern = QRegularExpression(rf"\b{cmd}\b")
            self.highlighting_rules.append((pattern, command_format))

        # Формат для цифр
        number_format = QTextCharFormat()
        number_format.setForeground(QColor("#FFA500"))  # Оранжевый
        self.highlighting_rules.append((QRegularExpression(r"\b\d+\.?\d*\b"), number_format))

    def highlightBlock(self, text):
        for pattern, format in self.highlighting_rules:
            match_iterator = pattern.globalMatch(text)
            while match_iterator.hasNext():
                match = match_iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), format)


# --- 3. ГЛАВНОЕ ОКНО ИНТЕРФЕЙСА ---
class AuvControlStation(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("3D-симулятор АНПА - Control Station")
        self.resize(1280, 800)

        # Настройка шрифтов
        self.mono_font = QFont("Consolas", 11)  # Замените на JetBrains Mono, если установлен
        self.sans_font = QFont("Segoe UI", 10)

        self.init_ui()
        self.apply_stylesheet()

        # Запуск UDP
        self.udp_thread = UdpListenerThread()
        self.udp_thread.telemetry_received.connect(self.update_telemetry)
        self.udp_thread.start()

        # Таймер миссии
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
        self.lbl_status = QLabel("🟢 UDP CONNECTED")
        self.lbl_status.setFont(self.sans_font)

        self.lbl_timer = QLabel("MISSION TIME: 00:00:00")
        self.lbl_timer.setFont(self.mono_font)
        self.lbl_timer.setAlignment(Qt.AlignCenter)

        self.btn_emergency = QPushButton("EMERGENCY SURFACE")
        self.btn_emergency.setObjectName("btn_emergency")
        self.btn_emergency.clicked.connect(self.trigger_emergency)

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
        self.lbl_vel = QLabel("VELOCITY: -- m/s")
        self.lbl_vel.setFont(self.mono_font)

        left_layout.addWidget(self.lbl_depth)
        left_layout.addWidget(self.lbl_yaw)
        left_layout.addWidget(self.lbl_pitch)
        left_layout.addWidget(self.lbl_roll)
        left_layout.addWidget(self.lbl_vel)
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
        self.text_script.setPlainText("1 move_forward 10\n1 set_depth 5.5")
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
        right_layout.addWidget(QLabel("SENSOR FEEDS"))

        self.view_camera = QLabel("CAMERA (2x2m)")
        self.view_camera.setObjectName("sensor_view")
        self.view_camera.setAlignment(Qt.AlignCenter)

        self.view_sonar = QLabel("SIDESCAN SONAR")
        self.view_sonar.setObjectName("sensor_view")
        self.view_sonar.setAlignment(Qt.AlignCenter)

        self.view_echo = QLabel("ECHO SOUNDER (1024 pts)")
        self.view_echo.setObjectName("sensor_view")
        self.view_echo.setAlignment(Qt.AlignCenter)

        right_layout.addWidget(self.view_camera)
        right_layout.addWidget(self.view_sonar)
        right_layout.addWidget(self.view_echo)
        splitter.addWidget(right_panel)

        # Настраиваем пропорции колонок (левая 1, центр 3, правая 1)
        splitter.setSizes([200, 600, 200])

        # --- Д. НИЖНЯЯ ПАНЕЛЬ (Logger) ---
        self.logger = QListWidget()
        self.logger.setFont(self.mono_font)
        self.logger.setMaximumHeight(150)
        self.log_message("System Initialized. Awaiting UDP connection...")

        # Сборка главного Layout
        main_layout.addLayout(header_layout)
        main_layout.addWidget(splitter)
        main_layout.addWidget(self.logger)

    def apply_stylesheet(self):
        # Design System QSS (Glassmorphism, угольный фон, морская волна)
        qss = """
        QMainWindow {
            background-color: #121212;
        }
        QLabel {
            color: #E0E0E0;
            font-weight: bold;
        }
        QFrame#glass_panel {
            background-color: rgba(30, 30, 35, 180);
            border: 1px solid rgba(0, 240, 255, 50);
            border-radius: 8px;
        }
        QLabel#sensor_view {
            background-color: #0A0A0A;
            border: 1px solid #00F0FF;
            border-radius: 8px;
            color: #00F0FF;
            min-height: 100px;
        }
        QLabel#view_3d {
            background-color: #050505;
            color: #555555;
            font-size: 24px;
        }
        QTabWidget::pane {
            border: 1px solid rgba(0, 240, 255, 50);
            border-radius: 8px;
            background: #181818;
        }
        QTabBar::tab {
            background: #202020;
            color: #E0E0E0;
            padding: 8px 20px;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
            margin-right: 2px;
        }
        QTabBar::tab:selected {
            background: #00F0FF;
            color: #121212;
            font-weight: bold;
        }
        QTextEdit, QListWidget {
            background-color: #1A1A1A;
            color: #E0E0E0;
            border: 1px solid rgba(0, 240, 255, 30);
            border-radius: 8px;
            padding: 5px;
        }
        QPushButton#btn_execute {
            background-color: rgba(0, 240, 255, 40);
            color: #00F0FF;
            border: 1px solid #00F0FF;
            border-radius: 8px;
            padding: 15px;
            font-size: 14px;
            font-weight: bold;
        }
        QPushButton#btn_execute:hover {
            background-color: #00F0FF;
            color: #121212;
        }
        QPushButton#btn_emergency {
            background-color: transparent;
            color: #FF3333;
            border: 2px solid #FF3333;
            border-radius: 8px;
            padding: 8px 15px;
            font-weight: bold;
        }
        QPushButton#btn_emergency:hover {
            background-color: #FF3333;
            color: white;
        }
        """
        self.setStyleSheet(qss)

    def log_message(self, text):
        timestamp = time.strftime("%H:%M:%S")
        self.logger.addItem(f"[{timestamp}] {text}")
        self.logger.scrollToBottom()

    def update_timers(self):
        elapsed = int(time.time() - self.start_time)
        mins, secs = divmod(elapsed, 60)
        hours, mins = divmod(mins, 60)
        self.lbl_timer.setText(f"MISSION TIME: {hours:02d}:{mins:02d}:{secs:02d}")

    def trigger_emergency(self):
        self.log_message("⚠️ EMERGENCY SURFACE INITIATED!")
        # Отправляем команду всплытия на все аппараты
        for i in range(1, 4):
            self.udp_thread.send_command(i, "set_depth", 0.0)

    def execute_script(self):
        script_text = self.text_script.toPlainText()
        lines = script_text.split('\n')
        self.log_message(f"Executing mission script ({len(lines)} lines)...")

        # Простой парсер команд (ID COMMAND VALUE)
        for line in lines:
            parts = line.strip().split()
            if len(parts) == 3:
                try:
                    auv_id, cmd, val = int(parts[0]), parts[1], float(parts[2])
                    self.udp_thread.send_command(auv_id, cmd, val)
                    self.log_message(f"Sent: AUV {auv_id} -> {cmd} ({val})")
                except ValueError:
                    self.log_message(f"Syntax Error in line: {line}")

        self.tabs.setCurrentIndex(0)  # Переключаемся на 3D вид после запуска

    def update_telemetry(self, data):
        # Обновляем UI на основе данных из потока (по ТЗ)
        if data.get("auv_id") == 1:  # Пока выводим данные для первого аппарата
            self.lbl_depth.setText(f"DEPTH: {data.get('depth', 0):.2f} m")
            self.lbl_yaw.setText(f"HEADING: {data.get('yaw', 0):.1f}°")
            self.lbl_pitch.setText(f"PITCH: {data.get('pitch', 0):.1f}°")
            self.lbl_roll.setText(f"ROLL: {data.get('roll', 0):.1f}°")
            self.lbl_vel.setText(f"VELOCITY: {data.get('velocity', 0):.2f} m/s")

    def closeEvent(self, event):
        self.udp_thread.stop()
        self.udp_thread.wait()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AuvControlStation()
    window.show()
    sys.exit(app.exec())