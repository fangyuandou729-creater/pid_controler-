"""
自动PID调参模块
支持Ziegler-Nichols法、继电反馈法、粒子群优化(PSO)算法
"""

import time
import numpy as np
from enum import Enum
from typing import Callable, Optional, Tuple, Dict, List
from dataclasses import dataclass
from scipy import signal as sig
from PySide6.QtCore import QObject, Signal, QThread


class TuningMethod(Enum):
    """调参方法枚举"""
    ZIEGLER_NICHOLS = "ziegler_nichols"     # 经典Z-N法
    RELAY_FEEDBACK = "relay_feedback"       # 继电反馈法
    PSO = "pso"                             # 粒子群优化
    COHEN_COON = "cohen_coon"               # Cohen-Coon法
    SIMPLE = "simple"                       # 简单步响应法


@dataclass
class TuningResult:
    """调参结果"""
    kp: float
    ki: float
    kd: float
    method: str
    performance: Dict[str, float] = None
    iterations: int = 0
    elapsed_time: float = 0.0

    def __str__(self):
        return (f"[{self.method}] Kp={self.kp:.4f}, Ki={self.ki:.4f}, Kd={self.kd:.4f} "
                f"(迭代{self.iterations}次, 耗时{self.elapsed_time:.2f}s)")


class AutoTuner(QObject):
    """
    自动PID调参器
    根据系统响应曲线自动计算最优PID参数
    """
    tuning_started = Signal()
    tuning_progress = Signal(int, str)  # (progress_percent, message)
    tuning_completed = Signal(object)   # TuningResult
    tuning_error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_tuning = False
        self._cancel_flag = False

    @property
    def is_tuning(self) -> bool:
        return self._is_tuning

    def cancel(self):
        self._cancel_flag = True

    def analyze_step_response(self, time_data: np.ndarray, 
                               response_data: np.ndarray,
                               setpoint: float) -> Dict[str, float]:
        """
        分析阶跃响应特性
        Returns:
            包含上升时间、超调量、调节时间、稳态误差等指标
        """
        if len(time_data) < 10:
            return {}

        t = np.array(time_data) - time_data[0]
        y = np.array(response_data)

        # 归一化
        y_ss = y[-1] if abs(y[-1]) > 1e-6 else 1.0
        y_norm = y / y_ss if abs(y_ss) > 1e-6 else y

        # 上升时间 (10% ~ 90%)
        try:
            idx_10 = np.where(y_norm >= 0.1)[0][0]
            idx_90 = np.where(y_norm >= 0.9)[0][0]
            rise_time = t[idx_90] - t[idx_10]
        except IndexError:
            rise_time = t[-1]

        # 超调量
        peak_idx = np.argmax(y)
        if y[peak_idx] > setpoint and abs(setpoint) > 1e-6:
            overshoot = (y[peak_idx] - setpoint) / abs(setpoint) * 100
        else:
            overshoot = 0.0

        # 稳态误差
        steady_state_val = np.mean(y[-max(10, len(y)//10):])
        ss_error = abs(setpoint - steady_state_val)

        # 调节时间 (±2%)
        settling_time = t[-1]
        band = abs(setpoint) * 0.02 if abs(setpoint) > 1e-6 else 0.1
        for i in range(len(y) - 1, -1, -1):
            if abs(y[i] - setpoint) > band:
                settling_time = t[min(i + 1, len(t) - 1)]
                break

        return {
            'rise_time': rise_time,
            'overshoot': overshoot,
            'settling_time': settling_time,
            'steady_state_error': ss_error,
            'peak_value': y[peak_idx],
            'steady_state_value': steady_state_val,
            'gain_margin': 0.0,
            'phase_margin': 0.0,
        }

    def ziegler_nichols(self, time_data: np.ndarray,
                        response_data: np.ndarray,
                        setpoint: float) -> TuningResult:
        """
        Ziegler-Nichols阶跃响应法
        基于S形响应曲线的切线法
        """
        t = np.array(time_data) - time_data[0]
        y = np.array(response_data)

        if len(t) < 20:
            raise ValueError("数据点不足，无法进行Z-N调参")

        y_final = np.mean(y[-max(10, len(y)//10):])
        if abs(y_final) < 1e-6:
            raise ValueError("系统无响应，输出趋近于零")

        # 估算过程增益 K
        step_size = abs(setpoint) if abs(setpoint) > 1e-6 else 1.0
        K = y_final / step_size

        # 找到最大斜率点作为切线
        dy = np.gradient(y, t)
        max_slope_idx = np.argmax(np.abs(dy))
        max_slope = dy[max_slope_idx]

        if abs(max_slope) < 1e-10:
            raise ValueError("响应曲线过于平缓")

        # 切线法求延迟时间L和时间常数T
        # 切线方程: y_tangent = max_slope * (t - t_inflect) + y_inflect
        y_at_inflect = y[max_slope_idx]
        t_at_inflect = t[max_slope_idx]

        # L: 切线与零线交点
        if abs(max_slope) > 1e-10:
            L = t_at_inflect - y_at_inflect / max_slope
            L = max(L, 0.001)
        else:
            L = 0.01

        # T: 切线与稳态值交点
        if abs(max_slope) > 1e-10:
            T = t_at_inflect + (y_final - y_at_inflect) / max_slope - L
            T = max(T, 0.001)
        else:
            T = 0.1

        # Z-N整定公式 (PID)
        if abs(K) > 1e-10 and abs(L) > 1e-10:
            kp = 1.2 * T / (K * L)
            ki = kp / (2.0 * L)
            kd = kp * 0.5 * L
        else:
            kp, ki, kd = 1.0, 0.1, 0.01

        # 限幅保护
        kp = np.clip(kp, 0.001, 1000)
        ki = np.clip(ki, 0.0, 500)
        kd = np.clip(kd, 0.0, 100)

        performance = self.analyze_step_response(time_data, response_data, setpoint)

        return TuningResult(
            kp=kp, ki=ki, kd=kd,
            method="Ziegler-Nichols",
            performance=performance,
            iterations=1,
        )

    def cohen_coon(self, time_data: np.ndarray,
                   response_data: np.ndarray,
                   setpoint: float) -> TuningResult:
        """
        Cohen-Coon整定法
        基于一阶加纯滞后模型
        """
        t = np.array(time_data) - time_data[0]
        y = np.array(response_data)

        y_final = np.mean(y[-max(10, len(y)//10):])
        step_size = abs(setpoint) if abs(setpoint) > 1e-6 else 1.0
        K = y_final / step_size

        dy = np.gradient(y, t)
        max_slope_idx = np.argmax(np.abs(dy))
        max_slope = dy[max_slope_idx]

        y_at_inflect = y[max_slope_idx]
        t_at_inflect = t[max_slope_idx]

        if abs(max_slope) < 1e-10:
            raise ValueError("响应曲线过于平缓")

        L = max(t_at_inflect - y_at_inflect / max_slope, 0.001)
        T = max(t_at_inflect + (y_final - y_at_inflect) / max_slope - L, 0.001)

        r = L / T  # L/T比值

        if abs(K) > 1e-10:
            kp = (1.0 / K) * (T / L) * (1.0 + r / 3.0) / (1.0 + 0.35 * r)
            ki = kp / (L * (1.0 + r * (1.0 - r / 3.0) / (1.0 + r / 3.0)))
            kd = kp * L * (1.0 - r / 3.0) / (4.0 * (1.0 + r / 3.0))
        else:
            kp, ki, kd = 1.0, 0.1, 0.01

        kp = np.clip(kp, 0.001, 1000)
        ki = np.clip(ki, 0.0, 500)
        kd = np.clip(kd, 0.0, 100)

        performance = self.analyze_step_response(time_data, response_data, setpoint)

        return TuningResult(
            kp=kp, ki=ki, kd=kd,
            method="Cohen-Coon",
            performance=performance,
            iterations=1,
        )

    def simple_step_response(self, time_data: np.ndarray,
                             response_data: np.ndarray,
                             setpoint: float) -> TuningResult:
        """
        简单阶跃响应法
        根据超调量和调节时间直接给出保守的PID参数
        """
        performance = self.analyze_step_response(time_data, response_data, setpoint)

        overshoot = performance.get('overshoot', 0)
        settling = performance.get('settling_time', 1.0)
        ss_error = performance.get('steady_state_error', 0)

        # 启发式参数
        if overshoot > 30:
            kp = 0.5
            kd = 0.2
        elif overshoot > 10:
            kp = 1.0
            kd = 0.1
        else:
            kp = 2.0
            kd = 0.05

        if ss_error > abs(setpoint) * 0.05:
            ki = 0.5
        else:
            ki = 0.1

        return TuningResult(
            kp=kp, ki=ki, kd=kd,
            method="Simple Step Response",
            performance=performance,
            iterations=1,
        )

    def relay_feedback_test(self, process_step_fn: Callable, 
                            measurement_fn: Callable,
                            amplitude: float = 5.0,
                            num_cycles: int = 5,
                            dt: float = 0.01) -> TuningResult:
        """
        继电反馈法 (Åström-Hägglund)
        通过继电反馈产生等幅振荡，测量临界增益和临界周期
        Args:
            process_step_fn: 执行一步的函数，接受(voltage, dt)参数
            measurement_fn: 获取测量值的函数
            amplitude: 继电幅度
            num_cycles: 需要测量的振荡周期数
            dt: 仿真步长
        """
        self._is_tuning = True
        self._cancel_flag = False

        start_time = time.time()
        measurements = []
        crossings = []  # 过零点时间
        last_sign = 0
        cycle_count = 0
        relay_state = amplitude

        max_steps = int(num_cycles * 10.0 / dt)  # 最大运行时间

        try:
            for step in range(max_steps):
                if self._cancel_flag:
                    break

                measurement = measurement_fn()
                measurements.append(measurement)

                # 继电控制
                relay_state = -amplitude if measurement > 0 else amplitude
                process_step_fn(relay_state, dt)

                # 检测过零点
                current_sign = 1 if measurement >= 0 else -1
                if last_sign != 0 and current_sign != last_sign:
                    crossings.append(step * dt)
                    if len(crossings) >= 2:
                        cycle_count = len(crossings) // 2

                last_sign = current_sign

                progress = min(int(cycle_count / num_cycles * 100), 99)
                self.tuning_progress.emit(progress, f"继电反馈测试中... 周期 {cycle_count}/{num_cycles}")

                if cycle_count >= num_cycles:
                    break

            if len(crossings) < 2:
                raise ValueError("未能检测到足够的振荡周期")

            # 计算临界周期 Tu
            periods = []
            for i in range(1, len(crossings) - 1, 2):
                periods.append(crossings[i + 1] - crossings[i] if i + 1 < len(crossings) else crossings[i] - crossings[i - 1])
            if not periods:
                periods = [crossings[-1] - crossings[0]]

            Tu = np.mean(periods) * 2  # 全周期
            Tu = max(Tu, 0.01)

            # 计算临界增益 Ku
            y_arr = np.array(measurements[-int(Tu / dt * 2):])
            a = (np.max(y_arr) - np.min(y_arr)) / 2.0  # 振幅
            Ku = 4.0 * amplitude / (np.pi * a) if a > 1e-6 else 1.0

            # Z-N临界增益法
            kp = 0.6 * Ku
            ki = 2.0 * kp / Tu
            kd = kp * Tu / 8.0

            kp = np.clip(kp, 0.001, 1000)
            ki = np.clip(ki, 0.0, 500)
            kd = np.clip(kd, 0.0, 100)

            result = TuningResult(
                kp=kp, ki=ki, kd=kd,
                method="Relay Feedback (Åström-Hägglund)",
                performance={'Ku': Ku, 'Tu': Tu, 'amplitude': a},
                iterations=cycle_count,
                elapsed_time=time.time() - start_time,
            )

            self.tuning_completed.emit(result)
            return result

        except Exception as e:
            self.tuning_error.emit(str(e))
            raise
        finally:
            self._is_tuning = False

    def pso_optimize(self, fitness_fn: Callable[[float, float, float], float],
                     bounds: Optional[Tuple[List[float], List[float]]] = None,
                     n_particles: int = 30,
                     n_iterations: int = 50,
                     w: float = 0.7,
                     c1: float = 1.5,
                     c2: float = 1.5) -> TuningResult:
        """
        粒子群优化PID参数
        Args:
            fitness_fn: 适应度函数，接受(kp, ki, kd)返回成本值（越小越好）
            bounds: 参数边界 ([kp_min, ki_min, kd_min], [kp_max, ki_max, kd_max])
            n_particles: 粒子数量
            n_iterations: 迭代次数
            w: 惯性权重
            c1: 个体学习因子
            c2: 社会学习因子
        """
        self._is_tuning = True
        self._cancel_flag = False
        start_time = time.time()

        if bounds is None:
            bounds = ([0.001, 0.0, 0.0], [100.0, 50.0, 20.0])

        lb = np.array(bounds[0])
        ub = np.array(bounds[1])
        dim = 3

        # 初始化粒子
        positions = np.random.uniform(lb, ub, (n_particles, dim))
        velocities = np.random.uniform(-(ub - lb) * 0.1, (ub - lb) * 0.1, (n_particles, dim))

        # 初始化个体最优和全局最优
        p_best_pos = positions.copy()
        p_best_cost = np.full(n_particles, np.inf)
        g_best_pos = positions[0].copy()
        g_best_cost = np.inf

        try:
            for iteration in range(n_iterations):
                if self._cancel_flag:
                    break

                # 自适应惯性权重
                w_iter = w * (1 - iteration / n_iterations) + 0.4 * (iteration / n_iterations)

                for i in range(n_particles):
                    cost = fitness_fn(positions[i, 0], positions[i, 1], positions[i, 2])

                    if cost < p_best_cost[i]:
                        p_best_cost[i] = cost
                        p_best_pos[i] = positions[i].copy()

                    if cost < g_best_cost:
                        g_best_cost = cost
                        g_best_pos = positions[i].copy()

                # 更新速度和位置
                r1 = np.random.random((n_particles, dim))
                r2 = np.random.random((n_particles, dim))

                velocities = (w_iter * velocities +
                              c1 * r1 * (p_best_pos - positions) +
                              c2 * r2 * (g_best_pos - positions))

                positions = positions + velocities
                positions = np.clip(positions, lb, ub)

                progress = int((iteration + 1) / n_iterations * 100)
                self.tuning_progress.emit(
                    progress,
                    f"PSO迭代 {iteration+1}/{n_iterations}, 最优成本={g_best_cost:.4f}"
                )

            result = TuningResult(
                kp=g_best_pos[0],
                ki=g_best_pos[1],
                kd=g_best_pos[2],
                method="PSO优化",
                performance={'best_cost': g_best_cost},
                iterations=n_iterations,
                elapsed_time=time.time() - start_time,
            )

            self.tuning_completed.emit(result)
            return result

        except Exception as e:
            self.tuning_error.emit(str(e))
            raise
        finally:
            self._is_tuning = False

    def auto_tune(self, method: TuningMethod,
                  time_data: Optional[np.ndarray] = None,
                  response_data: Optional[np.ndarray] = None,
                  setpoint: float = 1.0,
                  **kwargs) -> TuningResult:
        """
        统一调参接口
        """
        if method == TuningMethod.ZIEGLER_NICHOLS:
            return self.ziegler_nichols(time_data, response_data, setpoint)
        elif method == TuningMethod.COHEN_COON:
            return self.cohen_coon(time_data, response_data, setpoint)
        elif method == TuningMethod.SIMPLE:
            return self.simple_step_response(time_data, response_data, setpoint)
        elif method == TuningMethod.RELAY_FEEDBACK:
            return self.relay_feedback_test(**kwargs)
        elif method == TuningMethod.PSO:
            return self.pso_optimize(**kwargs)
        else:
            raise ValueError(f"不支持的调参方法: {method}")


class PSOWorker(QThread):
    """PSO优化线程"""
    progress = Signal(int, str)
    completed = Signal(object)
    error = Signal(str)

    def __init__(self, fitness_fn, bounds=None, n_particles=30, n_iterations=50, parent=None):
        super().__init__(parent)
        self.fitness_fn = fitness_fn
        self.bounds = bounds
        self.n_particles = n_particles
        self.n_iterations = n_iterations
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            tuner = AutoTuner()
            tuner.tuning_progress.connect(self.progress)
            tuner.tuning_completed.connect(self.completed)
            tuner.tuning_error.connect(self.error)

            # 传递取消标志
            result = tuner.pso_optimize(
                self.fitness_fn,
                bounds=self.bounds,
                n_particles=self.n_particles,
                n_iterations=self.n_iterations,
            )
            self.completed.emit(result)
        except Exception as e:
            self.error.emit(str(e))