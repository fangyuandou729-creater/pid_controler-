#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
直流减速电机闭环控制上位机
主程序入口

功能特性:
- 手动/自动PID参数调节
- 串级PID、位置环、速度环、角度环控制
- 实时波形显示与图像保存
- 电机仿真动画
- Ziegler-Nichols / Cohen-Coon / PSO / 继电反馈自动调参
- 串口通信与MCU交互
- 日志记录与导出

技术栈: PySide6 + PyQtGraph + NumPy + SciPy + PySerial
"""

import sys
import os
import logging

# 确保项目根目录在Python路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QCoreApplication
from PySide6.QtGui import QFont

from ui.main_window import MainWindow
from ui.styles import MAIN_STYLESHEET


def setup_logging():
    """配置全局日志"""
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    os.makedirs(log_dir, exist_ok=True)

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler(
                os.path.join(log_dir, 'pid_controller.log'),
                encoding='utf-8'
            ),
            logging.StreamHandler(sys.stdout),
        ]
    )
    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("直流减速电机闭环控制上位机启动")
    logger.info("=" * 60)
    return logger


def main():
    """主函数"""
    # 创建应用
    app = QApplication(sys.argv)
    app.setApplicationName("DC Motor PID Controller")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("PID Control Lab")

    # 设置默认字体
    font = QFont("Microsoft YaHei UI", 10)
    font.setStyleStrategy(QFont.PreferAntialias)
    app.setFont(font)

    # 配置日志
    logger = setup_logging()

    # 应用样式
    app.setStyleSheet(MAIN_STYLESHEET)

    # 创建主窗口
    try:
        window = MainWindow()
        window.show()
        logger.info("主窗口显示成功")
    except Exception as e:
        logger.critical(f"主窗口创建失败: {e}", exc_info=True)
        sys.exit(1)

    # 运行事件循环
    exit_code = app.exec()
    logger.info(f"应用退出，退出码: {exit_code}")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()