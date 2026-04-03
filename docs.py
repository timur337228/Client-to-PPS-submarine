from PySide6.QtWidgets import QVBoxLayout, QPushButton, QTextEdit, QDialog
from PySide6.QtGui import QFont

class CommandsDocDialog(QDialog):
    """Мини-окно с документацией по командам"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📖 Command Documentation")
        self.resize(520, 360)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Поле с HTML-разметкой для красивого отображения
        self.doc_view = QTextEdit()
        self.doc_view.setReadOnly(True)
        self.doc_view.setFont(QFont("Consolas", 10))
        self.setStyleSheet("""
            QDialog {
                background-color: #0D0D0D;
                border: none;
            }
            QTextEdit {
                background-color: #1E1E1E; 
                color: #D4D4D4; 
                border: 1px solid #444;
                border-radius: 4px;
            }
            QPushButton {
                background-color: #2D2D2D;
                color: #D4D4D4;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #3D3D3D;
            }
            QPushButton:pressed {
                background-color: #1E1E1E;
            }
        """)

        html_content = """
        <h3 style="color: #569CD6; margin-bottom: 10px;">📜 Доступные команды</h3>
        <table style="width: 100%; border-collapse: collapse; font-size: 12px;">
            <tr style="background-color: #2D2D2D;">
                <th style="padding: 6px; border: 1px solid #444; text-align: left; color: #9CDCFE;">Команда</th>
                <th style="padding: 6px; border: 1px solid #444; text-align: left;">Описание</th>
                <th style="padding: 6px; border: 1px solid #444; text-align: left;">Параметры</th>
            </tr>
            <tr>
                <td style="padding: 6px; border: 1px solid #444; font-family: monospace; color: #DCDCAA;">set_motor_speed</td>
                <td style="padding: 6px; border: 1px solid #444;">Устанавливает силу тяги для конкретного мотора.</td>
                <td style="padding: 6px; border: 1px solid #444; font-family: monospace; color: #CE9178;">auv_id=(int|null)  motor_id=(int)<br>force=(float, 0±100%)</td>
            </tr>
            <tr>
                <td style="padding: 6px; border: 1px solid #444; font-family: monospace; color: #DCDCAA;">reset_auv</td>
                <td style="padding: 6px; border: 1px solid #444;">Экстренное всплытие и сброс состояния АНПА.</td>
                <td style="padding: 6px; border: 1px solid #444; font-family: monospace; color: #CE9178;">auv_id=(int|null)</td>
            </tr>
            <tr>
                <td style="padding: 6px; border: 1px solid #444; font-family: monospace; color: #DCDCAA;">spawn_auv</td>
                <td style="padding: 6px; border: 1px solid #444;">Создать и инициализировать новый АНПА.</td>
                <td style="padding: 6px; border: 1px solid #444; font-family: monospace; color: #CE9178;">auv_id=(int|null)</td>
            </tr>
            <tr>
                <td style="padding: 6px; border: 1px solid #444; font-family: monospace; color: #DCDCAA;">remove_auv</td>
                <td style="padding: 6px; border: 1px solid #444;">Удалить АНПА из симуляции/сервера.</td>
                <td style="padding: 6px; border: 1px solid #444; font-family: monospace; color: #CE9178;">auv_id=(int|null)</td>
            </tr>
        </table>
        <p style="margin-top: 12px; color: #888; font-size: 11px;">💡 Синтаксис в скрипте: <code style="background:#333; padding:2px 4px; border-radius:3px;">команда(параметр=значение)</code></p>
        """
        self.doc_view.setHtml(html_content)
        layout.addWidget(self.doc_view)

        # Кнопка закрытия
        btn_close = QPushButton("Закрыть")
        btn_close.setObjectName("btn_close_doc")
        btn_close.setFixedHeight(30)
        btn_close.clicked.connect(self.close)
        layout.addWidget(btn_close)
