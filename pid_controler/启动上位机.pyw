#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
双击即可运行的启动脚本（无控制台窗口）
模仿者小队 - 直流减速电机闭环控制上位机
"""

import sys
import os

# 切换到脚本所在目录
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# 确保项目根目录在Python路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import main
main()