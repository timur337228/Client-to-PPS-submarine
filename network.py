import socket
import json
from queue import Queue, Empty
import time
from PySide6.QtCore import QThread, Signal, Slot


class UDPListener(QThread):
    command_response = Signal(dict)
    error_occurred = Signal(str)
    telemetry_received = Signal(dict)

    def __init__(self, ip="127.0.0.1", port=8080):
        super().__init__()
        self.ip = ip
        self.port = port
        self.is_running = True

        # Сокет для телеметрии (Порт 8081)
        self.telemetry_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.telemetry_sock.settimeout(0.01)  # Очень короткий таймаут для неблокирующего чтения
        self.telemetry_sock.bind(("0.0.0.0", 8081))

        # Сокет для команд (Порт 8080)
        self.command_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.command_sock.settimeout(1.0)  # Увеличиваем до 1 секунды!

        self.command_queue = Queue()

    def run(self):
        while self.is_running:
            # 1. Обрабатываем ТОЛЬКО ОДНУ команду за итерацию
            # Это позволяет телеметрии «протискиваться» между командами скрипта
            try:
                cmd_data = self.command_queue.get_nowait()
                self._send_command_internal(*cmd_data)
            except Empty:
                pass
            except Exception as e:
                self.error_occurred.emit(f"Queue error: {e}")

            # 2. Читаем телеметрию
            try:
                data, addr = self.telemetry_sock.recvfrom(65536)
                msg = json.loads(data.decode("utf-8"))
                self.telemetry_received.emit(msg)
            except socket.timeout:
                pass
            except Exception:
                pass

            time.sleep(0.001)  # Минимальная пауза для разгрузки CPU

    def _send_command_internal(self, cmd, val, request_id):
        try:
            payload = {"request": cmd, "values": dict(val), "request_id": request_id}
            self.command_sock.sendto(json.dumps(payload).encode('utf-8'), (self.ip, self.port))

            # Ждем подтверждения от Unity
            data, _ = self.command_sock.recvfrom(65536)
            response = json.loads(data.decode('utf-8'))

            # Проверяем соответствие ответа запросу
            if "request" not in response: response["request"] = cmd
            if "values" not in response: response["values"] = val

            self.command_response.emit(response)
        except socket.timeout:
            self.error_occurred.emit(f"Команда '{cmd}' не получила ответа (Timeout)")
        except Exception as e:
            self.error_occurred.emit(f"Ошибка команды: {e}")

    @Slot(str, dict)
    def send_command(self, cmd, val):
        request_id = int(time.time() * 1000)
        self.command_queue.put((cmd, val, request_id))

    def stop(self):
        self.is_running = False
        self.telemetry_sock.close()
        self.command_sock.close()