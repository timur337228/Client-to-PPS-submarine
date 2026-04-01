STYLE_SHEET = """
QMainWindow { background-color: #121212; }
QLabel { color: #E0E0E0; font-weight: bold; }
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
}
QTabBar::tab:selected {
    background: #00F0FF;
    color: #121212;
}
QTextEdit, QListWidget {
    background-color: #1A1A1A;
    color: #E0E0E0;
    border: 1px solid rgba(0, 240, 255, 30);
    border-radius: 8px;
}
QPushButton#btn_execute {
    background-color: rgba(0, 240, 255, 40);
    color: #00F0FF;
    border: 1px solid #00F0FF;
    border-radius: 8px;
    padding: 15px;
}
QPushButton#btn_execute:hover { background-color: #00F0FF; color: #121212; }
QPushButton#btn_emergency {
    color: #FF3333;
    border: 2px solid #FF3333;
    border-radius: 8px;
    padding: 8px 15px;
}
QPushButton#btn_emergency:hover { background-color: #FF3333; color: white; }
QSplitter::handle {
    background-color: rgba(0, 240, 255, 0.1);
    margin: 2px;
}

QSplitter::handle:hover {
    background-color: rgba(0, 240, 255, 0.5); 
}

QSplitter[orientation="1"]::handle {
    height: 2px;
}

"""