# ============================================================
# ВСТАВИТЬ ПЕРЕД классом AuvControlStation
# ============================================================
import numpy as np
from PySide6.QtWidgets import QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QColor, QLinearGradient


class SonarPanel(QFrame):
    """
    Статичная панель бокового сонара — аналог DrawSideSonarPanel из C#.

    Структура (сверху вниз):
      TITLE
      [Shadow strip — визуализация интенсивностей по лучам]
      "Shadow line"
      State / Hits / Best slant / Best cross-track / Best intensity
      [Echo level bar]
      "Echo level"
      0 m
      [Range marker — вертикальный]
      XX.0 m
    """

    def __init__(self, title: str, accent_color: str, flip: bool = False, parent=None):
        super().__init__(parent)
        self.setObjectName("glass_panel")
        self._title = title
        self._accent = QColor(accent_color)
        self._flip = flip          # True для левого — отражаем strip
        self._max_range = 200.0

        # Текущие данные
        self._intensities: np.ndarray = np.zeros(512, dtype=np.float32)
        self._hit_count = 0
        self._best_intensity = 0.0
        self._best_index = 0       # индекс луча с max интенсивностью
        self._n = 512

        self.setMinimumWidth(110)
        self._build_ui()

    # ----------------------------------------------------------
    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(4)

        # Заголовок
        self._lbl_title = QLabel(self._title)
        self._lbl_title.setAlignment(Qt.AlignCenter)
        self._lbl_title.setStyleSheet(
            f"color: {self._accent.name()}; font-weight: bold; font-size: 11px;"
        )
        lay.addWidget(self._lbl_title)

        # Shadow strip
        self._strip = _ShadowStrip(self._accent, self._flip)
        self._strip.setFixedHeight(60)
        lay.addWidget(self._strip)

        lbl_shadow = QLabel("Shadow line")
        lbl_shadow.setAlignment(Qt.AlignCenter)
        lbl_shadow.setStyleSheet("color: #6A7F8E; font-size: 9px;")
        lay.addWidget(lbl_shadow)

        # Stats
        self._lbl_stats = QLabel(self._make_stats_text())
        self._lbl_stats.setStyleSheet(
            "color: #D0E8F5; font-size: 10px; font-family: Consolas;"
        )
        self._lbl_stats.setWordWrap(True)
        lay.addWidget(self._lbl_stats)

        # Echo level bar
        self._echo_bar = _HBar(self._accent)
        self._echo_bar.setFixedHeight(12)
        lay.addWidget(self._echo_bar)

        lbl_echo = QLabel("Echo level")
        lbl_echo.setAlignment(Qt.AlignCenter)
        lbl_echo.setStyleSheet("color: #6A7F8E; font-size: 9px;")
        lay.addWidget(lbl_echo)

        # Range marker
        self._lbl_range_top = QLabel("0 m")
        self._lbl_range_top.setAlignment(Qt.AlignCenter)
        self._lbl_range_top.setStyleSheet("color: #6A7F8E; font-size: 9px;")
        lay.addWidget(self._lbl_range_top)

        self._range_bar = _VBar(self._accent)
        self._range_bar.setMinimumHeight(60)
        lay.addWidget(self._range_bar)

        self._lbl_range_bot = QLabel("— m")
        self._lbl_range_bot.setAlignment(Qt.AlignCenter)
        self._lbl_range_bot.setStyleSheet("color: #6A7F8E; font-size: 9px;")
        lay.addWidget(self._lbl_range_bot)

        lay.addStretch()

    # ----------------------------------------------------------
    def _make_stats_text(self) -> str:
        state = "ACTIVE" if self._hit_count > 0 else "MISS"
        # cross-track: позиция лучшего луча → дистанция
        cross = (self._best_index / max(self._n - 1, 1)) * self._max_range
        return (
            f"State: {state}\n"
            f"Hits: {self._hit_count}/{self._n}\n"
            f"Best slant: {cross:.1f} m\n"
            f"Best cross-track: {cross:.1f} m\n"
            f"Best intensity: {self._best_intensity:.2f}"
        )

    # ----------------------------------------------------------
    def set_data(self, intensities: list, max_range: float):
        """
        intensities — список float [0..1] длиной N (512)
        max_range   — максимальная дальность (м)
        """
        arr = np.array(intensities, dtype=np.float32)
        self._n = max(len(arr), 1)
        self._max_range = max_range if max_range > 0 else 200.0
        self._intensities = arr

        # Считаем stats из массива
        nonzero = arr > 1e-6
        self._hit_count = int(np.count_nonzero(nonzero))
        if self._hit_count > 0:
            self._best_index = int(np.argmax(arr))
            self._best_intensity = float(arr[self._best_index])
        else:
            self._best_index = 0
            self._best_intensity = 0.0

        # Обновляем дочерние виджеты
        self._strip.set_data(arr)
        self._lbl_stats.setText(self._make_stats_text())
        self._echo_bar.set_value(self._best_intensity)

        ratio = self._best_index / max(self._n - 1, 1)
        self._range_bar.set_ratio(ratio if self._hit_count > 0 else -1.0)
        self._lbl_range_bot.setText(f"{self._max_range:.0f} m")


# ----------------------------------------------------------
class _ShadowStrip(QWidget):
    """
    Визуализация массива интенсивностей в виде горизонтальной полосы.
    Каждый луч — вертикальный столбик, яркость = интенсивность.
    Аналог stripTexture из C#.
    """
    def __init__(self, accent: QColor, flip: bool = False, parent=None):
        super().__init__(parent)
        self._accent = accent
        self._flip = flip
        self._data: np.ndarray = np.zeros(512, dtype=np.float32)

    def set_data(self, arr: np.ndarray):
        self._data = arr
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, False)
        w, h = self.width(), self.height()

        # Фон
        p.fillRect(0, 0, w, h, QColor("#0D1419"))

        n = len(self._data)
        if n == 0:
            return

        data = self._data[::-1] if self._flip else self._data

        bar_w = max(1.0, w / n)
        r, g, b = self._accent.red(), self._accent.green(), self._accent.blue()

        for i, val in enumerate(data):
            val = float(np.clip(val, 0.0, 1.0))
            x = int(i * bar_w)
            bw = max(1, int(bar_w) + 1)
            # Цвет: от тёмного фона до accent, пропорционально интенсивности
            cr = int(13 + (r - 13) * val)
            cg = int(20 + (g - 20) * val)
            cb = int(25 + (b - 25) * val)
            p.fillRect(x, 0, bw, h, QColor(cr, cg, cb))


# ----------------------------------------------------------
class _HBar(QWidget):
    """Горизонтальный Echo level bar."""
    def __init__(self, accent: QColor, parent=None):
        super().__init__(parent)
        self._accent = accent
        self._value = 0.0

    def set_value(self, v: float):
        self._value = max(0.0, min(1.0, v))
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor("#1E2A33"))
        if self._value > 0:
            p.fillRect(0, 0, int(w * self._value), h, self._accent)


# ----------------------------------------------------------
class _VBar(QWidget):
    """Вертикальный Range marker — аналог rangeTrackRect + markerRect из C#."""
    def __init__(self, accent: QColor, parent=None):
        super().__init__(parent)
        self._accent = accent
        self._ratio = -1.0   # -1 = нет данных, маркер не рисуем

    def set_ratio(self, r: float):
        self._ratio = r
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        w, h = self.width(), self.height()
        tw = 14
        tx = (w - tw) // 2
        # Track
        p.fillRect(tx, 2, tw, h - 4, QColor("#1C2830"))
        # Marker
        if self._ratio >= 0:
            my = int(2 + (h - 8) * self._ratio)
            p.fillRect(tx - 6, my, tw + 12, 4, self._accent)