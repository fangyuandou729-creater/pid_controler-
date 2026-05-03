"""
日志窗口组件
提供带颜色的日志输出、日志级别过滤、日志保存功能
"""

import os
import logging
from datetime import datetime
from collections import deque
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
    QCheckBox, QComboBox, QLabel, QFileDialog, QLineEdit, QGroupBox
)
from PySide6.QtCore import Qt, Signal, Slot, QObject
from PySide6.QtGui import QTextCursor, QColor, QTextCharFormat, QFont

from .styles import Colors


class LogSignalHandler(QObject, logging.Handler):
    """将Python logging重定向到Qt信号"""
    log_record = Signal(str, str, str)  # (level, message, formatted)

    def __init__(self, parent=None):
        super().__init__(parent)
        logging.Handler.__init__(self)

    def emit(self, record):
        msg = self.format(record)
        self.log_record.emit(record.levelname, record.getMessage(), msg)


class LogWindow(QWidget):
    """
    日志窗口
    支持多级别日志显示、颜色标记、过滤、搜索、导出
    """
    LEVEL_COLORS = {
        'DEBUG': Colors.SUBTEXT0,
        'INFO': Colors.GREEN,
        'WARNING': Colors.YELLOW,
        'ERROR': Colors.RED,
        'CRITICAL': Colors.PINK,
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._max_lines = 5000
        self._auto_scroll = True
        self._setup_ui()
        self._setup_logging()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # 工具栏
        toolbar = QHBoxLayout()

        self._level_combo = QComboBox()
        self._level_combo.addItems(["全部", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self._level_combo.currentTextChanged.connect(self._on_filter_changed)
        toolbar.addWidget(QLabel("级别:"))
        toolbar.addWidget(self._level_combo)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("🔍 搜索日志...")
        self._search_input.setFixedWidth(200)
        self._search_input.returnPressed.connect(self._on_search)
        toolbar.addWidget(self._search_input)

        self._auto_scroll_check = QCheckBox("自动滚动")
        self._auto_scroll_check.setChecked(True)
        self._auto_scroll_check.toggled.connect(lambda v: setattr(self, '_auto_scroll', v))
        toolbar.addWidget(self._auto_scroll_check)

        toolbar.addStretch()

        self._clear_btn = QPushButton("🗑 清除")
        self._clear_btn.clicked.connect(self._clear_log)
        toolbar.addWidget(self._clear_btn)

        self._save_btn = QPushButton("💾 保存日志")
        self._save_btn.clicked.connect(self._save_log)
        toolbar.addWidget(self._save_btn)

        layout.addLayout(toolbar)

        # 日志显示区
        self._text_edit = QTextEdit()
        self._text_edit.setReadOnly(True)
        self._text_edit.setFont(QFont("Cascadia Code", 11))
        self._text_edit.setMinimumHeight(100)
        layout.addWidget(self._text_edit, 1)

        # 状态栏
        status_layout = QHBoxLayout()
        self._line_count_label = QLabel("行数: 0")
        self._line_count_label.setStyleSheet(f"color: {Colors.SUBTEXT0}; font-size: 11px;")
        status_layout.addWidget(self._line_count_label)

        self._last_msg_label = QLabel("")
        self._last_msg_label.setStyleSheet(f"color: {Colors.SUBTEXT0}; font-size: 11px;")
        status_layout.addStretch()
        status_layout.addWidget(self._last_msg_label)
        layout.addLayout(status_layout)

    def _setup_logging(self):
        """设置Python logging集成"""
        self._handler = LogSignalHandler(self)
        self._handler.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%H:%M:%S'
        ))
        self._handler.log_record.connect(self._on_log_record)
        logging.getLogger().addHandler(self._handler)
        logging.getLogger().setLevel(logging.DEBUG)

    def _on_log_record(self, level: str, message: str, formatted: str):
        self.append_log(message, level)

    @Slot(str, str)
    def append_log(self, message: str, level: str = "INFO"):
        """添加日志条目"""
        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        color = self.LEVEL_COLORS.get(level, Colors.TEXT)

        # HTML格式化
        html = (
            f'<span style="color:{Colors.SUBTEXT0};">[{timestamp}]</span> '
            f'<span style="color:{color}; font-weight:bold;">[{level}]</span> '
            f'<span style="color:{color};">{message}</span>'
        )

        self._text_edit.append(html)
        self._line_count_label.setText(f"行数: {self._text_edit.document().blockCount()}")
        self._last_msg_label.setText(message[:80])

        # 限制行数
        if self._text_edit.document().blockCount() > self._max_lines:
            cursor = self._text_edit.textCursor()
            cursor.movePosition(QTextCursor.Start)
            cursor.movePosition(QTextCursor.Down, QTextCursor.KeepAnchor,
                              self._text_edit.document().blockCount() - self._max_lines)
            cursor.removeSelectedText()

        # 自动滚动
        if self._auto_scroll:
            scrollbar = self._text_edit.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

    def _on_filter_changed(self, level: str):
        """日志级别过滤"""
        level_map = {
            "全部": logging.DEBUG,
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
        }
        min_level = level_map.get(level, logging.DEBUG)
        self._handler.setLevel(min_level)

    def _on_search(self):
        """搜索日志"""
        text = self._search_input.text()
        if not text:
            return
        # 简单高亮搜索
        cursor = self._text_edit.textCursor()
        cursor.movePosition(QTextCursor.Start)
        self._text_edit.setTextCursor(cursor)
        self._text_edit.find(text)

    def _clear_log(self):
        """清除日志"""
        self._text_edit.clear()
        self._line_count_label.setText("行数: 0")
        self._last_msg_label.setText("")

    def _save_log(self):
        """保存日志到文件"""
        default_name = f"pid_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        path, _ = QFileDialog.getSaveFileName(
            self, "保存日志", default_name,
            "日志文件 (*.log);;文本文件 (*.txt);;所有文件 (*.*)"
        )
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self._text_edit.toPlainText())
            self.append_log(f"日志已保存到: {path}", "INFO")

    def log_info(self, msg: str):
        self.append_log(msg, "INFO")

    def log_warning(self, msg: str):
        self.append_log(msg, "WARNING")

    def log_error(self, msg: str):
        self.append_log(msg, "ERROR")

    def log_debug(self, msg: str):
        self.append_log(msg, "DEBUG")

    def log_pid_update(self, kp: float, ki: float, kd: float):
        self.append_log(
            f"PID参数更新: Kp={kp:.4f}, Ki={ki:.4f}, Kd={kd:.4f}",
            "INFO"
        )

    def log_performance(self, metrics: dict):
        """记录性能指标"""
        lines = []
        if 'rise_time' in metrics:
            lines.append(f"上升时间: {metrics['rise_time']:.3f}s")
        if 'overshoot' in metrics:
            lines.append(f"超调量: {metrics['overshoot']:.1f}%")
        if 'settling_time' in metrics:
            lines.append(f"调节时间: {metrics['settling_time']:.3f}s")
        if 'steady_state_error' in metrics:
            lines.append(f"稳态误差: {metrics['steady_state_error']:.4f}")
        if lines:
            self.append_log("性能指标: " + " | ".join(lines), "INFO")