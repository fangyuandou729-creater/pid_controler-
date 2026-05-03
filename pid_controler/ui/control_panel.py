"""
控制面板组件
包含PID参数调节旋钮/滑块、控制模式切换、目标值设定等
支持滚动视图防止拥挤，PID参数需确认后才生效
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QLabel, QSlider, QDoubleSpinBox, QComboBox, QPushButton,
    QCheckBox, QFrame, QSizePolicy, QDial, QScrollArea,
    QMessageBox
)
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QFont, QColor

from .styles import Colors


class KnobWidget(QWidget):
    """旋钮控件，带标签和数值显示"""
    valueChanged = Signal(float)

    def __init__(self, label: str, min_val: float = 0.0, max_val: float = 100.0,
                 default: float = 0.0, step: float = 0.1, decimals: int = 2,
                 unit: str = "", parent=None):
        super().__init__(parent)
        self._min = min_val
        self._max = max_val
        self._step = step
        self._decimals = decimals
        self._scale = 10 ** decimals

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        # 标签
        self._label = QLabel(label)
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setStyleSheet(f"color: {Colors.BLUE}; font-weight: bold; font-size: 12px;")
        layout.addWidget(self._label)

        # 旋钮
        self._dial = QDial()
        self._dial.setMinimum(int(min_val * self._scale))
        self._dial.setMaximum(int(max_val * self._scale))
        self._dial.setValue(int(default * self._scale))
        self._dial.setFixedSize(70, 70)
        self._dial.setNotchesVisible(True)
        self._dial.setStyleSheet(f"""
            QDial {{
                background-color: {Colors.SURFACE0};
                color: {Colors.BLUE};
            }}
        """)
        layout.addWidget(self._dial, alignment=Qt.AlignCenter)

        # 数值输入
        self._spin = QDoubleSpinBox()
        self._spin.setRange(min_val, max_val)
        self._spin.setValue(default)
        self._spin.setSingleStep(step)
        self._spin.setDecimals(decimals)
        self._spin.setAlignment(Qt.AlignCenter)
        self._spin.setFixedWidth(90)
        layout.addWidget(self._spin, alignment=Qt.AlignCenter)

        # 单位
        if unit:
            self._unit_label = QLabel(unit)
            self._unit_label.setAlignment(Qt.AlignCenter)
            self._unit_label.setStyleSheet(f"color: {Colors.SUBTEXT0}; font-size: 10px;")
            layout.addWidget(self._unit_label)

        # 连接信号
        self._dial.valueChanged.connect(self._on_dial_changed)
        self._spin.valueChanged.connect(self._on_spin_changed)

    def _on_dial_changed(self, int_val):
        val = int_val / self._scale
        self._spin.blockSignals(True)
        self._spin.setValue(val)
        self._spin.blockSignals(False)
        self.valueChanged.emit(val)

    def _on_spin_changed(self, val):
        self._dial.blockSignals(True)
        self._dial.setValue(int(val * self._scale))
        self._dial.blockSignals(False)
        self.valueChanged.emit(val)

    def value(self) -> float:
        return self._spin.value()

    def setValue(self, val: float):
        self._spin.setValue(val)

    def setRange(self, min_val: float, max_val: float):
        self._min = min_val
        self._max = max_val
        self._spin.setRange(min_val, max_val)
        self._dial.blockSignals(True)
        self._dial.setMinimum(int(min_val * self._scale))
        self._dial.setMaximum(int(max_val * self._scale))
        self._dial.blockSignals(False)


class PIDParamRow(QWidget):
    """单行PID参数调节器（滑块+数值），需要确认按钮才生效"""

    def __init__(self, param_name: str, label: str, min_val: float,
                 max_val: float, default: float, step: float = 0.01,
                 decimals: int = 3, parent=None):
        super().__init__(parent)
        self._param_name = param_name
        self._committed_value = default  # 已确认的值
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(6)

        # 名称标签
        self._name_label = QLabel(label)
        self._name_label.setFixedWidth(28)
        self._name_label.setStyleSheet(f"""
            font-weight: bold; font-size: 15px; color: {Colors.MAUVE};
            font-family: 'Cascadia Code', 'Consolas', monospace;
        """)
        layout.addWidget(self._name_label)

        # 滑块
        self._slider = QSlider(Qt.Horizontal)
        self._slider.setMinimum(0)
        self._slider.setMaximum(1000)
        self._slider.setValue(int((default - min_val) / (max_val - min_val) * 1000))
        self._slider.setFixedHeight(24)
        layout.addWidget(self._slider, 1)

        # 数值输入
        self._spin = QDoubleSpinBox()
        self._spin.setRange(min_val, max_val)
        self._spin.setValue(default)
        self._spin.setSingleStep(step)
        self._spin.setDecimals(decimals)
        self._spin.setFixedWidth(90)
        layout.addWidget(self._spin)

        # 连接信号（滑块和输入框同步，但不发射外部信号）
        self._slider.valueChanged.connect(self._on_slider_changed)
        self._spin.valueChanged.connect(self._on_spin_changed)

    def _on_slider_changed(self, slider_val):
        val = self._spin.minimum() + (self._spin.maximum() - self._spin.minimum()) * slider_val / 1000.0
        val = round(val, self._spin.decimals())
        self._spin.blockSignals(True)
        self._spin.setValue(val)
        self._spin.blockSignals(False)

    def _on_spin_changed(self, val):
        slider_val = int((val - self._spin.minimum()) / (self._spin.maximum() - self._spin.minimum()) * 1000)
        slider_val = max(0, min(1000, slider_val))
        self._slider.blockSignals(True)
        self._slider.setValue(slider_val)
        self._slider.blockSignals(False)

    def value(self) -> float:
        """获取当前显示的值（不一定是已确认的值）"""
        return self._spin.value()

    def committed_value(self) -> float:
        """获取已确认的值"""
        return self._committed_value

    def commit(self):
        """确认当前值"""
        self._committed_value = self._spin.value()

    def setValue(self, val: float):
        self._spin.setValue(val)
        self._committed_value = val

    def setRange(self, min_val: float, max_val: float):
        self._spin.setRange(min_val, max_val)

    def has_changes(self) -> bool:
        """检查是否有未确认的变更"""
        return abs(self._spin.value() - self._committed_value) > 1e-6


class ControlPanel(QWidget):
    """
    控制面板（带滚动区域）
    包含：模式切换、目标值设定、PID参数调节、启停控制
    """
    # 信号
    mode_changed = Signal(str)
    target_changed = Signal(float)
    pid_param_changed = Signal(str, float, str)  # (param_name, value, loop_name)
    start_clicked = Signal()
    stop_clicked = Signal()
    reset_clicked = Signal()
    auto_tune_clicked = Signal(str)
    motor_params_changed = Signal(str, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        # 外层布局
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background-color: {Colors.BASE};
            }}
        """)

        # 滚动内容
        content = QWidget()
        main_layout = QVBoxLayout(content)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # ===== 标题 =====
        title = QLabel("🎛 控制面板")
        title.setStyleSheet(f"""
            font-size: 16px; font-weight: bold; color: {Colors.BLUE};
            padding: 6px 0;
        """)
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)

        # ===== 串口连接区 =====
        conn_group = QGroupBox("串口连接")
        conn_layout = QGridLayout(conn_group)
        conn_layout.setSpacing(6)

        conn_layout.addWidget(QLabel("端口:"), 0, 0)
        self._port_combo = QComboBox()
        self._port_combo.setMinimumWidth(120)
        self._port_combo.setEditable(True)
        conn_layout.addWidget(self._port_combo, 0, 1)

        self._refresh_btn = QPushButton("🔄 刷新")
        self._refresh_btn.setFixedHeight(30)
        self._refresh_btn.setToolTip("刷新端口列表")
        conn_layout.addWidget(self._refresh_btn, 0, 2)

        conn_layout.addWidget(QLabel("波特率:"), 1, 0)
        self._baud_combo = QComboBox()
        self._baud_combo.addItems(["9600", "19200", "38400", "57600", "115200", "230400", "460800", "921600"])
        self._baud_combo.setCurrentText("115200")
        conn_layout.addWidget(self._baud_combo, 1, 1)

        self._connect_btn = QPushButton("连接")
        self._connect_btn.setObjectName("startBtn")
        self._connect_btn.setFixedHeight(30)
        conn_layout.addWidget(self._connect_btn, 1, 2)

        self._conn_status = QLabel("● 未连接")
        self._conn_status.setStyleSheet(f"color: {Colors.RED};")
        conn_layout.addWidget(self._conn_status, 2, 0, 1, 3)

        main_layout.addWidget(conn_group)

        # ===== 控制模式区 =====
        mode_group = QGroupBox("控制模式")
        mode_layout = QVBoxLayout(mode_group)

        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["速度环 (Speed)", "位置环 (Position)", "角度环 (Angle)", "串级控制 (Cascade)"])
        self._mode_combo.currentTextChanged.connect(self._on_mode_changed)
        mode_layout.addWidget(self._mode_combo)

        self._auto_pid_check = QCheckBox("自动PID调参模式")
        self._auto_pid_check.setStyleSheet(f"color: {Colors.YELLOW};")
        mode_layout.addWidget(self._auto_pid_check)

        tune_row = QHBoxLayout()
        tune_row.addWidget(QLabel("方法:"))
        self._tune_method_combo = QComboBox()
        self._tune_method_combo.addItems(["Ziegler-Nichols", "Cohen-Coon", "阶跃响应法", "继电反馈法", "PSO优化"])
        self._tune_method_combo.setEnabled(False)
        tune_row.addWidget(self._tune_method_combo)
        self._auto_pid_check.toggled.connect(self._tune_method_combo.setEnabled)
        mode_layout.addLayout(tune_row)

        self._auto_tune_btn = QPushButton("🚀 开始自动调参")
        self._auto_tune_btn.setEnabled(False)
        self._auto_pid_check.toggled.connect(self._auto_tune_btn.setEnabled)
        self._auto_tune_btn.clicked.connect(lambda: self.auto_tune_clicked.emit(
            self._tune_method_combo.currentText()
        ))
        mode_layout.addWidget(self._auto_tune_btn)

        main_layout.addWidget(mode_group)

        # ===== 目标值设定区 =====
        target_group = QGroupBox("目标值设定")
        target_layout = QVBoxLayout(target_group)

        self._target_spin = QDoubleSpinBox()
        self._target_spin.setRange(-10000, 10000)
        self._target_spin.setValue(100)
        self._target_spin.setSingleStep(10)
        self._target_spin.setDecimals(1)
        self._target_spin.setSuffix(" rpm")
        target_layout.addWidget(self._target_spin)

        self._target_slider = QSlider(Qt.Horizontal)
        self._target_slider.setRange(-10000, 10000)
        self._target_slider.setValue(100)
        target_layout.addWidget(self._target_slider)

        # 快捷目标值按钮
        quick_row = QHBoxLayout()
        for val, text in [(-100, "-100"), (0, "0"), (100, "100"), (200, "200"), (300, "300")]:
            btn = QPushButton(text)
            btn.setFixedHeight(26)
            btn.clicked.connect(lambda checked, v=val: self._set_target(v))
            quick_row.addWidget(btn)
        target_layout.addLayout(quick_row)

        self._target_spin.valueChanged.connect(self._on_target_spin_changed)
        self._target_slider.valueChanged.connect(self._on_target_slider_changed)

        main_layout.addWidget(target_group)

        # ===== PID参数调节区 =====
        pid_group = QGroupBox("PID参数调节")
        pid_layout = QVBoxLayout(pid_group)

        # 环路选择
        loop_row = QHBoxLayout()
        loop_row.addWidget(QLabel("环路:"))
        self._loop_tabs = QComboBox()
        self._loop_tabs.addItems(["单环/当前环", "外环 (串级)", "内环 (串级)"])
        loop_row.addWidget(self._loop_tabs)
        pid_layout.addLayout(loop_row)

        # PID参数行
        self._kp_row = PIDParamRow("kp", "Kp", 0.0, 100.0, 1.0, 0.01, 3)
        self._ki_row = PIDParamRow("ki", "Ki", 0.0, 50.0, 0.1, 0.001, 4)
        self._kd_row = PIDParamRow("kd", "Kd", 0.0, 20.0, 0.01, 0.001, 4)

        pid_layout.addWidget(self._kp_row)
        pid_layout.addWidget(self._ki_row)
        pid_layout.addWidget(self._kd_row)

        # PID附加参数
        extra_row = QHBoxLayout()
        self._integral_max_spin = QDoubleSpinBox()
        self._integral_max_spin.setRange(0, 500)
        self._integral_max_spin.setValue(50)
        self._integral_max_spin.setPrefix("积分限幅: ")
        extra_row.addWidget(self._integral_max_spin)

        self._deadband_spin = QDoubleSpinBox()
        self._deadband_spin.setRange(0, 100)
        self._deadband_spin.setValue(0)
        self._deadband_spin.setPrefix("死区: ")
        self._deadband_spin.setDecimals(2)
        extra_row.addWidget(self._deadband_spin)
        pid_layout.addLayout(extra_row)

        # ⭐ 确认按钮
        self._pid_confirm_btn = QPushButton("✅ 确认修改PID参数")
        self._pid_confirm_btn.setFixedHeight(36)
        self._pid_confirm_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.BLUE};
                color: {Colors.CRUST};
                font-weight: bold;
                font-size: 13px;
                border: none;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: {Colors.SAPPHIRE};
            }}
            QPushButton:pressed {{
                background-color: {Colors.LAVENDER};
            }}
        """)
        self._pid_confirm_btn.clicked.connect(self._on_pid_confirm)
        pid_layout.addWidget(self._pid_confirm_btn)

        # 重置按钮
        reset_row = QHBoxLayout()
        self._pid_reset_btn = QPushButton("↩ 恢复默认")
        self._pid_reset_btn.setFixedHeight(28)
        self._pid_reset_btn.clicked.connect(self._on_pid_reset)
        reset_row.addWidget(self._pid_reset_btn)

        self._pid_status_label = QLabel("")
        self._pid_status_label.setStyleSheet(f"color: {Colors.SUBTEXT0}; font-size: 11px;")
        reset_row.addWidget(self._pid_status_label)
        reset_row.addStretch()
        pid_layout.addLayout(reset_row)

        main_layout.addWidget(pid_group)

        # ===== 电机参数区 =====
        motor_group = QGroupBox("电机参数")
        motor_layout = QGridLayout(motor_group)
        motor_layout.setSpacing(4)

        self._motor_params = {}
        param_defs = [
            ("resistance", "电阻Ra", 0.1, 50, 2.0, "Ω"),
            ("inductance", "电感La", 0.0001, 1.0, 0.005, "H"),
            ("torque_const", "转矩Kt", 0.001, 1.0, 0.05, "N·m/A"),
            ("back_emf_const", "反电势Ke", 0.001, 1.0, 0.05, "V·s/rad"),
            ("inertia", "惯量J", 0.00001, 1.0, 0.001, "kg·m²"),
            ("friction", "摩擦B", 0.0, 0.01, 0.0001, "N·m·s"),
            ("gear_ratio", "减速比N", 1, 200, 30, ""),
            ("max_voltage", "最大电压", 1, 48, 12, "V"),
        ]

        for i, (key, label, min_v, max_v, default, unit) in enumerate(param_defs):
            row, col = divmod(i, 2)
            spin = QDoubleSpinBox()
            spin.setRange(min_v, max_v)
            spin.setValue(default)
            spin.setDecimals(4)
            spin.setPrefix(f"{label}: ")
            spin.setSuffix(f" {unit}")
            spin.setMaximumWidth(200)
            spin.setMinimumWidth(140)
            motor_layout.addWidget(spin, row, col)
            self._motor_params[key] = spin
            spin.valueChanged.connect(lambda val, k=key: self.motor_params_changed.emit(k, val))

        main_layout.addWidget(motor_group)

        # ===== 控制按钮区 =====
        btn_group = QGroupBox("控制")
        btn_layout = QHBoxLayout(btn_group)

        self._start_btn = QPushButton("▶ 启动")
        self._start_btn.setObjectName("startBtn")
        self._start_btn.setFixedHeight(40)
        self._start_btn.clicked.connect(self.start_clicked.emit)
        btn_layout.addWidget(self._start_btn)

        self._stop_btn = QPushButton("⏹ 停止")
        self._stop_btn.setObjectName("stopBtn")
        self._stop_btn.setFixedHeight(40)
        self._stop_btn.clicked.connect(self.stop_clicked.emit)
        btn_layout.addWidget(self._stop_btn)

        self._reset_btn = QPushButton("🔄 重置")
        self._reset_btn.setFixedHeight(40)
        self._reset_btn.clicked.connect(self.reset_clicked.emit)
        btn_layout.addWidget(self._reset_btn)

        main_layout.addWidget(btn_group)

        main_layout.addStretch()

        # 设置滚动区域
        scroll.setWidget(content)
        outer_layout.addWidget(scroll)

    def _on_mode_changed(self, text):
        mode_map = {
            "速度环 (Speed)": "speed",
            "位置环 (Position)": "position",
            "角度环 (Angle)": "angle",
            "串级控制 (Cascade)": "cascade",
        }
        mode = mode_map.get(text, "speed")
        self.mode_changed.emit(mode)
        if "速度" in text:
            self._target_spin.setSuffix(" rpm")
        elif "位置" in text:
            self._target_spin.setSuffix(" mm")
        elif "角度" in text:
            self._target_spin.setSuffix(" °")
        else:
            self._target_spin.setSuffix(" rpm")

    def _on_target_spin_changed(self, val):
        self._target_slider.blockSignals(True)
        self._target_slider.setValue(int(val))
        self._target_slider.blockSignals(False)
        self.target_changed.emit(val)

    def _on_target_slider_changed(self, val):
        self._target_spin.blockSignals(True)
        self._target_spin.setValue(float(val))
        self._target_spin.blockSignals(False)
        self.target_changed.emit(float(val))

    def _set_target(self, val):
        self._target_spin.setValue(val)

    def _on_pid_confirm(self):
        """确认PID参数修改 - 只有按下确认按钮才会生效并记录日志"""
        loop_map = {0: "single", 1: "outer", 2: "inner"}
        loop = loop_map.get(self._loop_tabs.currentIndex(), "single")

        kp = self._kp_row.value()
        ki = self._ki_row.value()
        kd = self._kd_row.value()

        # 确认所有参数
        self._kp_row.commit()
        self._ki_row.commit()
        self._kd_row.commit()

        # 发射信号
        self.pid_param_changed.emit("kp", kp, loop)
        self.pid_param_changed.emit("ki", ki, loop)
        self.pid_param_changed.emit("kd", kd, loop)

        # 更新状态
        self._pid_status_label.setText(f"✅ 已确认 | Kp={kp:.3f} Ki={ki:.4f} Kd={kd:.4f}")
        self._pid_status_label.setStyleSheet(f"color: {Colors.GREEN}; font-size: 11px; font-weight: bold;")

    def _on_pid_reset(self):
        """恢复默认PID参数"""
        self._kp_row.setValue(1.0)
        self._ki_row.setValue(0.1)
        self._kd_row.setValue(0.01)
        self._pid_status_label.setText("↩ 已恢复默认参数")
        self._pid_status_label.setStyleSheet(f"color: {Colors.YELLOW}; font-size: 11px;")

    @Slot(bool)
    def update_connection_status(self, connected: bool):
        if connected:
            self._conn_status.setText("● 已连接")
            self._conn_status.setStyleSheet(f"color: {Colors.GREEN};")
            self._connect_btn.setText("断开")
        else:
            self._conn_status.setText("● 未连接")
            self._conn_status.setStyleSheet(f"color: {Colors.RED};")
            self._connect_btn.setText("连接")

    @Slot(list)
    def update_port_list(self, ports: list):
        current = self._port_combo.currentText()
        self._port_combo.blockSignals(True)
        self._port_combo.clear()
        self._port_combo.addItems(ports)
        if current in ports:
            self._port_combo.setCurrentText(current)
        self._port_combo.blockSignals(False)

    def get_pid_values(self) -> dict:
        return {
            'kp': self._kp_row.value(),
            'ki': self._ki_row.value(),
            'kd': self._kd_row.value(),
        }

    def set_pid_values(self, kp: float, ki: float, kd: float):
        self._kp_row.setValue(kp)
        self._ki_row.setValue(ki)
        self._kd_row.setValue(kd)
        # 自动确认
        self._kp_row.commit()
        self._ki_row.commit()
        self._kd_row.commit()