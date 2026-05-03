"""
直流减速电机仿真模型
基于直流电机传递函数的差分方程模型
包含电气特性、机械特性、减速器特性
"""

import numpy as np
from dataclasses import dataclass
from typing import Tuple, Optional
from PySide6.QtCore import QObject, Signal


@dataclass
class MotorParams:
    """直流电机物理参数"""
    resistance: float = 2.0         # 电枢电阻 Ra (Ω)
    inductance: float = 0.005       # 电枢电感 La (H)
    torque_const: float = 0.05      # 转矩常数 Kt (N·m/A)
    back_emf_const: float = 0.05    # 反电动势常数 Ke (V·s/rad)
    inertia: float = 0.001          # 转动惯量 J (kg·m²)
    friction: float = 0.0001        # 粘性摩擦系数 B (N·m·s/rad)
    gear_ratio: float = 30.0        # 减速比 N
    gear_efficiency: float = 0.85   # 减速器效率 η
    encoder_ppr: float = 1000.0     # 编码器每转脉冲数
    max_voltage: float = 12.0       # 最大电压 (V)
    rated_speed: float = 300.0      # 额定转速 (rpm, 减速后)
    dead_zone_voltage: float = 0.5  # 死区电压 (V)
    coulomb_friction: float = 0.001 # 库仑摩擦 (N·m)

    def to_dict(self):
        return {k: v for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, d):
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


class DCMotorModel(QObject):
    """
    直流减速电机仿真模型
    使用状态空间方程进行仿真:
    电气方程: V = Ra*I + La*dI/dt + Ke*ω
    机械方程: J*dω/dt = Kt*I - B*ω - T_load - T_fric
    减速器: ω_out = ω_in / N, T_out = T_in * N * η
    """
    state_updated = Signal(dict)  # 状态更新信号

    def __init__(self, params: Optional[MotorParams] = None, parent=None):
        super().__init__(parent)
        self.params = params or MotorParams()
        # 状态变量
        self._current = 0.0         # 电枢电流 (A)
        self._omega_motor = 0.0     # 电机角速度 (rad/s)
        self._theta_motor = 0.0     # 电机角度 (rad)
        self._speed_rpm = 0.0       # 输出转速 (rpm)
        self._position_deg = 0.0    # 输出角度 (deg)
        self._load_torque = 0.0     # 负载转矩 (N·m)
        self._dt = 0.001            # 仿真步长 (s)
        self._gear_backlash = 0.0   # 齿轮回差 (deg)
        self._noise_std = 0.01      # 测量噪声标准差
        self._encoder_count = 0

    def reset(self):
        """重置电机状态"""
        self._current = 0.0
        self._omega_motor = 0.0
        self._theta_motor = 0.0
        self._speed_rpm = 0.0
        self._position_deg = 0.0
        self._encoder_count = 0

    def set_load_torque(self, torque: float):
        """设置负载转矩"""
        self._load_torque = torque

    def update(self, voltage: float, dt: Optional[float] = None) -> dict:
        """
        电机模型更新
        Args:
            voltage: 控制电压 (V), 范围 [-max_voltage, max_voltage]
            dt: 仿真步长 (s)
        Returns:
            电机状态字典
        """
        if dt is not None:
            self._dt = dt
        dt = self._dt
        p = self.params

        # 电压限幅
        voltage = np.clip(voltage, -p.max_voltage, p.max_voltage)

        # 死区处理
        if abs(voltage) < p.dead_zone_voltage:
            voltage = 0.0

        # ===== 电气方程: La * dI/dt = V - Ra*I - Ke*ω =====
        back_emf = p.back_emf_const * self._omega_motor
        di_dt = (voltage - p.resistance * self._current - back_emf) / p.inductance
        self._current += di_dt * dt

        # ===== 机械方程: J * dω/dt = Kt*I - B*ω - T_load - T_coulomb*sign(ω) =====
        motor_torque = p.torque_const * self._current
        friction_torque = p.friction * self._omega_motor
        # 库仑摩擦
        if abs(self._omega_motor) > 0.01:
            coulomb = p.coulomb_friction * np.sign(self._omega_motor)
        else:
            coulomb = p.coulomb_friction * np.sign(motor_torque) if abs(motor_torque) > p.coulomb_friction else 0.0

        # 折算到电机轴的负载转矩
        load_reflected = self._load_torque / (p.gear_ratio * p.gear_efficiency)

        net_torque = motor_torque - friction_torque - coulomb - load_reflected
        dw_dt = net_torque / p.inertia
        self._omega_motor += dw_dt * dt

        # 电机角度积分
        self._theta_motor += self._omega_motor * dt

        # ===== 减速器输出 =====
        self._speed_rpm = (self._omega_motor / p.gear_ratio) * 60.0 / (2.0 * np.pi)
        self._position_deg = np.degrees(self._theta_motor / p.gear_ratio)

        # 编码器模拟
        counts_per_rad = p.encoder_ppr / (2.0 * np.pi)
        self._encoder_count = int(self._theta_motor * counts_per_rad / p.gear_ratio)

        # 测量噪声
        noisy_speed = self._speed_rpm + np.random.normal(0, self._noise_std * abs(self._speed_rpm + 0.1))
        noisy_position = self._position_deg + np.random.normal(0, self._noise_std)

        state = {
            'current': self._current,
            'voltage': voltage,
            'omega_motor': self._omega_motor,
            'theta_motor': self._theta_motor,
            'speed_rpm': noisy_speed,
            'position_deg': noisy_position,
            'actual_speed_rpm': self._speed_rpm,
            'actual_position_deg': self._position_deg,
            'motor_torque': motor_torque,
            'load_torque': self._load_torque,
            'encoder_count': self._encoder_count,
        }

        self.state_updated.emit(state)
        return state

    def get_state(self) -> dict:
        return {
            'current': self._current,
            'omega_motor': self._omega_motor,
            'theta_motor': self._theta_motor,
            'speed_rpm': self._speed_rpm,
            'position_deg': self._position_deg,
            'encoder_count': self._encoder_count,
        }

    def set_params(self, **kwargs):
        """动态更新电机参数"""
        for k, v in kwargs.items():
            if hasattr(self.params, k):
                setattr(self.params, k, v)