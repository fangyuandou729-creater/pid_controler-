"""
波形显示组件
使用PyQtGraph实现高性能实时波形绘制
支持缩放、拖拽、截图保存、数据导出
"""

import time
import os
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional
from collections import deque

import pyqtgraph as pg
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QPushButton,
    QCheckBox, QComboBox, QLabel, QFileDialog, QSplitter,
    QDoubleSpinBox, QToolBar, QSizePolicy, QTabWidget
)
from PySide6.QtCore import Qt, Signal, Slot, QTimer
from PySide6.QtGui import QAction, QKeySequence

from .styles import Colors

# 设置pyqtgraph全局配置
pg.setConfigOptions(antialias=True, background='#11111b', foreground='#cdd6f4')


class RealtimePlot(pg.PlotWidget):
    """实时波形绘图组件"""

    def __init__(self, title: str = "波形", xlabel: str = "时间 (s)",
                 ylabel: str = "值", max_points: int = 2000, parent=None):
        super().__init__(parent)
        self.setTitle(title, color=Colors.BLUE, size='12pt')
        self.setLabel('bottom', xlabel, color=Colors.SUBTEXT0)
        self.setLabel('left', ylabel, color=Colors.SUBTEXT0)
        self.showGrid(x=True, y=True, alpha=0.2)
        self.addLegend(offset=(10, 10), labelTextSize='10px')

        # 启用鼠标交互
        self.setMouseEnabled(x=True, y=True)
        self.enableAutoRange(axis='y', enable=False)

        self._max_points = max_points
        self._curves: Dict[str, pg.PlotDataItem] = {}
        self._data: Dict[str, dict] = {}  # {'x': deque, 'y': deque}
        self._colors = Colors.WAVEFORM_COLORS
        self._color_idx = 0
        self._start_time = time.perf_counter()

        # 设置暗色主题样式
        self.getAxis('left').setPen(pg.mkPen(color='#45475a'))
        self.getAxis('bottom').setPen(pg.mkPen(color='#45475a'))

    def add_curve(self, name: str, color: Optional[str] = None,
                  width: float = 1.5, style: Qt.PenStyle = Qt.SolidLine) -> str:
        """添加一条曲线"""
        if color is None:
            color = self._colors[self._color_idx % len(self._colors)]
            self._color_idx += 1

        pen = pg.mkPen(color=color, width=width, style=style)
        curve = self.plot(pen=pen, name=name, antialias=True)
        self._curves[name] = curve
        self._data[name] = {
            'x': deque(maxlen=self._max_points),
            'y': deque(maxlen=self._max_points),
        }
        return name

    def append_data(self, name: str, x: float, y: float):
        """追加数据点"""
        if name not in self._data:
            return
        self._data[name]['x'].append(x)
        self._data[name]['y'].append(y)

    def update_plot(self):
        """刷新所有曲线的显示"""
        for name, curve in self._curves.items():
            data = self._data[name]
            if len(data['x']) > 0:
                curve.setData(list(data['x']), list(data['y']))

    def clear_data(self):
        """清除所有数据"""
        for name in self._data:
            self._data[name]['x'].clear()
            self._data[name]['y'].clear()
        self.update_plot()

    def get_data_arrays(self, name: str):
        """获取指定曲线的数据数组"""
        if name not in self._data:
            return np.array([]), np.array([])
        return np.array(list(self._data[name]['x'])), np.array(list(self._data[name]['y']))

    def set_max_points(self, n: int):
        self._max_points = n
        for name in self._data:
            old_x = list(self._data[name]['x'])
            old_y = list(self._data[name]['y'])
            self._data[name] = {
                'x': deque(old_x[-n:], maxlen=n),
                'y': deque(old_y[-n:], maxlen=n),
            }


class WaveformDisplay(QWidget):
    """
    波形显示面板
    包含多通道实时波形、控制按钮、截图保存功能
    """
    save_requested = Signal(str)  # 保存路径

    def __init__(self, parent=None):
        super().__init__(parent)
        self._t0 = time.perf_counter()
        self._paused = False
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # 工具栏
        toolbar = QHBoxLayout()

        self._pause_btn = QPushButton("⏸ 暂停")
        self._pause_btn.setCheckable(True)
        self._pause_btn.toggled.connect(self._on_pause_toggled)
        toolbar.addWidget(self._pause_btn)

        self._clear_btn = QPushButton("🗑 清除")
        self._clear_btn.clicked.connect(self._clear_all)
        toolbar.addWidget(self._clear_btn)

        self._auto_range_btn = QPushButton("📐 自动缩放")
        self._auto_range_btn.clicked.connect(self._auto_range)
        toolbar.addWidget(self._auto_range_btn)

        toolbar.addStretch()

        self._point_spin = QDoubleSpinBox()
        self._point_spin.setRange(100, 50000)
        self._point_spin.setValue(2000)
        self._point_spin.setPrefix("显示点数: ")
        self._point_spin.setDecimals(0)
        toolbar.addWidget(self._point_spin)

        self._save_png_btn = QPushButton("📷 保存截图")
        self._save_png_btn.clicked.connect(self._save_screenshot)
        toolbar.addWidget(self._save_png_btn)

        self._save_csv_btn = QPushButton("💾 导出CSV")
        self._save_csv_btn.clicked.connect(self._save_csv)
        toolbar.addWidget(self._save_csv_btn)

        layout.addLayout(toolbar)

        # 标签页容器
        self._tab_widget = QTabWidget()
        layout.addWidget(self._tab_widget, 1)

        # ===== 速度响应波形 =====
        self._speed_plot = RealtimePlot(
            title="速度环响应", xlabel="时间 (s)", ylabel="速度 (rpm)"
        )
        self._speed_plot.add_curve("设定值", color=Colors.WAVEFORM_COLORS[0], width=2)
        self._speed_plot.add_curve("测量值", color=Colors.WAVEFORM_COLORS[1], width=1.5)
        self._speed_plot.add_curve("PID输出", color=Colors.WAVEFORM_COLORS[2], width=1)
        self._tab_widget.addTab(self._speed_plot, "速度响应")

        # ===== 位置响应波形 =====
        self._position_plot = RealtimePlot(
            title="位置环响应", xlabel="时间 (s)", ylabel="位置 (deg)"
        )
        self._position_plot.add_curve("设定值", color=Colors.WAVEFORM_COLORS[0], width=2)
        self._position_plot.add_curve("测量值", color=Colors.WAVEFORM_COLORS[1], width=1.5)
        self._position_plot.add_curve("PID输出", color=Colors.WAVEFORM_COLORS[2], width=1)
        self._tab_widget.addTab(self._position_plot, "位置响应")

        # ===== PID分量波形 =====
        self._pid_plot = RealtimePlot(
            title="PID分量", xlabel="时间 (s)", ylabel="值"
        )
        self._pid_plot.add_curve("P项", color=Colors.WAVEFORM_COLORS[4], width=1.5)
        self._pid_plot.add_curve("I项", color=Colors.WAVEFORM_COLORS[5], width=1.5)
        self._pid_plot.add_curve("D项", color=Colors.WAVEFORM_COLORS[6], width=1.5)
        self._pid_plot.add_curve("误差", color=Colors.WAVEFORM_COLORS[3], width=1, style=Qt.DashLine)
        self._tab_widget.addTab(self._pid_plot, "PID分量")

        # ===== 电流/电压波形 =====
        self._current_plot = RealtimePlot(
            title="电流与电压", xlabel="时间 (s)", ylabel="值"
        )
        self._current_plot.add_curve("电流 (A)", color=Colors.WAVEFORM_COLORS[1], width=1.5)
        self._current_plot.add_curve("电压 (V)", color=Colors.WAVEFORM_COLORS[2], width=1.5)
        self._tab_widget.addTab(self._current_plot, "电流/电压")

        # 刷新定时器
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_plots)
        self._refresh_timer.start(50)  # 20Hz刷新

    def _on_pause_toggled(self, paused):
        self._paused = paused
        self._pause_btn.setText("▶ 继续" if paused else "⏸ 暂停")

    def _clear_all(self):
        self._speed_plot.clear_data()
        self._position_plot.clear_data()
        self._pid_plot.clear_data()
        self._current_plot.clear_data()
        self._t0 = time.perf_counter()

    def _auto_range(self):
        for plot in [self._speed_plot, self._position_plot, self._pid_plot, self._current_plot]:
            plot.enableAutoRange()

    def _refresh_plots(self):
        if self._paused:
            return
        for plot in [self._speed_plot, self._position_plot, self._pid_plot, self._current_plot]:
            plot.update_plot()

    def update_speed(self, t: float, setpoint: float, measurement: float, output: float):
        """更新速度环数据"""
        self._speed_plot.append_data("设定值", t, setpoint)
        self._speed_plot.append_data("测量值", t, measurement)
        self._speed_plot.append_data("PID输出", t, output)

    def update_position(self, t: float, setpoint: float, measurement: float, output: float):
        """更新位置环数据"""
        self._position_plot.append_data("设定值", t, setpoint)
        self._position_plot.append_data("测量值", t, measurement)
        self._position_plot.append_data("PID输出", t, output)

    def update_pid_components(self, t: float, p_term: float, i_term: float,
                               d_term: float, error: float):
        """更新PID分量数据"""
        self._pid_plot.append_data("P项", t, p_term)
        self._pid_plot.append_data("I项", t, i_term)
        self._pid_plot.append_data("D项", t, d_term)
        self._pid_plot.append_data("误差", t, error)

    def update_current_voltage(self, t: float, current: float, voltage: float):
        """更新电流电压数据"""
        self._current_plot.append_data("电流 (A)", t, current)
        self._current_plot.append_data("电压 (V)", t, voltage)

    def _save_screenshot(self):
        """保存当前标签页的波形截图"""
        default_name = f"waveform_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        path, _ = QFileDialog.getSaveFileName(
            self, "保存波形截图", default_name,
            "PNG图像 (*.png);;JPEG图像 (*.jpg);;所有文件 (*.*)"
        )
        if path:
            current_widget = self._tab_widget.currentWidget()
            if isinstance(current_widget, RealtimePlot):
                exporter = pg.exporters.ImageExporter(current_widget.plotItem)
                exporter.export(path)
                self.save_requested.emit(path)

    def _save_csv(self):
        """导出数据为CSV"""
        default_name = f"pid_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        path, _ = QFileDialog.getSaveFileName(
            self, "导出数据", default_name,
            "CSV文件 (*.csv);;所有文件 (*.*)"
        )
        if path:
            try:
                import csv
                with open(path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    # 写入表头
                    writer.writerow(['时间', '速度设定值', '速度测量值', '速度PID输出',
                                     '位置设定值', '位置测量值', '位置PID输出',
                                     'P项', 'I项', 'D项', '误差'])
                    # 获取最大长度
                    max_len = 0
                    for plot in [self._speed_plot, self._position_plot, self._pid_plot]:
                        for name in plot._data:
                            max_len = max(max_len, len(plot._data[name]['x']))

                    for i in range(max_len):
                        row = []
                        # 速度数据
                        for name in ["设定值", "测量值", "PID输出"]:
                            data = self._speed_plot._data.get(name, {'x': [], 'y': []})
                            x_list = list(data['x'])
                            y_list = list(data['y'])
                            if i < len(x_list):
                                if not row:
                                    row.append(x_list[i])
                                row.append(y_list[i])
                            else:
                                row.append('')
                        # 位置数据
                        for name in ["设定值", "测量值", "PID输出"]:
                            data = self._position_plot._data.get(name, {'x': [], 'y': []})
                            y_list = list(data['y'])
                            row.append(y_list[i] if i < len(y_list) else '')
                        # PID分量
                        for name in ["P项", "I项", "D项", "误差"]:
                            data = self._pid_plot._data.get(name, {'y': []})
                            y_list = list(data['y'])
                            row.append(y_list[i] if i < len(y_list) else '')
                        writer.writerow(row)
                self.save_requested.emit(path)
            except Exception as e:
                print(f"CSV导出失败: {e}")