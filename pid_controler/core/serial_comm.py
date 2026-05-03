"""
串口通信模块
负责上位机与MCU之间的双向数据传输
支持串口自动扫描、数据校验、协议编解码
"""

import time
import struct
import logging
import threading
from enum import IntEnum
from typing import Optional, Callable, Dict, List, Any
from collections import deque

import serial
import serial.tools.list_ports
from PySide6.QtCore import QObject, Signal, QThread, QTimer

logger = logging.getLogger(__name__)


class CmdType(IntEnum):
    """命令类型"""
    SET_PID_PARAMS = 0x01       # 设置PID参数
    SET_TARGET = 0x02           # 设置目标值
    SET_MODE = 0x03             # 设置控制模式
    START_STOP = 0x04           # 启停控制
    QUERY_STATUS = 0x05         # 查询状态
    RESPONSE = 0x80             # 响应
    DATA_REPORT = 0x81          # 数据上报
    ERROR = 0xFF                # 错误


class ProtocolCodec:
    """
    通信协议编解码器
    协议格式: [帧头(2B)] [长度(1B)] [命令(1B)] [数据(NB)] [校验(1B)] [帧尾(2B)]
    帧头: 0xAA 0x55
    帧尾: 0x55 0xAA
    校验: XOR校验
    """
    HEADER = b'\xAA\x55'
    TAIL = b'\x55\xAA'
    MIN_FRAME_LEN = 8  # 最小帧长度

    @staticmethod
    def encode(cmd: int, data: bytes = b'') -> bytes:
        """编码一帧数据"""
        length = len(data) + 4  # cmd + data + checksum + padding
        frame = ProtocolCodec.HEADER
        frame += bytes([length & 0xFF, cmd & 0xFF])
        frame += data
        # 计算XOR校验
        checksum = length ^ cmd
        for b in data:
            checksum ^= b
        frame += bytes([checksum & 0xFF])
        frame += ProtocolCodec.TAIL
        return frame

    @staticmethod
    def encode_pid_params(kp: float, ki: float, kd: float, loop_id: int = 0) -> bytes:
        """编码PID参数数据"""
        data = struct.pack('<Bfff', loop_id, kp, ki, kd)
        return ProtocolCodec.encode(CmdType.SET_PID_PARAMS, data)

    @staticmethod
    def encode_target(target: float) -> bytes:
        """编码目标值"""
        data = struct.pack('<f', target)
        return ProtocolCodec.encode(CmdType.SET_TARGET, data)

    @staticmethod
    def encode_mode(mode: int) -> bytes:
        """编码控制模式"""
        data = struct.pack('<B', mode)
        return ProtocolCodec.encode(CmdType.SET_MODE, data)

    @staticmethod
    def encode_start_stop(start: bool) -> bytes:
        """编码启停命令"""
        data = struct.pack('<B', 1 if start else 0)
        return ProtocolCodec.encode(CmdType.START_STOP, data)

    @staticmethod
    def decode(buffer: bytes) -> Optional[Dict[str, Any]]:
        """
        从缓冲区解码一帧数据
        Returns:
            解码结果字典或None
        """
        # 查找帧头
        idx = buffer.find(ProtocolCodec.HEADER)
        if idx < 0:
            return None
        buffer = buffer[idx:]

        if len(buffer) < ProtocolCodec.MIN_FRAME_LEN:
            return None

        length = buffer[2]
        frame_len = length + 4  # header(2) + length(1) + cmd(1) + data(length-4) + checksum(1) + tail(2)

        if len(buffer) < frame_len:
            return None

        # 检查帧尾
        if buffer[frame_len - 2:frame_len] != ProtocolCodec.TAIL:
            return None

        cmd = buffer[3]
        data = buffer[4:frame_len - 3]
        checksum = buffer[frame_len - 3]

        # 验证校验
        calc_checksum = length ^ cmd
        for b in data:
            calc_checksum ^= b
        if (calc_checksum & 0xFF) != checksum:
            logger.warning(f"校验失败: 期望 {calc_checksum & 0xFF:#x}, 收到 {checksum:#x}")
            return None

        result = {
            'cmd': cmd,
            'data': data,
            'frame_len': frame_len,
        }

        # 解析数据
        if cmd == CmdType.DATA_REPORT and len(data) >= 16:
            result['measurement'] = struct.unpack('<f', data[0:4])[0]
            result['output'] = struct.unpack('<f', data[4:8])[0]
            result['setpoint'] = struct.unpack('<f', data[8:12])[0]
            result['feedback'] = struct.unpack('<f', data[12:16])[0]

        return result


class SerialReaderThread(QThread):
    """串口读取线程"""
    data_received = Signal(bytes)
    error_occurred = Signal(str)
    connection_lost = Signal()

    def __init__(self, port: serial.Serial, parent=None):
        super().__init__(parent)
        self.port = port
        self._running = True

    def run(self):
        buffer = b''
        while self._running:
            try:
                if self.port and self.port.is_open:
                    if self.port.in_waiting > 0:
                        data = self.port.read(self.port.in_waiting)
                        buffer += data
                        # 尝试解码
                        while len(buffer) >= ProtocolCodec.MIN_FRAME_LEN:
                            result = ProtocolCodec.decode(buffer)
                            if result is None:
                                # 跳过无效字节
                                idx = buffer.find(ProtocolCodec.HEADER, 1)
                                if idx > 0:
                                    buffer = buffer[idx:]
                                else:
                                    if len(buffer) > 256:
                                        buffer = buffer[-128:]
                                    break
                            else:
                                frame = buffer[:result['frame_len']]
                                buffer = buffer[result['frame_len']:]
                                self.data_received.emit(frame)
                    else:
                        self.msleep(1)
                else:
                    self.connection_lost.emit()
                    break
            except serial.SerialException as e:
                self.error_occurred.emit(f"串口错误: {e}")
                self.connection_lost.emit()
                break
            except Exception as e:
                self.error_occurred.emit(f"读取错误: {e}")
                self.msleep(10)

    def stop(self):
        self._running = False
        self.wait(2000)


class SerialManager(QObject):
    """
    串口管理器
    管理串口连接、数据收发、协议处理
    """
    connection_changed = Signal(bool)       # 连接状态变化
    data_received = Signal(dict)            # 解码后的数据
    raw_data_received = Signal(bytes)       # 原始数据
    error_occurred = Signal(str)            # 错误信息
    port_list_changed = Signal(list)        # 端口列表变化
    log_message = Signal(str)               # 日志消息

    def __init__(self, parent=None):
        super().__init__(parent)
        self._port: Optional[serial.Serial] = None
        self._reader_thread: Optional[SerialReaderThread] = None
        self._connected = False
        self._port_name = ""
        self._baudrate = 115200
        self._rx_buffer = deque(maxlen=10000)
        self._tx_count = 0
        self._rx_count = 0
        self._last_rx_time = 0

        # 端口扫描定时器
        self._scan_timer = QTimer(self)
        self._scan_timer.timeout.connect(self._scan_ports)
        self._scan_timer.start(2000)  # 每2秒扫描一次

    @property
    def is_connected(self) -> bool:
        return self._connected and self._port is not None and self._port.is_open

    @property
    def port_name(self) -> str:
        return self._port_name

    @property
    def baudrate(self) -> int:
        return self._baudrate

    @property
    def tx_count(self) -> int:
        return self._tx_count

    @property
    def rx_count(self) -> int:
        return self._rx_count

    def get_available_ports(self) -> List[Dict[str, str]]:
        """获取可用串口列表"""
        ports = []
        for port in serial.tools.list_ports.comports():
            ports.append({
                'port': port.device,
                'description': port.description,
                'hwid': port.hwid,
            })
        return ports

    def _scan_ports(self):
        """扫描可用端口"""
        ports = self.get_available_ports()
        port_names = [p['port'] for p in ports]
        self.port_list_changed.emit(port_names)

    def connect(self, port_name: str, baudrate: int = 115200) -> bool:
        """
        连接串口
        Args:
            port_name: 串口名称
            baudrate: 波特率
        """
        if self.is_connected:
            self.disconnect()

        try:
            self._port = serial.Serial(
                port=port_name,
                baudrate=baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.1,
            )
            self._port_name = port_name
            self._baudrate = baudrate

            # 启动读取线程
            self._reader_thread = SerialReaderThread(self._port, self)
            self._reader_thread.data_received.connect(self._on_raw_data)
            self._reader_thread.error_occurred.connect(self._on_error)
            self._reader_thread.connection_lost.connect(self._on_connection_lost)
            self._reader_thread.start()

            self._connected = True
            self.connection_changed.emit(True)
            self.log_message.emit(f"已连接到 {port_name} @ {baudrate}")
            logger.info(f"Connected to {port_name} @ {baudrate}")
            return True

        except serial.SerialException as e:
            msg = f"无法连接 {port_name}: {e}"
            self.error_occurred.emit(msg)
            self.log_message.emit(msg)
            logger.error(msg)
            return False

    def disconnect(self):
        """断开串口连接"""
        if self._reader_thread:
            self._reader_thread.stop()
            self._reader_thread = None

        if self._port and self._port.is_open:
            try:
                self._port.close()
            except Exception:
                pass

        if self._connected:
            self._connected = False
            self.connection_changed.emit(False)
            self.log_message.emit(f"已断开 {self._port_name}")
            logger.info(f"Disconnected from {self._port_name}")

    def send(self, data: bytes) -> bool:
        """发送原始数据"""
        if not self.is_connected:
            self.error_occurred.emit("未连接串口")
            return False
        try:
            self._port.write(data)
            self._tx_count += len(data)
            return True
        except serial.SerialException as e:
            self.error_occurred.emit(f"发送失败: {e}")
            return False

    def send_pid_params(self, kp: float, ki: float, kd: float, loop_id: int = 0) -> bool:
        """发送PID参数"""
        data = ProtocolCodec.encode_pid_params(kp, ki, kd, loop_id)
        self.log_message.emit(f"发送PID参数: Kp={kp:.4f}, Ki={ki:.4f}, Kd={kd:.4f} (环路{loop_id})")
        return self.send(data)

    def send_target(self, target: float) -> bool:
        """发送目标值"""
        data = ProtocolCodec.encode_target(target)
        self.log_message.emit(f"发送目标值: {target:.2f}")
        return self.send(data)

    def send_mode(self, mode: int) -> bool:
        """发送控制模式"""
        data = ProtocolCodec.encode_mode(mode)
        self.log_message.emit(f"发送控制模式: {mode}")
        return self.send(data)

    def send_start_stop(self, start: bool) -> bool:
        """发送启停命令"""
        data = ProtocolCodec.encode_start_stop(start)
        self.log_message.emit(f"{'启动' if start else '停止'}控制")
        return self.send(data)

    def _on_raw_data(self, raw: bytes):
        """处理接收到的原始数据"""
        self._rx_count += len(raw)
        self._last_rx_time = time.time()
        self.raw_data_received.emit(raw)

        result = ProtocolCodec.decode(raw)
        if result:
            self.data_received.emit(result)

    def _on_error(self, msg: str):
        self.error_occurred.emit(msg)
        self.log_message.emit(f"[错误] {msg}")

    def _on_connection_lost(self):
        if self._connected:
            self._connected = False
            self.connection_changed.emit(False)
            self.log_message.emit("连接丢失")
            logger.warning("Connection lost")

    def get_statistics(self) -> Dict[str, Any]:
        """获取通信统计信息"""
        return {
            'connected': self.is_connected,
            'port': self._port_name,
            'baudrate': self._baudrate,
            'tx_count': self._tx_count,
            'rx_count': self._rx_count,
            'last_rx_time': self._last_rx_time,
        }

    def __del__(self):
        self.disconnect()