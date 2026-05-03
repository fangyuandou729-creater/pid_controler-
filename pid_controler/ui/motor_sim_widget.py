"""
电机仿真动画组件
用Qt绘图模拟直流减速电机的运动状态
包含：逼真电机外观、转子旋转动画、齿轮减速器、速度/电流仪表盘
"""

import math
import time
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QGridLayout, QFrame, QProgressBar
)
from PySide6.QtCore import Qt, Signal, Slot, QTimer, QRectF, QPointF
from PySide6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QRadialGradient,
    QLinearGradient, QPainterPath, QConicalGradient
)

from .styles import Colors


class GaugeWidget(QWidget):
    """圆形仪表盘控件"""

    def __init__(self, title: str = "", unit: str = "",
                 min_val: float = -300, max_val: float = 300,
                 green_range: tuple = (-100, 100),
                 parent=None):
        super().__init__(parent)
        self._title = title
        self._unit = unit
        self._min = min_val
        self._max = max_val
        self._value = 0.0
        self._target = 0.0
        self._green_range = green_range
        self.setMinimumSize(140, 140)

    def setValue(self, val: float):
        self._value = val
        self.update()

    def setTarget(self, val: float):
        self._target = val
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        size = min(w, h)
        cx, cy = w / 2, h / 2
        r = size / 2 - 10

        # 背景圆
        painter.setPen(QPen(QColor(Colors.SURFACE1), 2))
        painter.setBrush(QBrush(QColor(Colors.MANTLE)))
        painter.drawEllipse(QPointF(cx, cy), r, r)

        # 刻度弧
        start_angle = 225 * 16
        span_angle = -270 * 16

        painter.setPen(QPen(QColor(Colors.SURFACE1), 3))
        painter.drawArc(QRectF(cx - r + 8, cy - r + 8, 2 * (r - 8), 2 * (r - 8)),
                        start_angle, span_angle)

        # 刻度线和数值
        painter.setPen(QPen(QColor(Colors.SUBTEXT0), 1))
        painter.setFont(QFont("Consolas", 8))
        num_ticks = 10
        for i in range(num_ticks + 1):
            angle = math.radians(225 - 270 * i / num_ticks)
            val = self._min + (self._max - self._min) * i / num_ticks

            # 刻度线
            x1 = cx + (r - 12) * math.cos(angle)
            y1 = cy - (r - 12) * math.sin(angle)
            x2 = cx + (r - 20) * math.cos(angle)
            y2 = cy - (r - 20) * math.sin(angle)
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

            # 刻度数值
            tx = cx + (r - 30) * math.cos(angle)
            ty = cy - (r - 30) * math.sin(angle)
            painter.drawText(QPointF(tx - 10, ty + 4), f"{val:.0f}")

        # 值指示弧
        value_ratio = (self._value - self._min) / (self._max - self._min) if self._max != self._min else 0
        value_ratio = max(0, min(1, value_ratio))
        value_angle = int(-270 * value_ratio * 16)

        # 根据值选择颜色
        if self._green_range[0] <= self._value <= self._green_range[1]:
            color = QColor(Colors.GREEN)
        elif abs(self._value) > self._max * 0.8:
            color = QColor(Colors.RED)
        else:
            color = QColor(Colors.YELLOW)

        pen = QPen(color, 5)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.drawArc(QRectF(cx - r + 4, cy - r + 4, 2 * (r - 4), 2 * (r - 4)),
                        start_angle, value_angle)

        # 指针
        needle_angle = math.radians(225 - 270 * value_ratio)
        nx = cx + (r - 25) * math.cos(needle_angle)
        ny = cy - (r - 25) * math.sin(needle_angle)

        painter.setPen(QPen(QColor(Colors.TEXT), 2))
        painter.drawLine(QPointF(cx, cy), QPointF(nx, ny))

        # 中心圆
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(Colors.BLUE)))
        painter.drawEllipse(QPointF(cx, cy), 5, 5)

        # 标题
        painter.setPen(QColor(Colors.BLUE))
        painter.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
        painter.drawText(QRectF(0, cy + r * 0.2, w, 20), Qt.AlignCenter, self._title)

        # 值显示
        painter.setPen(QColor(Colors.TEXT))
        painter.setFont(QFont("Consolas", 14, QFont.Bold))
        painter.drawText(QRectF(0, cy - 10, w, 24), Qt.AlignCenter,
                         f"{self._value:.1f}")

        # 单位
        painter.setPen(QColor(Colors.SUBTEXT0))
        painter.setFont(QFont("Microsoft YaHei", 8))
        painter.drawText(QRectF(0, cy + r * 0.35, w, 16), Qt.AlignCenter, self._unit)

        painter.end()


class MotorVisualWidget(QWidget):
    """电机可视化控件 - 逼真的直流减速电机模型"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rotation_angle = 0.0       # 转子角度 (度)
        self._target_angle = 0.0
        self._speed = 0.0                # 当前速度 (rpm)
        self._current = 0.0              # 当前电流
        self._voltage = 0.0              # 当前电压
        self._running = False
        self.setMinimumSize(280, 220)

        # 动画定时器
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._animate)
        self._anim_timer.start(33)  # ~30fps

    def setState(self, speed: float, current: float, voltage: float,
                 position: float):
        self._speed = speed
        self._current = current
        self._voltage = voltage
        self._target_angle = position
        self._running = True
        self.update()

    def reset(self):
        self._rotation_angle = 0
        self._target_angle = 0
        self._speed = 0
        self._current = 0
        self._voltage = 0
        self.update()

    def _animate(self):
        if abs(self._target_angle - self._rotation_angle) > 0.1:
            diff = self._target_angle - self._rotation_angle
            self._rotation_angle += diff * 0.3
        else:
            self._rotation_angle = self._target_angle
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        cx, cy = w / 2, h / 2

        # 背景
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(Colors.CRUST)))
        painter.drawRoundedRect(self.rect(), 10, 10)

        # ===== 电机主体（圆柱形） =====
        body_w = w * 0.45
        body_h = h * 0.4
        body_x = cx - body_w * 0.55
        body_y = cy - body_h / 2

        # 电机外壳 - 圆柱体效果
        shell_grad = QLinearGradient(body_x, body_y, body_x, body_y + body_h)
        shell_grad.setColorAt(0, QColor("#4a4a7a"))
        shell_grad.setColorAt(0.15, QColor("#3a3a6a"))
        shell_grad.setColorAt(0.5, QColor("#2a2a55"))
        shell_grad.setColorAt(0.85, QColor("#3a3a6a"))
        shell_grad.setColorAt(1, QColor("#4a4a7a"))
        painter.setBrush(QBrush(shell_grad))
        painter.setPen(QPen(QColor(Colors.SURFACE1), 2))
        painter.drawRoundedRect(QRectF(body_x, body_y, body_w, body_h), 12, 12)

        # 散热片
        painter.setPen(QPen(QColor(Colors.SURFACE0), 1))
        for i in range(10):
            x = body_x + body_w * 0.08 + i * body_w * 0.085
            painter.drawLine(QPointF(x, body_y + 4), QPointF(x, body_y + body_h - 4))

        # 端盖（左侧圆形）
        endcap_r = body_h / 2
        endcap_x = body_x
        endcap_grad = QRadialGradient(endcap_x, cy, endcap_r)
        endcap_grad.setColorAt(0, QColor("#5555aa"))
        endcap_grad.setColorAt(0.7, QColor("#3a3a7a"))
        endcap_grad.setColorAt(1, QColor("#2a2a5a"))
        painter.setBrush(QBrush(endcap_grad))
        painter.setPen(QPen(QColor(Colors.SURFACE1), 2))
        painter.drawEllipse(QPointF(endcap_x, cy), endcap_r * 0.9, endcap_r * 0.9)

        # 接线端子（顶部）
        terminal_w = 25
        terminal_h = 18
        terminal_x = cx - body_w * 0.1
        terminal_y = body_y - terminal_h + 2
        painter.setBrush(QBrush(QColor("#2d4a2d")))
        painter.setPen(QPen(QColor(Colors.SURFACE1), 1.5))
        painter.drawRoundedRect(QRectF(terminal_x, terminal_y, terminal_w, terminal_h), 3, 3)
        painter.setBrush(QBrush(QColor("#2d4a2d")))
        painter.drawRoundedRect(QRectF(terminal_x + 35, terminal_y, terminal_w, terminal_h), 3, 3)

        # 红黑引线
        painter.setPen(QPen(QColor(Colors.RED), 2.5))
        painter.drawLine(QPointF(terminal_x + 12, terminal_y),
                         QPointF(terminal_x + 12, terminal_y - 12))
        painter.drawLine(QPointF(terminal_x + 12, terminal_y - 12),
                         QPointF(terminal_x + 30, terminal_y - 12))
        painter.setPen(QPen(QColor("#555555"), 2.5))
        painter.drawLine(QPointF(terminal_x + 47, terminal_y),
                         QPointF(terminal_x + 47, terminal_y - 12))
        painter.drawLine(QPointF(terminal_x + 47, terminal_y - 12),
                         QPointF(terminal_x + 65, terminal_y - 12))

        # 标签 "M"
        painter.setPen(QColor(Colors.BLUE))
        painter.setFont(QFont("Consolas", 14, QFont.Bold))
        painter.drawText(QRectF(body_x + body_w * 0.02, cy - 12, 25, 24), Qt.AlignCenter, "M")

        # ===== 转子（内部旋转部分） =====
        rotor_cx = endcap_x + body_h * 0.05
        rotor_r = body_h * 0.35
        painter.save()
        painter.translate(rotor_cx, cy)
        painter.rotate(self._rotation_angle)

        # 转子铁芯
        rotor_grad = QRadialGradient(0, 0, rotor_r)
        rotor_grad.setColorAt(0, QColor("#6666aa"))
        rotor_grad.setColorAt(0.6, QColor("#4444aa"))
        rotor_grad.setColorAt(1, QColor("#3333aa"))
        painter.setBrush(QBrush(rotor_grad))
        painter.setPen(QPen(QColor("#5555bb"), 1.5))
        painter.drawEllipse(QPointF(0, 0), rotor_r, rotor_r)

        # 转子绕组（3组线圈）
        painter.setPen(QPen(QColor(Colors.RED), 3))
        painter.drawLine(QPointF(0, 0), QPointF(rotor_r * 0.75, 0))
        painter.setPen(QPen(QColor(Colors.GREEN), 3))
        painter.drawLine(QPointF(0, 0), QPointF(-rotor_r * 0.375, rotor_r * 0.65))
        painter.setPen(QPen(QColor("#5599ff"), 3))
        painter.drawLine(QPointF(0, 0), QPointF(-rotor_r * 0.375, -rotor_r * 0.65))

        # 转子槽（6条）
        painter.setPen(QPen(QColor(Colors.SURFACE0), 1.5))
        for i in range(6):
            angle = math.radians(i * 60)
            x1 = rotor_r * 0.35 * math.cos(angle)
            y1 = rotor_r * 0.35 * math.sin(angle)
            x2 = rotor_r * 0.82 * math.cos(angle)
            y2 = rotor_r * 0.82 * math.sin(angle)
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

        # 换向器
        for i in range(3):
            angle = math.radians(i * 120 + 30)
            comm_x = rotor_r * 0.9 * math.cos(angle)
            comm_y = rotor_r * 0.9 * math.sin(angle)
            painter.setBrush(QBrush(QColor("#ccaa44")))
            painter.setPen(QPen(QColor("#aa8833"), 1))
            painter.drawEllipse(QPointF(comm_x, comm_y), 4, 4)

        painter.restore()

        # ===== 碳刷 =====
        brush_y_top = cy - rotor_r * 0.6
        brush_y_bot = cy + rotor_r * 0.6
        painter.setBrush(QBrush(QColor("#444444")))
        painter.setPen(QPen(QColor(Colors.SURFACE1), 1))
        painter.drawRect(QRectF(rotor_cx - rotor_r - 14, brush_y_top - 4, 14, 8))
        painter.drawRect(QRectF(rotor_cx - rotor_r - 14, brush_y_bot - 4, 14, 8))

        # ===== 减速器箱体 =====
        gear_x = body_x + body_w + 5
        gear_w = w * 0.18
        gear_h = body_h * 1.15
        gear_y = cy - gear_h / 2

        gear_grad = QLinearGradient(gear_x, gear_y, gear_x, gear_y + gear_h)
        gear_grad.setColorAt(0, QColor("#3d3d60"))
        gear_grad.setColorAt(0.5, QColor("#2d2d50"))
        gear_grad.setColorAt(1, QColor("#3d3d60"))
        painter.setBrush(QBrush(gear_grad))
        painter.setPen(QPen(QColor(Colors.SURFACE1), 2))
        painter.drawRoundedRect(QRectF(gear_x, gear_y, gear_w, gear_h), 6, 6)

        # 减速器标签
        painter.setPen(QColor(Colors.SUBTEXT0))
        painter.setFont(QFont("Consolas", 8, QFont.Bold))
        painter.drawText(QRectF(gear_x, gear_y + 2, gear_w, 14), Qt.AlignCenter, "GEARBOX")
        painter.setFont(QFont("Consolas", 7))
        painter.drawText(QRectF(gear_x, gear_y + gear_h - 14, gear_w, 12), Qt.AlignCenter, "N:30:1")

        # 内部齿轮示意
        gear_cx = gear_x + gear_w / 2
        painter.save()
        painter.translate(gear_cx, cy)

        # 大齿轮
        big_r = min(gear_w, gear_h) * 0.3
        big_rot = self._rotation_angle / 30.0  # 减速比30
        painter.rotate(big_rot)
        painter.setPen(QPen(QColor(Colors.SURFACE1), 1.5))
        painter.setBrush(QBrush(QColor("#4444aa")))
        painter.drawEllipse(QPointF(0, 0), big_r, big_r)
        # 齿
        for i in range(12):
            a = math.radians(i * 30)
            tx1 = (big_r - 3) * math.cos(a)
            ty1 = (big_r - 3) * math.sin(a)
            tx2 = (big_r + 4) * math.cos(a)
            ty2 = (big_r + 4) * math.sin(a)
            painter.setPen(QPen(QColor("#5555cc"), 2))
            painter.drawLine(QPointF(tx1, ty1), QPointF(tx2, ty2))

        painter.restore()

        # 小齿轮（输入）
        small_cx = gear_cx - big_r * 0.7
        small_r = big_r * 0.35
        painter.save()
        painter.translate(small_cx, cy - big_r * 0.4)
        painter.rotate(-self._rotation_angle)  # 反转
        painter.setPen(QPen(QColor(Colors.SURFACE1), 1))
        painter.setBrush(QBrush(QColor("#5555cc")))
        painter.drawEllipse(QPointF(0, 0), small_r, small_r)
        for i in range(8):
            a = math.radians(i * 45)
            painter.setPen(QPen(QColor("#6666dd"), 1.5))
            painter.drawLine(
                QPointF((small_r - 2) * math.cos(a), (small_r - 2) * math.sin(a)),
                QPointF((small_r + 3) * math.cos(a), (small_r + 3) * math.sin(a))
            )
        painter.restore()

        # ===== 输出轴 =====
        shaft_x = gear_x + gear_w
        shaft_w = w * 0.12
        shaft_h = 10
        shaft_y = cy - shaft_h / 2

        # 轴
        shaft_grad = QLinearGradient(shaft_x, shaft_y, shaft_x, shaft_y + shaft_h)
        shaft_grad.setColorAt(0, QColor("#666688"))
        shaft_grad.setColorAt(0.5, QColor("#888888"))
        shaft_grad.setColorAt(1, QColor("#666688"))
        painter.setBrush(QBrush(shaft_grad))
        painter.setPen(QPen(QColor(Colors.SURFACE1), 1.5))
        painter.drawRect(QRectF(shaft_x, shaft_y, shaft_w, shaft_h))

        # 轴端D型切面
        painter.setPen(QPen(QColor("#aaaacc"), 1))
        painter.drawLine(QPointF(shaft_x + shaft_w - 3, shaft_y + 2),
                         QPointF(shaft_x + shaft_w - 3, shaft_y + shaft_h - 2))

        # 轴标记线
        painter.setPen(QPen(QColor(Colors.GREEN), 2))
        painter.drawLine(QPointF(shaft_x + shaft_w * 0.3, shaft_y),
                         QPointF(shaft_x + shaft_w * 0.3, shaft_y + shaft_h))

        # ===== 底座 =====
        base_x = body_x - 10
        base_w = (shaft_x + shaft_w) - base_x + 10
        base_y = body_y + body_h
        base_h = 8
        painter.setBrush(QBrush(QColor(Colors.SURFACE0)))
        painter.setPen(QPen(QColor(Colors.SURFACE1), 1))
        painter.drawRect(QRectF(base_x, base_y, base_w, base_h))

        # 安装孔
        painter.setBrush(QBrush(QColor(Colors.CRUST)))
        painter.drawEllipse(QPointF(base_x + 12, base_y + base_h / 2), 3, 3)
        painter.drawEllipse(QPointF(base_x + base_w - 12, base_y + base_h / 2), 3, 3)

        # ===== 电流方向箭头 =====
        if abs(self._current) > 0.01:
            arrow_color = QColor(Colors.GREEN) if self._current > 0 else QColor(Colors.RED)
            painter.setPen(QPen(arrow_color, 2.5))
            arrow_y = body_y - 28
            if self._current > 0:
                painter.drawLine(QPointF(cx - 35, arrow_y), QPointF(cx + 35, arrow_y))
                painter.drawLine(QPointF(cx + 28, arrow_y - 6), QPointF(cx + 35, arrow_y))
                painter.drawLine(QPointF(cx + 28, arrow_y + 6), QPointF(cx + 35, arrow_y))
            else:
                painter.drawLine(QPointF(cx + 35, arrow_y), QPointF(cx - 35, arrow_y))
                painter.drawLine(QPointF(cx - 28, arrow_y - 6), QPointF(cx - 35, arrow_y))
                painter.drawLine(QPointF(cx - 28, arrow_y + 6), QPointF(cx - 35, arrow_y))

            painter.setPen(QColor(arrow_color))
            painter.setFont(QFont("Consolas", 8))
            painter.drawText(QRectF(cx - 40, arrow_y - 14, 80, 12), Qt.AlignCenter,
                             f"I = {abs(self._current):.2f}A")

        # ===== 状态文字 =====
        painter.setPen(QColor(Colors.TEXT))
        painter.setFont(QFont("Consolas", 10))
        status = "● 运行中" if self._running and abs(self._speed) > 0.1 else "○ 停止"
        status_color = Colors.GREEN if "运行" in status else Colors.SUBTEXT0
        painter.setPen(QColor(status_color))
        painter.drawText(QRectF(0, h - 22, w, 18), Qt.AlignCenter,
                         f"{status}  |  {self._speed:.1f} rpm  |  {self._voltage:.1f} V")

        painter.end()


class MotorSimWidget(QWidget):
    """
    电机仿真面板
    组合电机可视化、仪表盘、状态信息
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # 标题
        title = QLabel("⚙ 电机仿真")
        title.setStyleSheet(f"""
            font-size: 15px; font-weight: bold; color: {Colors.BLUE};
            padding: 4px 0;
        """)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # 电机可视化
        self._motor_vis = MotorVisualWidget()
        self._motor_vis.setMinimumHeight(200)
        layout.addWidget(self._motor_vis, 2)

        # 仪表盘行
        gauge_layout = QHBoxLayout()
        gauge_layout.setSpacing(4)

        self._speed_gauge = GaugeWidget("速度", "rpm", -300, 300, (-10, 10))
        self._speed_gauge.setFixedSize(150, 150)
        gauge_layout.addWidget(self._speed_gauge)

        self._current_gauge = GaugeWidget("电流", "A", -5, 5, (-0.5, 0.5))
        self._current_gauge.setFixedSize(150, 150)
        gauge_layout.addWidget(self._current_gauge)

        layout.addLayout(gauge_layout, 1)

        # 状态信息区
        info_group = QGroupBox("电机状态")
        info_layout = QGridLayout(info_group)
        info_layout.setSpacing(4)

        self._info_labels = {}
        info_items = [
            ("speed_rpm", "输出转速", "rpm"),
            ("position_deg", "输出角度", "°"),
            ("current", "电枢电流", "A"),
            ("voltage", "控制电压", "V"),
            ("motor_torque", "电机转矩", "N·m"),
            ("encoder_count", "编码器计数", ""),
        ]

        for i, (key, label, unit) in enumerate(info_items):
            row, col = divmod(i, 2)
            lbl = QLabel(f"{label}:")
            lbl.setStyleSheet(f"color: {Colors.SUBTEXT0}; font-size: 11px;")
            val_lbl = QLabel(f"-- {unit}")
            val_lbl.setStyleSheet(f"""
                color: {Colors.GREEN}; font-weight: bold;
                font-family: 'Consolas', monospace; font-size: 12px;
            """)
            info_layout.addWidget(lbl, row, col * 2)
            info_layout.addWidget(val_lbl, row, col * 2 + 1)
            self._info_labels[key] = (val_lbl, unit)

        layout.addWidget(info_group, 1)

    def update_state(self, state: dict):
        """更新电机状态"""
        speed = state.get('speed_rpm', 0)
        current = state.get('current', 0)
        voltage = state.get('voltage', 0)
        position = state.get('position_deg', 0)

        # 更新可视化
        self._motor_vis.setState(speed, current, voltage, position)

        # 更新仪表盘
        self._speed_gauge.setValue(speed)
        self._current_gauge.setValue(current)

        # 更新信息标签
        for key, (label, unit) in self._info_labels.items():
            if key in state:
                val = state[key]
                if isinstance(val, float):
                    label.setText(f"{val:.4f} {unit}")
                else:
                    label.setText(f"{val} {unit}")

    def reset(self):
        self._motor_vis.reset()
        self._speed_gauge.setValue(0)
        self._current_gauge.setValue(0)
        for key, (label, unit) in self._info_labels.items():
            label.setText(f"-- {unit}")