# DC Motor PID Controller - 直流减速电机闭环控制上位机

## 功能特性

### 🎛 控制模式
- **速度环控制** - 电机转速闭环PID控制
- **位置环控制** - 电机位置闭环PID控制
- **角度环控制** - 电机角度闭环PID控制
- **串级控制** - 外环(位置) + 内环(速度)串级PID

### 🔧 PID参数调节
- **手动模式** - 通过旋钮/滑块实时调节 Kp、Ki、Kd
- **自动模式** - 支持多种自动调参算法:
  - Ziegler-Nichols 阶跃响应法
  - Cohen-Coon 整定法
  - 阶跃响应启发式法
  - 继电反馈法 (Åström-Hägglund)
  - 粒子群优化 (PSO) 算法

### 📊 实时数据可视化
- 设定值/测量值/PID输出 三曲线实时显示
- PID分量 (P/I/D) 波形
- 电流/电压波形
- 支持缩放、拖拽、自动缩放
- 波形截图保存 (PNG/JPG)
- 数据导出 (CSV)

### 🖥 电机仿真
- 直流减速电机物理模型仿真
- 转子旋转动画
- 速度/电流仪表盘
- 实时状态参数显示

### 📝 日志系统
- 带颜色的日志输出
- 日志级别过滤 (DEBUG/INFO/WARNING/ERROR)
- 搜索功能
- 日志文件导出

### 🔌 串口通信
- 串口自动扫描
- 自定义通信协议 (帧头/校验/帧尾)
- PID参数实时下发
- 控制指令发送

## 项目结构

```
pid_controler/
├── main.py                 # 主程序入口
├── requirements.txt        # 依赖包列表
├── README.md              # 项目说明
├── core/                   # 核心逻辑模块
│   ├── __init__.py
│   ├── pid_controller.py  # PID控制器 (单环+串级)
│   ├── motor_model.py     # 直流电机仿真模型
│   ├── auto_tuner.py      # 自动调参算法
│   └── serial_comm.py     # 串口通信管理
├── ui/                     # UI模块
│   ├── __init__.py
│   ├── styles.py          # 全局样式表 (Catppuccin Mocha主题)
│   ├── main_window.py     # 主窗口
│   ├── control_panel.py   # 控制面板
│   ├── waveform_display.py # 波形显示
│   ├── log_window.py      # 日志窗口
│   └── motor_sim_widget.py # 电机仿真动画
├── assets/                 # 资源文件
└── logs/                   # 日志文件 (自动生成)
```

## 安装与运行

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 运行程序
```bash
python main.py
```

### 快捷键
| 快捷键 | 功能 |
|--------|------|
| F5 | 启动控制 |
| F6 | 停止控制 |
| Ctrl+R | 重置系统 |
| Ctrl+S | 导出数据 |
| Alt+F4 | 退出 |

## 技术栈

| 组件 | 技术 |
|------|------|
| UI框架 | PySide6 (Qt6) |
| 实时波形 | PyQtGraph |
| 数值计算 | NumPy + SciPy |
| 串口通信 | PySerial |
| 静态图像 | Matplotlib |
| 主题 | Catppuccin Mocha |

## 通信协议

```
[帧头 0xAA55] [长度 1B] [命令 1B] [数据 NB] [XOR校验 1B] [帧尾 0x55AA]
```

| 命令 | 说明 |
|------|------|
| 0x01 | 设置PID参数 |
| 0x02 | 设置目标值 |
| 0x03 | 设置控制模式 |
| 0x04 | 启停控制 |
| 0x05 | 查询状态 |
| 0x81 | 数据上报 |

## 电机模型

基于直流电机状态空间方程:
- **电气方程**: `V = Ra·I + La·dI/dt + Ke·ω`
- **机械方程**: `J·dω/dt = Kt·I - B·ω - T_load - T_fric`
- **减速器**: `ω_out = ω_in / N`, `T_out = T_in · N · η`