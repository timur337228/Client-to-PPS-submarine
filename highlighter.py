from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont
from PySide6.QtCore import QRegularExpression


class ScriptHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.highlighting_rules = []
        command_format = QTextCharFormat()
        command_format.setForeground(QColor("#00F0FF"))
        command_format.setFontWeight(QFont.Bold)
        commands = [
            "set_motor_speed",
            "get_auvs",
            "get_motor_ids",
            "get_telemetry",
            "reset_auv",
            "spawn_auv",
            "get_side_sonar",
            "get_camera",
            "get_mbes",
            "remove_auv",
        ]
        for cmd in commands:
            pattern = QRegularExpression(rf"\b{cmd}\b")
            self.highlighting_rules.append((pattern, command_format))

        number_format = QTextCharFormat()
        number_format.setForeground(QColor("#FFA500"))
        self.highlighting_rules.append((QRegularExpression(r"\b\d+\.?\d*\b"), number_format))

    def highlightBlock(self, text):
        for pattern, format in self.highlighting_rules:
            match_iterator = pattern.globalMatch(text)
            while match_iterator.hasNext():
                match = match_iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), format)
