"""
PID控制器模块
支持位置环、速度环、角度环及串级PID控制
"""

import time
import numpy as np
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from PySide6.QtCore import QObject, Signal


class ControlMode(Enum):
    """控制模式枚举"""
    POSITION = "position"       # 位置环
    SPEED = "speed"             # 速度环
    ANGLE = "angle"             # 角度环
    CASCADE = "cascade"         # 串级控制


@dataclass
class PIDParams:
    """PID参数数据类"""
    kp: float = 1.0
    ki: float = 0.0
    kd: float = 0.0
    setpoint: float = 0.0
    output_min: float = -100.0
    output_max: float = 100.0
    integral_max: float = 50.0
    deadband: float = 0.0
    filter_coeff: float = 0.1   # 微分滤波系数 (0~1)

    def to_dict(self) -> Dict[str, float]:
        return {
            'kp': self.kp, 'ki': self.ki, 'kd': self.kd,
            'setpoint': self.setpoint,
            'output_min': self.output_min, 'output_max': self.output_max,
            'integral_max': self.integral_max,
            'deadband': self.deadband,
            'filter_coeff': self.filter_coeff,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, float]) -> 'PIDParams':
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


class PIDController(QObject):
    """
    单环PID控制器
    支持增量式和位置式PID，带抗积分饱和、微分滤波、死区
    """
    output_updated = Signal(float)  # 输出更新信号
    params_changed = Signal(dict)   # 参数变化信号

    def __init__(self, params: Optional[PIDParams] = None, parent=None):
        super().__init__(parent)
        self.params = params or PIDParams()
        self._integral = 0.0
        self._prev_error = 0.0
        self._prev_output = 0.0
        self._prev_measurement = 0.0
        self._filtered_derivative = 0.0
        self._last_time: Optional[float] = None
        self._history = {
            'time': [],
            'setpoint': [],
            'measurement': [],
            'output': [],
            'error': [],
            'p_term': [],
            'i_term': [],
            'd_term': [],
        }
        self._max_history = 2000

    def reset(self):
        """重置控制器状态"""
        self._integral = 0.0
        self._prev_error = 0.0
        self._prev_output = 0.0
        self._prev_measurement = 0.0
        self._filtered_derivative = 0.0
        self._last_time = None
        for key in self._history:
            self._history[key].clear()

    def update(self, measurement: float, dt: Optional[float] = None) -> float:
        """
        执行一次PID计算
        Args:
            measurement: 当前测量值
            dt: 时间步长(秒)，None则自动计算
        Returns:
            PID输出值
        """
        now = time.perf_counter()
        if dt is None:
            if self._last_time is None:
                dt = 0.01
            else:
                dt = now - self._last_time
                dt = max(dt, 0.001)  # 最小1ms
        self._last_time = now

        p = self.params
        error = p.setpoint - measurement

        # 死区处理
        if abs(error) < p.deadband:
            error = 0.0

        # 比例项
        p_term = p.kp * error

        # 积分项（带抗积分饱和）
        self._integral += error * dt
        self._integral = np.clip(self._integral, -p.integral_max, p.integral_max)
        i_term = p.ki * self._integral

        # 微分项（带滤波，基于测量值微分避免阶跃）
        raw_derivative = -(measurement - self._prev_measurement) / dt if dt > 0 else 0.0
        alpha = p.filter_coeff
        self._filtered_derivative = alpha * raw_derivative + (1 - alpha) * self._filtered_derivative
        d_term = p.kd * self._filtered_derivative

        # 计算输出
        output = p_term + i_term + d_term

        # 输出限幅
        output = np.clip(output, p.output_min, p.output_max)

        # 抗积分饱和：当输出饱和时回退积分
        if output >= p.output_max or output <= p.output_min:
            self._integral -= error * dt

        # 保存历史
        self._record_history(now, p.setpoint, measurement, output, error, p_term, i_term, d_term)

        # 更新状态
        self._prev_error = error
        self._prev_output = output
        self._prev_measurement = measurement

        self.output_updated.emit(output)
        return output

    def _record_history(self, t, sp, mv, out, err, p, i, d):
        h = self._history
        h['time'].append(t)
        h['setpoint'].append(sp)
        h['measurement'].append(mv)
        h['output'].append(out)
        h['error'].append(err)
        h['p_term'].append(p)
        h['i_term'].append(i)
        h['d_term'].append(d)
        # 限制历史长度
        if len(h['time']) > self._max_history:
            for key in h:
                h[key] = h[key][-self._max_history:]

    def set_params(self, **kwargs):
        """动态更新PID参数"""
        for k, v in kwargs.items():
            if hasattr(self.params, k):
                setattr(self.params, k, v)
        self.params_changed.emit(self.params.to_dict())

    def get_history(self) -> Dict[str, list]:
        return self._history.copy()

    def get_latest_state(self) -> Dict[str, float]:
        h = self._history
        if not h['time']:
            return {}
        return {
            'time': h['time'][-1],
            'setpoint': h['setpoint'][-1],
            'measurement': h['measurement'][-1],
            'output': h['output'][-1],
            'error': h['error'][-1],
            'p_term': h['p_term'][-1],
            'i_term': h['i_term'][-1],
            'd_term': h['d_term'][-1],
        }


class CascadePIDController(QObject):
    """
    串级PID控制器
    外环输出作为内环的设定值
    """
    output_updated = Signal(float)
    params_changed = Signal(str, dict)  # (loop_name, params_dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.outer_loop = PIDController(PIDParams(kp=1.0, ki=0.1, kd=0.01), self)
        self.inner_loop = PIDController(PIDParams(kp=2.0, ki=0.5, kd=0.0), self)
        self._enabled = True

    def reset(self):
        self.outer_loop.reset()
        self.inner_loop.reset()

    def update(self, outer_measurement: float, inner_measurement: float,
               dt: Optional[float] = None) -> float:
        """
        串级PID更新
        Args:
            outer_measurement: 外环测量值（如位置）
            inner_measurement: 内环测量值（如速度）
            dt: 时间步长
        Returns:
            最终输出值
        """
        # 外环计算，输出作为内环设定值
        outer_output = self.outer_loop.update(outer_measurement, dt)
        self.inner_loop.params.setpoint = outer_output

        # 内环计算
        inner_output = self.inner_loop.update(inner_measurement, dt)

        self.output_updated.emit(inner_output)
        return inner_output

    def set_outer_params(self, **kwargs):
        for k, v in kwargs.items():
            if hasattr(self.outer_loop.params, k):
                setattr(self.outer_loop.params, k, v)
        self.params_changed.emit('outer', self.outer_loop.params.to_dict())

    def set_inner_params(self, **kwargs):
        for k, v in kwargs.items():
            if hasattr(self.inner_loop.params, k):
                setattr(self.inner_loop.params, k, v)
        self.params_changed.emit('inner', self.inner_loop.params.to_dict())