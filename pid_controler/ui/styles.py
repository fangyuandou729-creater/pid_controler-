"""
全局样式表
提供现代化的深色主题界面风格
"""

MAIN_STYLESHEET = """
/* ========== 全局样式 ========== */
QMainWindow {
    background-color: #1e1e2e;
}

QWidget {
    font-family: "Microsoft YaHei UI", "Segoe UI", "Noto Sans SC", sans-serif;
    font-size: 13px;
    color: #cdd6f4;
}

/* ========== 分组框 ========== */
QGroupBox {
    background-color: #181825;
    border: 1px solid #313244;
    border-radius: 8px;
    margin-top: 12px;
    padding: 16px 10px 10px 10px;
    font-weight: bold;
    font-size: 13px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    padding: 0 8px;
    color: #89b4fa;
    background-color: #181825;
}

/* ========== 按钮 ========== */
QPushButton {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 6px 16px;
    font-weight: bold;
    min-height: 28px;
}

QPushButton:hover {
    background-color: #45475a;
    border-color: #585b70;
}

QPushButton:pressed {
    background-color: #585b70;
}

QPushButton:disabled {
    background-color: #1e1e2e;
    color: #585b70;
    border-color: #313244;
}

QPushButton#startBtn {
    background-color: #a6e3a1;
    color: #1e1e2e;
    border-color: #a6e3a1;
}

QPushButton#startBtn:hover {
    background-color: #94e2d5;
}

QPushButton#stopBtn {
    background-color: #f38ba8;
    color: #1e1e2e;
    border-color: #f38ba8;
}

QPushButton#stopBtn:hover {
    background-color: #eba0ac;
}

QPushButton#dangerBtn {
    background-color: #f38ba8;
    color: #1e1e2e;
}

/* ========== 输入框 ========== */
QLineEdit, QSpinBox, QDoubleSpinBox {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 5px;
    padding: 4px 8px;
    min-height: 24px;
}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: #89b4fa;
}

QSpinBox::up-button, QDoubleSpinBox::up-button {
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 20px;
    border-left: 1px solid #45475a;
    border-top-right-radius: 5px;
    background-color: #45475a;
}

QSpinBox::down-button, QDoubleSpinBox::down-button {
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 20px;
    border-left: 1px solid #45475a;
    border-bottom-right-radius: 5px;
    background-color: #45475a;
}

QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
    width: 8px;
    height: 8px;
}

QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
    width: 8px;
    height: 8px;
}

/* ========== 下拉框 ========== */
QComboBox {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 5px;
    padding: 4px 8px;
    min-height: 24px;
}

QComboBox:hover {
    border-color: #585b70;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox QAbstractItemView {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    selection-background-color: #45475a;
}

/* ========== 滑块 ========== */
QSlider::groove:horizontal {
    height: 6px;
    background-color: #313244;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    width: 16px;
    height: 16px;
    margin: -5px 0;
    background-color: #89b4fa;
    border-radius: 8px;
}

QSlider::handle:horizontal:hover {
    background-color: #b4befe;
}

QSlider::sub-page:horizontal {
    background-color: #89b4fa;
    border-radius: 3px;
}

/* ========== 旋钮 (用QDial模拟) ========== */
QDial {
    background-color: #313244;
    color: #89b4fa;
}

/* ========== 标签页 ========== */
QTabWidget::pane {
    background-color: #181825;
    border: 1px solid #313244;
    border-radius: 6px;
}

QTabBar::tab {
    background-color: #1e1e2e;
    color: #a6adc8;
    border: 1px solid #313244;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 8px 18px;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background-color: #181825;
    color: #89b4fa;
    border-bottom: 2px solid #89b4fa;
}

QTabBar::tab:hover:!selected {
    background-color: #313244;
}

/* ========== 文本编辑 (日志) ========== */
QTextEdit {
    background-color: #11111b;
    color: #a6adc8;
    border: 1px solid #313244;
    border-radius: 6px;
    padding: 6px;
    font-family: "Cascadia Code", "Consolas", "Courier New", monospace;
    font-size: 12px;
    selection-background-color: #45475a;
}

/* ========== 表格 ========== */
QTableWidget {
    background-color: #181825;
    color: #cdd6f4;
    border: 1px solid #313244;
    border-radius: 6px;
    gridline-color: #313244;
}

QTableWidget::item {
    padding: 4px;
}

QTableWidget::item:selected {
    background-color: #45475a;
}

QHeaderView::section {
    background-color: #1e1e2e;
    color: #89b4fa;
    border: 1px solid #313244;
    padding: 6px;
    font-weight: bold;
}

/* ========== 进度条 ========== */
QProgressBar {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 4px;
    text-align: center;
    color: #cdd6f4;
    min-height: 18px;
}

QProgressBar::chunk {
    background-color: #89b4fa;
    border-radius: 3px;
}

/* ========== 状态栏 ========== */
QStatusBar {
    background-color: #11111b;
    color: #a6adc8;
    border-top: 1px solid #313244;
    font-size: 12px;
}

QStatusBar::item {
    border: none;
}

/* ========== 工具栏 ========== */
QToolBar {
    background-color: #181825;
    border-bottom: 1px solid #313244;
    spacing: 4px;
    padding: 4px;
}

QToolButton {
    background-color: transparent;
    color: #cdd6f4;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 4px 8px;
}

QToolButton:hover {
    background-color: #313244;
    border-color: #45475a;
}

/* ========== 菜单 ========== */
QMenuBar {
    background-color: #181825;
    color: #cdd6f4;
    border-bottom: 1px solid #313244;
}

QMenuBar::item:selected {
    background-color: #313244;
}

QMenu {
    background-color: #1e1e2e;
    color: #cdd6f4;
    border: 1px solid #313244;
}

QMenu::item:selected {
    background-color: #45475a;
}

/* ========== 分割线 ========== */
QSplitter::handle {
    background-color: #313244;
}

QSplitter::handle:horizontal {
    width: 3px;
}

QSplitter::handle:vertical {
    height: 3px;
}

/* ========== 复选框 ========== */
QCheckBox {
    color: #cdd6f4;
    spacing: 6px;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #45475a;
    border-radius: 3px;
    background-color: #313244;
}

QCheckBox::indicator:checked {
    background-color: #89b4fa;
    border-color: #89b4fa;
}

/* ========== 工具提示 ========== */
QToolTip {
    background-color: #1e1e2e;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 4px 8px;
}

/* ========== 滚动条 ========== */
QScrollBar:vertical {
    background-color: #1e1e2e;
    width: 10px;
    border-radius: 5px;
}

QScrollBar::handle:vertical {
    background-color: #45475a;
    border-radius: 5px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background-color: #585b70;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    background-color: #1e1e2e;
    height: 10px;
    border-radius: 5px;
}

QScrollBar::handle:horizontal {
    background-color: #45475a;
    border-radius: 5px;
    min-width: 30px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #585b70;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* ========== 仪表盘相关 ========== */
QLabel#title {
    font-size: 16px;
    font-weight: bold;
    color: #89b4fa;
}

QLabel#value {
    font-family: "Cascadia Code", "Consolas", monospace;
    font-size: 18px;
    font-weight: bold;
    color: #a6e3a1;
}

QLabel#unit {
    color: #a6adc8;
    font-size: 11px;
}

QLabel#warning {
    color: #fab387;
    font-weight: bold;
}

QLabel#error {
    color: #f38ba8;
    font-weight: bold;
}
"""

# Catppuccin Mocha 色彩方案常量
class Colors:
    """颜色常量"""
    BASE = "#1e1e2e"
    MANTLE = "#181825"
    CRUST = "#11111b"
    SURFACE0 = "#313244"
    SURFACE1 = "#45475a"
    SURFACE2 = "#585b70"
    OVERLAY0 = "#6c7086"
    OVERLAY1 = "#7f849c"
    SUBTEXT0 = "#a6adc8"
    SUBTEXT1 = "#bac2de"
    TEXT = "#cdd6f4"
    LAVENDER = "#b4befe"
    BLUE = "#89b4fa"
    SAPPHIRE = "#74c7ec"
    SKY = "#89dceb"
    TEAL = "#94e2d5"
    GREEN = "#a6e3a1"
    YELLOW = "#f9e2af"
    PEACH = "#fab387"
    MAROON = "#eba0ac"
    RED = "#f38ba8"
    MAUVE = "#cba6f7"
    PINK = "#f5c2e7"
    FLAMINGO = "#f2cdcd"
    ROSEWATER = "#f5e0dc"

    # 波形颜色
    WAVEFORM_COLORS = [
        '#89b4fa',  # 蓝色 - 设定值
        '#a6e3a1',  # 绿色 - 测量值
        '#f38ba8',  # 红色 - PID输出
        '#f9e2af',  # 黄色 - 误差
        '#cba6f7',  # 紫色 - P项
        '#94e2d5',  # 青色 - I项
        '#fab387',  # 橙色 - D项
    ]