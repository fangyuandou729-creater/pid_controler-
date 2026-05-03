"""
主窗口
整合所有UI组件和核心逻辑，实现完整的PID控制上位机
"""

import time
import logging
from typing import Optional

import numpy as np
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QStatusBar, QLabel, QMenuBar, QMenu, QMessageBox, QApplication,
    QFileDialog, QToolBar, QProgressBar
)
from PySide6.QtCore import Qt, Signal, Slot, QTimer
from PySide6.QtGui import QAction, QKeySequence, QIcon

from .styles import MAIN_STYLESHEET, Colors
from .control_panel import ControlPanel
from .waveform_display import WaveformDisplay
from .log_window import LogWindow
from .motor_sim_widget import MotorSimWidget

from core.pid_controller import PIDController, CascadePIDController, PIDParams, ControlMode
from core.motor_model import DCMotorModel, MotorParams
from core.auto_tuner import AutoTuner, TuningMethod
from core.serial_comm import SerialManager

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """
    主窗口
    左侧: 控制面板 (串口、模式、PID参数、电机参数)
    中间: 波形显示 + 日志窗口
    右侧: 电机仿真
    底部: 状态栏
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("模仿者小队 - DC Motor PID Controller - 直流减速电机闭环控制上位机")
        self.setMinimumSize(1400, 900)
        self.resize(1700, 1000)

        # ===== 核心模块初始化 =====
        self._serial_manager = SerialManager(self)
        self._motor_model = DCMotorModel(parent=self)
        self._pid_controller = PIDController(parent=self)
        self._cascade_pid = CascadePIDController(parent=self)
        self._auto_tuner = AutoTuner(parent=self)

        # 状态
        self._is_running = False
        self._control_mode = ControlMode.SPEED
        self._t0 = time.perf_counter()
        self._step_count = 0
        self._target_value = 100.0

        # 仿真定时器
        self._sim_timer = QTimer(self)
        self._sim_timer.timeout.connect(self._simulation_step)
        self._sim_interval = 10  # 10ms = 100Hz

        # ===== UI构建 =====
        self._setup_central_widget()
        self._setup_menubar()
        self._setup_toolbar()
        self._setup_statusbar()

        # ===== 信号连接 =====
        self._connect_signals()

        # 应用样式
        self.setStyleSheet(MAIN_STYLESHEET)

        # 初始化日志
        logger.info("上位机启动完成")
        self._log_window.log_info("🚀 直流减速电机闭环控制上位机已启动")
        self._log_window.log_info("请连接串口或使用仿真模式进行测试")

    def _setup_menubar(self):
        """创建菜单栏"""
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu("文件(&F)")

        export_csv_action = QAction("导出数据为CSV", self)
        export_csv_action.setShortcut(QKeySequence("Ctrl+S"))
        export_csv_action.triggered.connect(self._export_csv)
        file_menu.addAction(export_csv_action)

        export_log_action = QAction("导出日志", self)
        export_log_action.triggered.connect(self._export_log)
        file_menu.addAction(export_log_action)

        file_menu.addSeparator()

        exit_action = QAction("退出(&X)", self)
        exit_action.setShortcut(QKeySequence("Alt+F4"))
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # 控制菜单
        control_menu = menubar.addMenu("控制(&C)")

        self._start_action = QAction("启动控制", self)
        self._start_action.setShortcut(QKeySequence("F5"))
        self._start_action.triggered.connect(self._start_control)
        control_menu.addAction(self._start_action)

        self._stop_action = QAction("停止控制", self)
        self._stop_action.setShortcut(QKeySequence("F6"))
        self._stop_action.triggered.connect(self._stop_control)
        control_menu.addAction(self._stop_action)

        reset_action = QAction("重置系统", self)
        reset_action.setShortcut(QKeySequence("Ctrl+R"))
        reset_action.triggered.connect(self._reset_system)
        control_menu.addAction(reset_action)

        # 视图菜单
        view_menu = menubar.addMenu("视图(&V)")

        auto_range_action = QAction("自动缩放波形", self)
        auto_range_action.triggered.connect(self._waveform._auto_range)
        view_menu.addAction(auto_range_action)

        clear_wave_action = QAction("清除波形", self)
        clear_wave_action.triggered.connect(self._waveform._clear_all)
        view_menu.addAction(clear_wave_action)

        # 帮助菜单
        help_menu = menubar.addMenu("帮助(&H)")

        about_action = QAction("关于", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

        usage_action = QAction("使用说明", self)
        usage_action.triggered.connect(self._show_usage)
        help_menu.addAction(usage_action)

    def _setup_toolbar(self):
        """创建工具栏"""
        toolbar = QToolBar("快速操作")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self._start_tb = toolbar.addAction("▶ 启动")
        self._start_tb.triggered.connect(self._start_control)

        self._stop_tb = toolbar.addAction("⏹ 停止")
        self._stop_tb.triggered.connect(self._stop_control)

        toolbar.addSeparator()

        self._sim_mode_tb = toolbar.addAction("🖥 仿真模式")
        self._sim_mode_tb.setCheckable(True)
        self._sim_mode_tb.setChecked(True)
        self._sim_mode_tb.triggered.connect(self._toggle_sim_mode)

        toolbar.addSeparator()

        toolbar.addAction("📷 截图", self._waveform._save_screenshot if hasattr(self, '_waveform') else lambda: None)
        toolbar.addAction("💾 导出", self._export_csv)

    def _setup_central_widget(self):
        """构建中心布局"""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(6)

        # 主分割器 (水平)
        h_splitter = QSplitter(Qt.Horizontal)
        h_splitter.setHandleWidth(4)

        # ===== 左侧: 控制面板 =====
        self._control_panel = ControlPanel()
        self._control_panel.setMinimumWidth(360)
        self._control_panel.setMaximumWidth(500)
        h_splitter.addWidget(self._control_panel)

        # ===== 中间: 波形 + 日志 (垂直分割) =====
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(4)

        v_splitter = QSplitter(Qt.Vertical)

        # 波形显示
        self._waveform = WaveformDisplay()
        v_splitter.addWidget(self._waveform)

        # 日志窗口
        self._log_window = LogWindow()
        self._log_window.setMinimumHeight(120)
        v_splitter.addWidget(self._log_window)

        v_splitter.setSizes([600, 200])
        center_layout.addWidget(v_splitter)
        h_splitter.addWidget(center_widget)

        # ===== 右侧: 电机仿真 =====
        self._motor_sim = MotorSimWidget()
        self._motor_sim.setMinimumWidth(280)
        self._motor_sim.setMaximumWidth(400)
        h_splitter.addWidget(self._motor_sim)

        h_splitter.setSizes([400, 900, 350])
        main_layout.addWidget(h_splitter)

    def _setup_statusbar(self):
        """创建状态栏"""
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)

        self._conn_label = QLabel("● 未连接")
        self._conn_label.setStyleSheet(f"color: {Colors.RED};")
        self._statusbar.addWidget(self._conn_label)

        self._mode_label = QLabel("模式: 速度环")
        self._statusbar.addWidget(self._mode_label)

        self._run_label = QLabel("状态: 停止")
        self._run_label.setStyleSheet(f"color: {Colors.SUBTEXT0};")
        self._statusbar.addWidget(self._run_label)

        self._fps_label = QLabel("FPS: --")
        self._statusbar.addPermanentWidget(self._fps_label)

        self._time_label = QLabel("运行时间: 00:00")
        self._statusbar.addPermanentWidget(self._time_label)

        # FPS计算定时器
        self._fps_timer = QTimer(self)
        self._fps_timer.timeout.connect(self._update_fps)
        self._fps_timer.start(1000)
        self._fps_counter = 0
        self._last_fps_time = time.perf_counter()

    def _connect_signals(self):
        """连接所有信号"""
        # 串口管理器
        self._serial_manager.connection_changed.connect(self._on_connection_changed)
        self._serial_manager.port_list_changed.connect(self._control_panel.update_port_list)
        self._serial_manager.log_message.connect(self._log_window.append_log)
        self._serial_manager.error_occurred.connect(lambda msg: self._log_window.log_error(msg))
        self._serial_manager.data_received.connect(self._on_serial_data)

        # 控制面板
        self._control_panel.start_clicked.connect(self._start_control)
        self._control_panel.stop_clicked.connect(self._stop_control)
        self._control_panel.reset_clicked.connect(self._reset_system)
        self._control_panel.mode_changed.connect(self._on_mode_changed)
        self._control_panel.target_changed.connect(self._on_target_changed)
        self._control_panel.pid_param_changed.connect(self._on_pid_param_changed)
        self._control_panel.auto_tune_clicked.connect(self._on_auto_tune)
        self._control_panel.motor_params_changed.connect(self._on_motor_param_changed)

        # 串口连接按钮
        self._control_panel._connect_btn.clicked.connect(self._toggle_connection)
        self._control_panel._refresh_btn.clicked.connect(
            lambda: self._control_panel.update_port_list(
                [p['port'] for p in self._serial_manager.get_available_ports()]
            )
        )

    def _toggle_connection(self):
        """切换串口连接"""
        if self._serial_manager.is_connected:
            self._serial_manager.disconnect()
        else:
            port = self._control_panel._port_combo.currentText()
            baud = int(self._control_panel._baud_combo.currentText())
            if port:
                self._serial_manager.connect(port, baud)

    @Slot(bool)
    def _on_connection_changed(self, connected: bool):
        self._control_panel.update_connection_status(connected)
        if connected:
            self._conn_label.setText(f"● 已连接 ({self._serial_manager.port_name})")
            self._conn_label.setStyleSheet(f"color: {Colors.GREEN};")
        else:
            self._conn_label.setText("● 未连接")
            self._conn_label.setStyleSheet(f"color: {Colors.RED};")

    @Slot(str)
    def _on_mode_changed(self, mode_str: str):
        mode_map = {
            "speed": ControlMode.SPEED,
            "position": ControlMode.POSITION,
            "angle": ControlMode.ANGLE,
            "cascade": ControlMode.CASCADE,
        }
        self._control_mode = mode_map.get(mode_str, ControlMode.SPEED)
        self._mode_label.setText(f"模式: {mode_str}")
        self._log_window.log_info(f"控制模式切换: {mode_str}")

        # 更新目标值单位
        unit_map = {
            ControlMode.SPEED: "rpm",
            ControlMode.POSITION: "mm",
            ControlMode.ANGLE: "°",
            ControlMode.CASCADE: "rpm",
        }
        self._target_value = self._control_panel._target_spin.value()

    @Slot(float)
    def _on_target_changed(self, value: float):
        self._target_value = value
        self._pid_controller.params.setpoint = value
        self._cascade_pid.outer_loop.params.setpoint = value
        self._log_window.log_debug(f"目标值更新: {value}")

    @Slot(str, float, str)
    def _on_pid_param_changed(self, param_name: str, value: float, loop: str):
        if loop == "single" or loop == "outer":
            setattr(self._pid_controller.params, param_name, value)
            setattr(self._cascade_pid.outer_loop.params, param_name, value)
        elif loop == "inner":
            setattr(self._cascade_pid.inner_loop.params, param_name, value)

        # 发送到MCU
        if self._serial_manager.is_connected:
            if loop == "inner":
                self._serial_manager.send_pid_params(
                    self._cascade_pid.inner_loop.params.kp,
                    self._cascade_pid.inner_loop.params.ki,
                    self._cascade_pid.inner_loop.params.kd,
                    loop_id=1
                )
            else:
                kp = self._control_panel._kp_row.value()
                ki = self._control_panel._ki_row.value()
                kd = self._control_panel._kd_row.value()
                self._serial_manager.send_pid_params(kp, ki, kd, loop_id=0)

        self._log_window.log_info(f"PID参数已确认 [{loop}] {param_name} = {value:.4f}")

    @Slot(str, float)
    def _on_motor_param_changed(self, key: str, value: float):
        self._motor_model.set_params(**{key: value})

    @Slot(str)
    def _on_auto_tune(self, method_name: str):
        """执行自动调参"""
        self._log_window.log_info(f"开始自动调参: {method_name}")

        # 获取当前波形数据
        t_data, y_data = self._waveform._speed_plot.get_data_arrays("测量值")
        setpoint = self._target_value

        if len(t_data) < 20:
            self._log_window.log_warning("数据不足，请先运行控制并收集响应数据")
            QMessageBox.warning(self, "自动调参", "请先运行控制并收集足够的响应数据（至少20个数据点）")
            return

        method_map = {
            "Ziegler-Nichols": TuningMethod.ZIEGLER_NICHOLS,
            "Cohen-Coon": TuningMethod.COHEN_COON,
            "阶跃响应法": TuningMethod.SIMPLE,
        }

        method = method_map.get(method_name)
        if method:
            try:
                result = self._auto_tuner.auto_tune(
                    method, t_data, y_data, setpoint
                )
                self._control_panel.set_pid_values(result.kp, result.ki, result.kd)
                self._pid_controller.params.kp = result.kp
                self._pid_controller.params.ki = result.ki
                self._pid_controller.params.kd = result.kd
                self._log_window.log_info(f"自动调参完成: {result}")
                if result.performance:
                    self._log_window.log_performance(result.performance)
            except Exception as e:
                self._log_window.log_error(f"自动调参失败: {e}")
                QMessageBox.warning(self, "自动调参失败", str(e))
        elif method_name == "PSO优化":
            self._run_pso_tuning()
        elif method_name == "继电反馈法":
            self._log_window.log_info("继电反馈法需要实时硬件支持，仿真模式下使用Z-N法替代")
            try:
                result = self._auto_tuner.auto_tune(
                    TuningMethod.ZIEGLER_NICHOLS, t_data, y_data, setpoint
                )
                self._control_panel.set_pid_values(result.kp, result.ki, result.kd)
                self._pid_controller.params.kp = result.kp
                self._pid_controller.params.ki = result.ki
                self._pid_controller.params.kd = result.kd
                self._log_window.log_info(f"替代调参完成: {result}")
            except Exception as e:
                self._log_window.log_error(f"调参失败: {e}")

    def _run_pso_tuning(self):
        """运行PSO优化"""
        t_data, y_data = self._waveform._speed_plot.get_data_arrays("测量值")
        setpoint = self._target_value

        if len(t_data) < 50:
            self._log_window.log_warning("PSO优化需要更多数据，请先运行控制")
            return

        def fitness_fn(kp, ki, kd):
            """适应度函数: 模拟PID控制并计算ITAE指标"""
            pid = PIDController(PIDParams(kp=kp, ki=ki, kd=kd,
                                          setpoint=setpoint,
                                          output_min=-100, output_max=100))
            motor = DCMotorModel()
            dt = 0.01
            total_cost = 0.0
            n_steps = min(len(t_data), 500)

            for i in range(n_steps):
                state = motor.get_state()
                measurement = state.get('speed_rpm', 0)
                output = pid.update(measurement, dt)
                motor.update(output * 0.1, dt)
                error = abs(setpoint - measurement)
                # ITAE指标
                total_cost += (i * dt) * error

            # 加入超调惩罚
            history = pid.get_history()
            if history['measurement']:
                max_val = max(history['measurement'])
                overshoot = max(0, max_val - setpoint) / abs(setpoint) * 100 if abs(setpoint) > 0 else 0
                total_cost += overshoot * 5

            return total_cost

        self._log_window.log_info("开始PSO优化...")
        try:
            result = self._auto_tuner.pso_optimize(
                fitness_fn,
                bounds=([0.01, 0.0, 0.0], [50.0, 20.0, 10.0]),
                n_particles=20,
                n_iterations=30,
            )
            self._control_panel.set_pid_values(result.kp, result.ki, result.kd)
            self._pid_controller.params.kp = result.kp
            self._pid_controller.params.ki = result.ki
            self._pid_controller.params.kd = result.kd
            self._log_window.log_info(f"PSO优化完成: {result}")
        except Exception as e:
            self._log_window.log_error(f"PSO优化失败: {e}")

    def _start_control(self):
        """启动控制"""
        if self._is_running:
            return

        self._is_running = True
        self._t0 = time.perf_counter()
        self._step_count = 0
        self._pid_controller.reset()
        self._cascade_pid.reset()
        self._motor_model.reset()

        # 设置PID目标值
        self._pid_controller.params.setpoint = self._target_value
        self._cascade_pid.outer_loop.params.setpoint = self._target_value

        # 启动仿真定时器
        self._sim_timer.start(self._sim_interval)

        self._run_label.setText("状态: 运行中")
        self._run_label.setStyleSheet(f"color: {Colors.GREEN};")
        self._log_window.log_info(f"▶ 控制启动 | 模式: {self._control_mode.value} | 目标: {self._target_value}")

        # 发送到MCU
        if self._serial_manager.is_connected:
            self._serial_manager.send_start_stop(True)
            self._serial_manager.send_target(self._target_value)

    def _stop_control(self):
        """停止控制"""
        if not self._is_running:
            return

        self._is_running = False
        self._sim_timer.stop()

        self._run_label.setText("状态: 停止")
        self._run_label.setStyleSheet(f"color: {Colors.RED};")
        self._log_window.log_info("⏹ 控制停止")

        if self._serial_manager.is_connected:
            self._serial_manager.send_start_stop(False)

    def _reset_system(self):
        """重置系统"""
        self._stop_control()
        self._pid_controller.reset()
        self._cascade_pid.reset()
        self._motor_model.reset()
        self._motor_sim.reset()
        self._step_count = 0
        self._log_window.log_info("🔄 系统已重置")

    def _simulation_step(self):
        """仿真步进 - 核心控制循环"""
        if not self._is_running:
            return

        dt = self._sim_interval / 1000.0  # 转换为秒
        t = time.perf_counter() - self._t0
        self._step_count += 1

        # 获取当前电机状态
        motor_state = self._motor_model.get_state()

        # 根据控制模式选择测量值
        if self._control_mode == ControlMode.SPEED:
            measurement = motor_state.get('speed_rpm', 0)
            output = self._pid_controller.update(measurement, dt)
        elif self._control_mode == ControlMode.POSITION:
            measurement = motor_state.get('position_deg', 0)
            output = self._pid_controller.update(measurement, dt)
        elif self._control_mode == ControlMode.ANGLE:
            measurement = motor_state.get('position_deg', 0)
            output = self._pid_controller.update(measurement, dt)
        elif self._control_mode == ControlMode.CASCADE:
            outer_meas = motor_state.get('position_deg', 0)
            inner_meas = motor_state.get('speed_rpm', 0)
            output = self._cascade_pid.update(outer_meas, inner_meas, dt)
        else:
            measurement = motor_state.get('speed_rpm', 0)
            output = self._pid_controller.update(measurement, dt)

        # 电机模型更新
        voltage = output * 0.12  # 输出映射到电压
        motor_state = self._motor_model.update(voltage, dt)

        # 获取PID状态
        pid_state = self._pid_controller.get_latest_state()

        # ===== 更新波形显示 =====
        self._waveform.update_speed(
            t,
            self._pid_controller.params.setpoint,
            motor_state.get('speed_rpm', 0),
            output
        )
        self._waveform.update_position(
            t,
            self._pid_controller.params.setpoint,
            motor_state.get('position_deg', 0),
            output
        )
        if pid_state:
            self._waveform.update_pid_components(
                t,
                pid_state.get('p_term', 0),
                pid_state.get('i_term', 0),
                pid_state.get('d_term', 0),
                pid_state.get('error', 0),
            )
        self._waveform.update_current_voltage(
            t,
            motor_state.get('current', 0),
            motor_state.get('voltage', 0),
        )

        # ===== 更新电机仿真 =====
        self._motor_sim.update_state(motor_state)

        # FPS计数
        self._fps_counter += 1

        # 发送到MCU
        if self._serial_manager.is_connected and self._step_count % 5 == 0:
            self._serial_manager.send_pid_params(
                self._pid_controller.params.kp,
                self._pid_controller.params.ki,
                self._pid_controller.params.kd,
            )

    def _update_fps(self):
        """更新FPS显示"""
        now = time.perf_counter()
        elapsed = now - self._last_fps_time
        fps = self._fps_counter / elapsed if elapsed > 0 else 0
        self._fps_label.setText(f"FPS: {fps:.0f}")
        self._fps_counter = 0
        self._last_fps_time = now

        # 更新运行时间
        if self._is_running:
            run_time = now - self._t0
            mins = int(run_time // 60)
            secs = int(run_time % 60)
            self._time_label.setText(f"运行时间: {mins:02d}:{secs:02d}")

    def _toggle_sim_mode(self, checked):
        """切换仿真模式"""
        if checked:
            self._log_window.log_info("已切换到仿真模式")
        else:
            self._log_window.log_info("已切换到硬件模式（需要连接串口）")

    def _on_serial_data(self, data: dict):
        """处理来自MCU的数据"""
        if 'measurement' in data:
            # 可以用MCU数据替代仿真数据
            pass

    def _export_csv(self):
        self._waveform._save_csv()

    def _export_log(self):
        self._log_window._save_log()

    def _show_about(self):
        QMessageBox.about(
            self,
            "关于",
            "<h2>DC Motor PID Controller</h2>"
            "<p>直流减速电机闭环控制上位机 v1.0</p>"
            "<p>功能特性:</p>"
            "<ul>"
            "<li>手动/自动PID参数调节</li>"
            "<li>串级PID、位置环、速度环、角度环控制</li>"
            "<li>实时波形显示与图像保存</li>"
            "<li>电机仿真动画</li>"
            "<li>Ziegler-Nichols / Cohen-Coon / PSO自动调参</li>"
            "<li>串口通信与MCU交互</li>"
            "</ul>"
            "<p>技术栈: PySide6 + PyQtGraph + NumPy + SciPy</p>"
        )

    def _show_usage(self):
        QMessageBox.information(
            self,
            "使用说明",
            "<h3>快速开始</h3>"
            "<ol>"
            "<li><b>仿真模式</b>: 直接点击 ▶ 启动，即可看到PID控制效果</li>"
            "<li><b>调节参数</b>: 拖动Kp/Ki/Kd滑块或旋钮实时调节PID参数</li>"
            "<li><b>切换模式</b>: 在控制模式下拉框选择速度环/位置环/角度环/串级</li>"
            "<li><b>自动调参</b>: 勾选自动PID调参模式，选择方法后点击开始</li>"
            "<li><b>硬件连接</b>: 选择串口端口和波特率，点击连接</li>"
            "</ol>"
            "<h3>快捷键</h3>"
            "<ul>"
            "<li>F5: 启动控制</li>"
            "<li>F6: 停止控制</li>"
            "<li>Ctrl+R: 重置系统</li>"
            "<li>Ctrl+S: 导出数据</li>"
            "</ul>"
        )

    def closeEvent(self, event):
        """关闭事件"""
        self._stop_control()
        self._serial_manager.disconnect()
        self._log_window.log_info("上位机已退出")
        event.accept()