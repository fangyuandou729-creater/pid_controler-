"""
核心逻辑模块包
包含PID控制器、电机模型、自动调参、串口通信等核心功能
"""

from .pid_controller import PIDController, CascadePIDController
from .motor_model import DCMotorModel
from .auto_tuner import AutoTuner, TuningMethod
from .serial_comm import SerialManager, ProtocolCodec

__all__ = [
    'PIDController',
    'CascadePIDController',
    'DCMotorModel',
    'AutoTuner',
    'TuningMethod',
    'SerialManager',
    'ProtocolCodec',
]