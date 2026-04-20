#!/usr/bin/env python3
"""Noin IDE"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import cast
import re
import tempfile
import json

from PySide6.QtCore import QProcess, QRegularExpression, QTimer, QRect, QSize, Qt
from PySide6.QtGui import (
    QAction,
    QColor,
    QFont,
    QFontDatabase,
    QCloseEvent,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QPainter,
    QKeyEvent,
    QPaintEvent,
    QResizeEvent,
    QKeySequence,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QCompleter,
    QFileDialog,
    QHBoxLayout,
    QLineEdit,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from serial import Serial, SerialException
from serial.tools import list_ports
from noinc import CompileError, Compiler, compile_file


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT_DIR / "program.noin"
BUILD_SCRIPT = ROOT_DIR / "build.ps1"
GENERATED_C = ROOT_DIR / "src/program.generated.c"
SETTINGS_FILE = ROOT_DIR / ".noin_ide_settings.json"


THEMES = {
    "Aero": {
        "window": "#F4F7FB",
        "base": "#FFFFFF",
        "alt": "#EAF0F8",
        "text": "#111827",
        "button": "#E5ECF5",
        "highlight": "#0284C7",
        "editor_border": "#D1D9E6",
        "editor_selection": "#BAE6FD",
        "button_border": "#B8C4D8",
        "button_bg": "#F8FBFF",
        "button_hover": "#E7F3FF",
        "combo_border": "#B8C4D8",
        "menu_bg": "#EAF0F8",
        "syntax_keyword": "#1D4ED8",
        "syntax_builtin": "#C2410C",
        "syntax_literal": "#0F766E",
        "syntax_comment": "#6B7280",
        "syntax_number": "#7C3AED",
        "syntax_string": "#047857",
        "gutter_bg": "#E5E7EB",
        "gutter_fg": "#64748B",
        "active_line_bg": "#DBEAFE",
        "error_line_bg": "#FECACA",
        "tab_bg": "#EAF0F8",
        "tab_active_bg": "#FFFFFF",
    },
    "Sunset": {
        "window": "#FFF7ED",
        "base": "#FFFBF5",
        "alt": "#FDEDDC",
        "text": "#3A2E23",
        "button": "#F9DFC8",
        "highlight": "#EA580C",
        "editor_border": "#E8CBAE",
        "editor_selection": "#FED7AA",
        "button_border": "#D9B79A",
        "button_bg": "#FFF0E2",
        "button_hover": "#FFE2CC",
        "combo_border": "#D9B79A",
        "menu_bg": "#FDEDDC",
        "syntax_keyword": "#9A3412",
        "syntax_builtin": "#7C2D12",
        "syntax_literal": "#065F46",
        "syntax_comment": "#7C6F64",
        "syntax_number": "#A21CAF",
        "syntax_string": "#0F766E",
        "gutter_bg": "#F4E2CF",
        "gutter_fg": "#7C6F64",
        "active_line_bg": "#FFEBCF",
        "error_line_bg": "#FECACA",
        "tab_bg": "#F7E8D8",
        "tab_active_bg": "#FFFBF5",
    },
    "Forest": {
        "window": "#EEF6EF",
        "base": "#FAFFFA",
        "alt": "#DFEDE1",
        "text": "#1D2B1F",
        "button": "#DCEBDE",
        "highlight": "#15803D",
        "editor_border": "#BFD8C2",
        "editor_selection": "#BBF7D0",
        "button_border": "#A7C7AB",
        "button_bg": "#F2FBF3",
        "button_hover": "#DDF3E1",
        "combo_border": "#A7C7AB",
        "menu_bg": "#DFEDE1",
        "syntax_keyword": "#166534",
        "syntax_builtin": "#0F766E",
        "syntax_literal": "#1D4ED8",
        "syntax_comment": "#6B7280",
        "syntax_number": "#7C3AED",
        "syntax_string": "#BE123C",
        "gutter_bg": "#DCEBDE",
        "gutter_fg": "#5F6F61",
        "active_line_bg": "#DCFCE7",
        "error_line_bg": "#FECACA",
        "tab_bg": "#DFEDE1",
        "tab_active_bg": "#FAFFFA",
    },
    "Midnight": {
        "window": "#111827",
        "base": "#0F172A",
        "alt": "#1E293B",
        "text": "#E5E7EB",
        "button": "#1F2937",
        "highlight": "#38BDF8",
        "editor_border": "#334155",
        "editor_selection": "#1D4ED8",
        "button_border": "#475569",
        "button_bg": "#1F2937",
        "button_hover": "#334155",
        "combo_border": "#475569",
        "menu_bg": "#1E293B",
        "syntax_keyword": "#93C5FD",
        "syntax_builtin": "#F59E0B",
        "syntax_literal": "#34D399",
        "syntax_comment": "#94A3B8",
        "syntax_number": "#C4B5FD",
        "syntax_string": "#86EFAC",
        "gutter_bg": "#1F2937",
        "gutter_fg": "#9CA3AF",
        "active_line_bg": "#1E293B",
        "error_line_bg": "#7F1D1D",
        "tab_bg": "#1E293B",
        "tab_active_bg": "#0F172A",
    },
}


class NoinHighlighter(QSyntaxHighlighter):
    def __init__(self, document: QTextDocument) -> None:
        super().__init__(document)
        self.rules: list[tuple[QRegularExpression, QTextCharFormat]] = []
        self._build_rules("Aero")

    def _build_rules(self, theme_name: str) -> None:
        palette = THEMES[theme_name]
        self.rules.clear()

        keyword_fmt = QTextCharFormat()
        keyword_fmt.setForeground(QColor(palette["syntax_keyword"]))
        keyword_fmt.setFontWeight(QFont.Weight.Bold)

        builtin_fmt = QTextCharFormat()
        builtin_fmt.setForeground(QColor(palette["syntax_builtin"]))

        literal_fmt = QTextCharFormat()
        literal_fmt.setForeground(QColor(palette["syntax_literal"]))
        literal_fmt.setFontWeight(QFont.Weight.Bold)

        comment_fmt = QTextCharFormat()
        comment_fmt.setForeground(QColor(palette["syntax_comment"]))
        comment_fmt.setFontItalic(True)

        number_fmt = QTextCharFormat()
        number_fmt.setForeground(QColor(palette["syntax_number"]))

        string_fmt = QTextCharFormat()
        string_fmt.setForeground(QColor(palette["syntax_string"]))

        keywords = [
            "function",
            "end",
            "if",
            "then",
            "else",
            "while",
            "do",
            "repeat",
            "local",
            "and",
            "or",
            "not",
            "void",
            "return",
            "static",
            "int",
            "int32_t",
            "run",
        ]
        builtins = [
            "pin",
            "write",
            "high",
            "low",
            "wait",
            "read",
            "analog",
            "pwm",
            "map",
            "setup",
            "loop",
            "print",
            "serial",
        ]
        literals = ["input", "output", "true", "false"]

        for word in keywords:
            self.rules.append((QRegularExpression(rf"\b{word}\b"), keyword_fmt))
        for word in builtins:
            self.rules.append((QRegularExpression(rf"\b{word}\b"), builtin_fmt))
        for word in literals:
            self.rules.append((QRegularExpression(rf"\b{word}\b"), literal_fmt))

        self.rules.append((QRegularExpression(r"\b\d+\b"), number_fmt))
        self.rules.append((QRegularExpression(r'"[^"\n]*"'), string_fmt))
        self.rules.append((QRegularExpression(r"'[^'\n]*'"), string_fmt))
        self.rules.append((QRegularExpression(r"--[^\n]*"), comment_fmt))
        self.rules.append((QRegularExpression(r"#[^\n]*"), comment_fmt))

    def set_theme(self, theme_name: str) -> None:
        self._build_rules(theme_name)
        self.rehighlight()

    def highlightBlock(self, text: str) -> None:
        for pattern, text_format in self.rules:
            iterator = pattern.globalMatch(text)
            while iterator.hasNext():
                match = iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), text_format)


class CHighlighter(QSyntaxHighlighter):
    def __init__(self, document: QTextDocument) -> None:
        super().__init__(document)
        self.rules: list[tuple[QRegularExpression, QTextCharFormat]] = []
        self._build_rules("Aero")

    def _build_rules(self, theme_name: str) -> None:
        palette = THEMES[theme_name]
        self.rules.clear()

        kw = QTextCharFormat()
        kw.setForeground(QColor(palette["syntax_keyword"]))
        kw.setFontWeight(QFont.Weight.Bold)

        fn = QTextCharFormat()
        fn.setForeground(QColor(palette["syntax_builtin"]))

        num = QTextCharFormat()
        num.setForeground(QColor(palette["syntax_number"]))

        com = QTextCharFormat()
        com.setForeground(QColor(palette["syntax_comment"]))
        com.setFontItalic(True)

        st = QTextCharFormat()
        st.setForeground(QColor(palette["syntax_string"]))

        keywords = [
            "void",
            "int",
            "int32_t",
            "uint8_t",
            "if",
            "else",
            "while",
            "for",
            "return",
            "static",
            "const",
            "volatile",
            "include",
        ]
        for word in keywords:
            self.rules.append((QRegularExpression(rf"\b{word}\b"), kw))

        self.rules.append((QRegularExpression(r"\b[A-Za-z_][A-Za-z0-9_]*\s*(?=\()"), fn))
        self.rules.append((QRegularExpression(r"\b\d+\b"), num))
        self.rules.append((QRegularExpression(r'"[^"\n]*"'), st))
        self.rules.append((QRegularExpression(r"'[^'\n]*'"), st))
        self.rules.append((QRegularExpression(r"//[^\n]*"), com))
        self.rules.append((QRegularExpression(r"/\*.*\*/"), com))

    def set_theme(self, theme_name: str) -> None:
        self._build_rules(theme_name)
        self.rehighlight()

    def highlightBlock(self, text: str) -> None:
        for pattern, text_format in self.rules:
            iterator = pattern.globalMatch(text)
            while iterator.hasNext():
                match = iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), text_format)


class LineNumberArea(QWidget):
    def __init__(self, editor: "CodeEditor") -> None:
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self) -> QSize:
        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event: QPaintEvent) -> None:
        self.editor.line_number_area_paint_event(event)


class CodeEditor(QPlainTextEdit):
    def __init__(self) -> None:
        super().__init__()
        self.line_number_area = LineNumberArea(self)
        self.error_line: int | None = None
        self.completer: QCompleter | None = None
        self.gutter_bg = QColor("#E5E7EB")
        self.gutter_fg = QColor("#64748B")
        self.active_line_bg = QColor("#DBEAFE")
        self.error_line_bg = QColor("#FECACA")

        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_special_lines)
        self.update_line_number_area_width(0)
        self.highlight_special_lines()

    def line_number_area_width(self) -> int:
        digits = len(str(max(1, self.blockCount())))
        return 12 + self.fontMetrics().horizontalAdvance("9") * digits

    def update_line_number_area_width(self, _new_block_count: int) -> None:
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect: QRect, dy: int) -> None:
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())

        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height()))

    def line_number_area_paint_event(self, event: QPaintEvent) -> None:
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), self.gutter_bg)

        block = self.firstVisibleBlock()
        block_number = block.blockNumber() + 1
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number)
                painter.setPen(self.gutter_fg)
                painter.drawText(0, top, self.line_number_area.width() - 6, self.fontMetrics().height(), Qt.AlignmentFlag.AlignRight, number)

            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_number += 1

    def set_error_line(self, line_no: int | None) -> None:
        self.error_line = line_no
        self.highlight_special_lines()

    def highlight_special_lines(self) -> None:
        selections: list[QTextEdit.ExtraSelection] = []

        current = QTextEdit.ExtraSelection()
        current.format.setBackground(self.active_line_bg)
        current.format.setProperty(QTextCharFormat.Property.FullWidthSelection, True)
        current.cursor = self.textCursor()
        current.cursor.clearSelection()
        selections.append(current)

        if self.error_line is not None and self.error_line > 0:
            block = self.document().findBlockByNumber(self.error_line - 1)
            if block.isValid():
                err_cursor = QTextCursor(block)
                err = QTextEdit.ExtraSelection()
                err.format.setBackground(self.error_line_bg)
                err.format.setProperty(QTextCharFormat.Property.FullWidthSelection, True)
                err.cursor = err_cursor
                err.cursor.clearSelection()
                selections.append(err)

        self.setExtraSelections(selections)

    def set_completions(self, words: list[str]) -> None:
        self.completer = QCompleter(words, self)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.setWidget(self)
        self.completer.activated.connect(self.insert_completion)

    def apply_visual_theme(self, theme_data: dict[str, str]) -> None:
        self.gutter_bg = QColor(theme_data["gutter_bg"])
        self.gutter_fg = QColor(theme_data["gutter_fg"])
        self.active_line_bg = QColor(theme_data["active_line_bg"])
        self.error_line_bg = QColor(theme_data["error_line_bg"])
        self.highlight_special_lines()
        self.line_number_area.update()

    def insert_completion(self, completion: str) -> None:
        cursor = self.textCursor()
        cursor.beginEditBlock()
        cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        cursor.removeSelectedText()
        cursor.insertText(completion)
        cursor.endEditBlock()
        self.setTextCursor(cursor)

    def text_under_cursor(self) -> str:
        cursor = self.textCursor()
        cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        return cursor.selectedText()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        popup = self.completer.popup() if self.completer is not None else None
        if popup is not None and popup.isVisible():
            if event.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return, Qt.Key.Key_Escape, Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
                event.ignore()
                return

        is_shortcut = event.modifiers() == Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_Space
        is_show_all_shortcut = event.modifiers() == Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_F7
        if is_show_all_shortcut:
            self.show_all_completions()
            return

        if not is_shortcut:
            super().keyPressEvent(event)

        if self.completer is None:
            return

        completion_prefix = self.text_under_cursor()
        if not is_shortcut and len(completion_prefix) < 2:
            popup = self.completer.popup()
            if popup is not None:
                popup.hide()
            return

        if completion_prefix != self.completer.completionPrefix():
            self.completer.setCompletionPrefix(completion_prefix)
            popup = self.completer.popup()
            if popup is not None:
                popup.setCurrentIndex(self.completer.completionModel().index(0, 0))

        cr = self.cursorRect()
        popup = self.completer.popup()
        if popup is not None:
            cr.setWidth(popup.sizeHintForColumn(0) + popup.verticalScrollBar().sizeHint().width())
        self.completer.complete(cr)

    def show_all_completions(self) -> None:
        if self.completer is None:
            return

        self.completer.setCompletionPrefix("")
        popup = self.completer.popup()
        if popup is not None:
            popup.setCurrentIndex(self.completer.completionModel().index(0, 0))

        cr = self.cursorRect()
        if popup is not None:
            cr.setWidth(max(360, popup.sizeHintForColumn(0) + popup.verticalScrollBar().sizeHint().width()))
        self.completer.complete(cr)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Noin IDE")
        self.resize(1200, 760)

        self.current_file = DEFAULT_SOURCE
        self.settings = self._load_settings()
        self.serial_port: Serial | None = None
        self.reopen_monitor_after_process = False
        self.monitor_start_pending = False
        self.last_build_output = ""
        self.lint_timer = QTimer(self)
        self.lint_timer.setSingleShot(True)
        self.lint_timer.setInterval(500)
        self.lint_timer.timeout.connect(self.run_live_lint)
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._on_process_output)
        self.process.finished.connect(self._on_process_finished)
        self.monitor_timer = QTimer(self)
        self.monitor_timer.setInterval(80)
        self.monitor_timer.timeout.connect(self._poll_serial)

        self._setup_ui()
        self._setup_menu()
        self._load_file(self.current_file)
        self.refresh_ports()
        self._restore_settings()

    @staticmethod
    def _default_settings() -> dict[str, str]:
        return {
            "theme": "Aero",
            "board_profile": "nano_avr",
            "bootloader": "optiboot",
            "upload_baud": "115200",
            "monitor_baud": "115200",
            "programmer": "arduino",
            "avrdude_verbose": "1",
            "avrdude_chip_erase": "0",
            "avrdude_no_verify": "0",
            "avrdude_extra": "",
            "monitor_decode": "UTF-8",
            "auto_reopen_monitor": "1",
            "last_port": "",
        }

    def _load_settings(self) -> dict[str, str]:
        defaults = self._default_settings()
        if not SETTINGS_FILE.exists():
            return defaults

        try:
            raw = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return defaults

        if not isinstance(raw, dict):
            return defaults

        raw_dict = cast(dict[str, object], raw)
        merged = defaults.copy()
        for key in defaults:
            value = raw_dict.get(key)
            if isinstance(value, str):
                merged[key] = value
        return merged

    def _save_settings(self) -> None:
        data = {
            "theme": self.theme_combo.currentText(),
            "board_profile": str(self.board_combo.currentData()),
            "bootloader": str(self.bootloader_combo.currentData()),
            "upload_baud": self.baud_combo.currentText(),
            "monitor_baud": self.monitor_baud_combo.currentText(),
            "programmer": str(self.programmer_combo.currentData()),
            "avrdude_verbose": self.avrdude_verbose_combo.currentText(),
            "avrdude_chip_erase": "1" if self.avrdude_chip_erase_checkbox.isChecked() else "0",
            "avrdude_no_verify": "1" if self.avrdude_no_verify_checkbox.isChecked() else "0",
            "avrdude_extra": self.avrdude_extra_edit.text(),
            "monitor_decode": self.monitor_decode_combo.currentText(),
            "auto_reopen_monitor": "1" if self.auto_reopen_monitor_checkbox.isChecked() else "0",
            "last_port": self._selected_port(),
        }

        try:
            SETTINGS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError:
            return

    def _restore_settings(self) -> None:
        desired_theme = self.settings.get("theme", "Aero")
        if desired_theme in THEMES:
            self.theme_combo.setCurrentText(desired_theme)

        desired_board = self.settings.get("board_profile", "nano_avr")
        for i in range(self.board_combo.count()):
            if self.board_combo.itemData(i) == desired_board:
                self.board_combo.setCurrentIndex(i)
                break

        desired_bootloader = self.settings.get("bootloader", "optiboot")
        for i in range(self.bootloader_combo.count()):
            if self.bootloader_combo.itemData(i) == desired_bootloader:
                self.bootloader_combo.setCurrentIndex(i)
                break

        desired_programmer = self.settings.get("programmer", "arduino")
        for i in range(self.programmer_combo.count()):
            if self.programmer_combo.itemData(i) == desired_programmer:
                self.programmer_combo.setCurrentIndex(i)
                break

        self.baud_combo.setCurrentText(self.settings.get("upload_baud", "115200"))
        self.monitor_baud_combo.setCurrentText(self.settings.get("monitor_baud", "115200"))
        self.avrdude_verbose_combo.setCurrentText(self.settings.get("avrdude_verbose", "1"))
        self.avrdude_chip_erase_checkbox.setChecked(self.settings.get("avrdude_chip_erase", "0") == "1")
        self.avrdude_no_verify_checkbox.setChecked(self.settings.get("avrdude_no_verify", "0") == "1")
        self.avrdude_extra_edit.setText(self.settings.get("avrdude_extra", ""))
        self.monitor_decode_combo.setCurrentText(self.settings.get("monitor_decode", "UTF-8"))
        self.auto_reopen_monitor_checkbox.setChecked(self.settings.get("auto_reopen_monitor", "1") == "1")
        self._sync_upload_controls_for_board()
        self._sync_baud_for_bootloader()

        desired_port = self.settings.get("last_port", "")
        if desired_port:
            for i in range(self.port_combo.count()):
                if self.port_combo.itemData(i) == desired_port:
                    self.port_combo.setCurrentIndex(i)
                    break

    def _on_selection_changed(self, _value: object = None) -> None:
        self._save_settings()

    def _setup_ui(self) -> None:
        wrapper = QWidget()
        self.setCentralWidget(wrapper)

        outer = QVBoxLayout(wrapper)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(8)

        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(180)
        refresh_btn = QPushButton("Refresh Ports")
        refresh_btn.clicked.connect(self.refresh_ports)

        self.board_combo = QComboBox()
        self.board_combo.addItem("Arduino Nano (AVR)", "nano_avr")
        self.board_combo.addItem("Arduino Uno (AVR)", "uno_avr")
        self.board_combo.addItem("Pro Micro (AVR)", "promicro_avr")
        self.board_combo.addItem("ESP32 DevKit", "esp32_devkit")
        self.board_combo.currentIndexChanged.connect(self._on_selection_changed)
        self.board_combo.currentIndexChanged.connect(self._sync_upload_controls_for_board)

        self.bootloader_combo = QComboBox()
        self.bootloader_combo.addItem("Optiboot (New) - 115200", "optiboot")
        self.bootloader_combo.addItem("Old Nano - 57600", "old")
        self.bootloader_combo.addItem("Custom", "custom")
        self.bootloader_combo.currentIndexChanged.connect(self._sync_baud_for_bootloader)
        self.bootloader_combo.currentIndexChanged.connect(self._on_selection_changed)

        self.baud_combo = QComboBox()
        self.baud_combo.addItems(["115200", "57600", "9600", "19200", "38400"])
        self.baud_combo.setCurrentText("115200")
        self.baud_combo.currentTextChanged.connect(self._on_selection_changed)

        self.programmer_combo = QComboBox()
        self.programmer_combo.addItem("arduino (recommended)", "arduino")
        self.programmer_combo.addItem("stk500v1 (legacy)", "stk500v1")
        self.programmer_combo.addItem("wiring", "wiring")
        self.programmer_combo.currentIndexChanged.connect(self._on_selection_changed)

        self.avrdude_verbose_combo = QComboBox()
        self.avrdude_verbose_combo.addItems(["0", "1", "2", "3"])
        self.avrdude_verbose_combo.setCurrentText("1")
        self.avrdude_verbose_combo.currentTextChanged.connect(self._on_selection_changed)

        self.avrdude_chip_erase_checkbox = QCheckBox("Chip erase")
        self.avrdude_chip_erase_checkbox.toggled.connect(self._on_selection_changed)
        self.avrdude_no_verify_checkbox = QCheckBox("Skip verify")
        self.avrdude_no_verify_checkbox.toggled.connect(self._on_selection_changed)
        self.avrdude_extra_edit = QLineEdit()
        self.avrdude_extra_edit.setPlaceholderText("AVRDUDE extra args (e.g. -F -i 10)")
        self.avrdude_extra_edit.textChanged.connect(self._on_selection_changed)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(list(THEMES.keys()))
        self.theme_combo.currentTextChanged.connect(self.apply_theme)
        self.theme_combo.currentTextChanged.connect(self._on_selection_changed)

        compile_btn = QPushButton("Build")
        compile_btn.clicked.connect(self.build_project)
        format_btn = QPushButton("Format")
        format_btn.clicked.connect(self.format_code)
        upload_btn = QPushButton("Upload")
        upload_btn.clicked.connect(self.upload_project)
        c_refresh_btn = QPushButton("Refresh C Preview")
        c_refresh_btn.clicked.connect(self.refresh_generated_c_view)

        top_bar.addWidget(QLabel("Port:"))
        top_bar.addWidget(self.port_combo)
        top_bar.addWidget(refresh_btn)
        top_bar.addSpacing(8)
        top_bar.addWidget(QLabel("Board:"))
        top_bar.addWidget(self.board_combo)
        top_bar.addSpacing(8)
        top_bar.addWidget(QLabel("Bootloader:"))
        top_bar.addWidget(self.bootloader_combo)
        top_bar.addSpacing(10)
        top_bar.addWidget(QLabel("Baud:"))
        top_bar.addWidget(self.baud_combo)
        top_bar.addSpacing(8)
        top_bar.addWidget(QLabel("Programmer:"))
        top_bar.addWidget(self.programmer_combo)
        top_bar.addSpacing(8)
        top_bar.addWidget(QLabel("V:"))
        top_bar.addWidget(self.avrdude_verbose_combo)
        top_bar.addWidget(self.avrdude_chip_erase_checkbox)
        top_bar.addWidget(self.avrdude_no_verify_checkbox)
        top_bar.addWidget(self.avrdude_extra_edit)
        top_bar.addSpacing(8)
        top_bar.addWidget(QLabel("Theme:"))
        top_bar.addWidget(self.theme_combo)
        self.lint_label = QLabel("Lint: ready")
        self.lint_label.setStyleSheet("color:#64748B;")
        top_bar.addWidget(self.lint_label)
        top_bar.addStretch(1)
        top_bar.addWidget(format_btn)
        top_bar.addWidget(compile_btn)
        top_bar.addWidget(upload_btn)
        top_bar.addWidget(c_refresh_btn)

        self.editor = CodeEditor()
        self.editor.setPlaceholderText("Write your Noin code here...")
        self.editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.editor.textChanged.connect(self._on_text_changed)
        self.editor.textChanged.connect(self._schedule_live_lint)
        self.editor.document().setDocumentMargin(10)

        fixed = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        fixed.setPointSize(11)
        self.editor.setFont(fixed)
        self.editor.set_completions([
            "function", "setup", "run", "loop", "if", "elseif", "then", "else", "end", "while", "do", "repeat",
            "local", "and", "or", "not", "pin", "write", "high", "low", "toggle", "wait", "read", "analog",
            "pwm", "map", "serial", "print", "input", "output", "true", "false",
            "function <name>()",
            "function setup()",
            "function run()",
            "if <condition> then",
            "elseif <condition> then",
            "else",
            "end",
            "while <condition> do",
            "repeat <count> do",
            "local <name> = <expr>",
            "serial(<baud>)",
            "print(<expr>)",
            "print(\"<text>\")",
            "pin(<pin>, output|input)",
            "write(<pin>, high|low)",
            "high(<pin>)",
            "low(<pin>)",
            "toggle(<pin>)",
            "wait(<ms>)",
            "read(<pin>)",
            "analog(<channel>)",
            "pwm(<pin>, <value_0_255>)",
            "map(<x>, <in_min>, <in_max>, <out_min>, <out_max>)",
        ])
        self.highlighter = NoinHighlighter(self.editor.document())

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(2500)
        self.log.setPlaceholderText("Build and upload logs appear here")
        self.log.setFont(fixed)
        self.log.setMinimumHeight(190)

        monitor_bar = QHBoxLayout()
        monitor_bar.setSpacing(8)
        self.monitor_toggle_btn = QPushButton("Start Monitor")
        self.monitor_toggle_btn.clicked.connect(self.toggle_monitor)
        monitor_clear_btn = QPushButton("Clear Monitor")
        monitor_clear_btn.clicked.connect(self.monitor_clear)
        self.monitor_input = QLineEdit()
        self.monitor_input.setPlaceholderText("Type a serial command and send it")
        self.monitor_baud_combo = QComboBox()
        self.monitor_baud_combo.setEditable(True)
        self.monitor_baud_combo.addItems(["115200", "57600", "9600", "19200", "38400", "74880"])
        self.monitor_baud_combo.setCurrentText("115200")
        self.monitor_baud_combo.currentTextChanged.connect(self._on_selection_changed)
        self.monitor_decode_combo = QComboBox()
        self.monitor_decode_combo.addItems(["UTF-8", "Latin-1", "HEX"])
        self.monitor_decode_combo.currentTextChanged.connect(self._on_selection_changed)
        self.auto_reopen_monitor_checkbox = QCheckBox("Reopen monitor after upload")
        self.auto_reopen_monitor_checkbox.setChecked(True)
        self.auto_reopen_monitor_checkbox.toggled.connect(self._on_selection_changed)
        monitor_send_btn = QPushButton("Send")
        monitor_send_btn.clicked.connect(self.monitor_send)

        monitor_bar.addWidget(QLabel("Serial Monitor"))
        monitor_bar.addWidget(self.monitor_toggle_btn)
        monitor_bar.addWidget(monitor_clear_btn)
        monitor_bar.addWidget(QLabel("Monitor Baud:"))
        monitor_bar.addWidget(self.monitor_baud_combo)
        monitor_bar.addWidget(QLabel("Decode:"))
        monitor_bar.addWidget(self.monitor_decode_combo)
        monitor_bar.addWidget(self.auto_reopen_monitor_checkbox)
        monitor_bar.addWidget(self.monitor_input, 1)
        monitor_bar.addWidget(monitor_send_btn)

        self.monitor_output = QPlainTextEdit()
        self.monitor_output.setReadOnly(True)
        self.monitor_output.setMaximumBlockCount(3000)
        self.monitor_output.setPlaceholderText("Serial data from the device appears here")
        self.monitor_output.setFont(fixed)
        self.monitor_output.setMinimumHeight(170)

        self.c_preview = QPlainTextEdit()
        self.c_preview.setReadOnly(True)
        self.c_preview.setPlaceholderText("Generated C code appears here")
        self.c_preview.setFont(fixed)
        self.c_highlighter = CHighlighter(self.c_preview.document())

        monitor_panel = QWidget()
        monitor_layout = QVBoxLayout(monitor_panel)
        monitor_layout.setContentsMargins(0, 0, 0, 0)
        monitor_layout.addLayout(monitor_bar)
        monitor_layout.addWidget(self.monitor_output)

        tabs = QTabWidget()
        tabs.addTab(self.log, "Build Log")
        tabs.addTab(monitor_panel, "Serial Monitor")
        tabs.addTab(self.c_preview, "Generated C")

        self.examples_list = QListWidget()
        self.examples_list.setMinimumWidth(220)
        self.examples_list.itemDoubleClicked.connect(self.open_selected_example)
        self._refresh_examples_list()

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)
        right_layout.addWidget(self.editor, 3)
        right_layout.addWidget(tabs, 2)

        splitter = QSplitter()
        splitter.addWidget(self.examples_list)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        outer.addLayout(top_bar)
        outer.addWidget(splitter, 1)

        status = QStatusBar()
        status.showMessage("Ready")
        self.setStatusBar(status)
        self._sync_baud_for_bootloader()
        self._sync_upload_controls_for_board()
        self.apply_theme(self.theme_combo.currentText())
        self.refresh_generated_c_view()

    def _setup_menu(self) -> None:
        menu = self.menuBar()
        file_menu = menu.addMenu("File")

        open_action = QAction("Open", self)
        open_action.triggered.connect(self.open_file)
        save_action = QAction("Save", self)
        save_action.triggered.connect(self.save_file)
        save_as_action = QAction("Save As", self)
        save_as_action.triggered.connect(self.save_file_as)

        file_menu.addAction(open_action)
        file_menu.addAction(save_action)
        file_menu.addAction(save_as_action)

        tools_menu = menu.addMenu("Tools")
        refresh_c_action = QAction("Refresh Generated C", self)
        refresh_c_action.triggered.connect(self.refresh_generated_c_view)
        format_action = QAction("Format Code", self)
        format_action.triggered.connect(self.format_code)
        format_action.setShortcut(QKeySequence("Ctrl+T"))
        intellisense_action = QAction("Show All Completions", self)
        intellisense_action.triggered.connect(self.editor.show_all_completions)
        intellisense_action.setShortcut(QKeySequence("Ctrl+F7"))
        build_action = QAction("Build", self)
        build_action.triggered.connect(self.build_project)
        build_action.setShortcut(QKeySequence("Ctrl+F5"))
        upload_action = QAction("Upload", self)
        upload_action.triggered.connect(self.upload_project)
        upload_action.setShortcut(QKeySequence("Ctrl+F6"))
        tools_menu.addAction(refresh_c_action)
        tools_menu.addAction(format_action)
        tools_menu.addAction(intellisense_action)
        tools_menu.addSeparator()
        tools_menu.addAction(build_action)
        tools_menu.addAction(upload_action)

        self.addAction(format_action)
        self.addAction(intellisense_action)
        self.addAction(build_action)
        self.addAction(upload_action)

        help_menu = menu.addMenu("Help")
        about_action = QAction("About Noin IDE", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def _on_text_changed(self) -> None:
        title = f"Noin IDE - {self.current_file.name}*"
        self.setWindowTitle(title)

    def _schedule_live_lint(self) -> None:
        self.editor.set_error_line(None)
        self.lint_timer.start()

    def run_live_lint(self) -> None:
        try:
            Compiler(self.editor.toPlainText().splitlines()).parse()
        except CompileError as err:
            code = self._error_code_for_message(err.message)
            self.lint_label.setText(f"Lint: [{code}] Line {err.line_no}")
            self.lint_label.setStyleSheet("color:#B91C1C;")
            self.editor.set_error_line(err.line_no)
            return
        except Exception:
            self.lint_label.setText("Lint: unavailable")
            self.lint_label.setStyleSheet("color:#B45309;")
            self.editor.set_error_line(None)
            return

        self.lint_label.setText("Lint: clean")
        self.lint_label.setStyleSheet("color:#166534;")
        self.editor.set_error_line(None)

    def _set_saved_title(self) -> None:
        self.setWindowTitle(f"Noin IDE - {self.current_file.name}")

    def _refresh_examples_list(self) -> None:
        self.examples_list.clear()
        examples_dir = ROOT_DIR / "examples"
        if not examples_dir.exists():
            return

        for p in sorted(examples_dir.glob("*.noin")):
            self.examples_list.addItem(str(p.relative_to(ROOT_DIR)))

    def open_selected_example(self, item: QListWidgetItem) -> None:
        rel_path = item.text().strip()
        path = ROOT_DIR / rel_path
        if path.exists():
            self._load_file(path)

    def _load_file(self, path: Path) -> None:
        try:
            content = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            content = "function setup()\n  pin(13, output)\n  serial(115200)\n  print(\"Noin is ready\")\nend\n\nfunction run()\n  toggle(13)\n  wait(500)\nend\n"
        except OSError as exc:
            QMessageBox.critical(self, "File Error", str(exc))
            return

        self.current_file = path
        self.editor.setPlainText(content)
        self._set_saved_title()
        self.statusBar().showMessage(f"Loaded: {path}", 3000)

    def open_file(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Open Noin File",
            str(ROOT_DIR),
            "Noin files (*.noin);;All files (*.*)",
        )
        if selected:
            self._load_file(Path(selected))

    def save_file(self) -> bool:
        try:
            self.current_file.write_text(self.editor.toPlainText(), encoding="utf-8")
        except OSError as exc:
            QMessageBox.critical(self, "Save Error", str(exc))
            return False

        self._set_saved_title()
        self.statusBar().showMessage(f"Saved: {self.current_file}", 3000)
        return True

    def save_file_as(self) -> None:
        selected, _ = QFileDialog.getSaveFileName(
            self,
            "Save Noin File As",
            str(self.current_file),
            "Noin files (*.noin);;All files (*.*)",
        )
        if not selected:
            return

        self.current_file = Path(selected)
        self.save_file()

    def refresh_ports(self) -> None:
        previous_port = self._selected_port() or self.settings.get("last_port", "")
        self.port_combo.clear()
        ports = sorted(list_ports.comports(), key=lambda p: p.device)
        for item in ports:
            text = f"{item.device} - {item.description}"
            self.port_combo.addItem(text, item.device)

        if not ports:
            self.port_combo.addItem("No ports found", "")
            return

        if previous_port:
            for i in range(self.port_combo.count()):
                if self.port_combo.itemData(i) == previous_port:
                    self.port_combo.setCurrentIndex(i)
                    break

        self._save_settings()

    def _selected_port(self) -> str:
        return self.port_combo.currentData() or ""

    def _selected_board_profile(self) -> str:
        return str(self.board_combo.currentData())

    def _is_make_avr_board(self) -> bool:
        return self._selected_board_profile() in {"nano_avr", "uno_avr"}

    def _sync_upload_controls_for_board(self) -> None:
        is_make_avr = self._is_make_avr_board()
        self.bootloader_combo.setEnabled(is_make_avr)
        self.programmer_combo.setEnabled(is_make_avr)
        self.avrdude_verbose_combo.setEnabled(is_make_avr)
        self.avrdude_chip_erase_checkbox.setEnabled(is_make_avr)
        self.avrdude_no_verify_checkbox.setEnabled(is_make_avr)
        self.avrdude_extra_edit.setEnabled(is_make_avr)
        if is_make_avr:
            self._sync_baud_for_bootloader()
        else:
            self.baud_combo.setEnabled(False)

    def _sync_baud_for_bootloader(self) -> None:
        if not self._is_make_avr_board():
            self.baud_combo.setEnabled(False)
            return
        mode = self.bootloader_combo.currentData()
        if mode == "optiboot":
            self.baud_combo.setCurrentText("115200")
            self.baud_combo.setEnabled(False)
        elif mode == "old":
            self.baud_combo.setCurrentText("57600")
            self.baud_combo.setEnabled(False)
        else:
            self.baud_combo.setEnabled(True)

    def apply_theme(self, theme_name: str) -> None:
        if theme_name not in THEMES:
            return

        palette_data = THEMES[theme_name]
        app_instance = QApplication.instance()
        if app_instance is None:
            return
        app = cast(QApplication, app_instance)

        palette = app.palette()
        palette.setColor(palette.ColorRole.Window, QColor(palette_data["window"]))
        palette.setColor(palette.ColorRole.Base, QColor(palette_data["base"]))
        palette.setColor(palette.ColorRole.AlternateBase, QColor(palette_data["alt"]))
        palette.setColor(palette.ColorRole.Text, QColor(palette_data["text"]))
        palette.setColor(palette.ColorRole.WindowText, QColor(palette_data["text"]))
        palette.setColor(palette.ColorRole.Button, QColor(palette_data["button"]))
        palette.setColor(palette.ColorRole.ButtonText, QColor(palette_data["text"]))
        palette.setColor(palette.ColorRole.Highlight, QColor(palette_data["highlight"]))
        palette.setColor(palette.ColorRole.HighlightedText, QColor("#FFFFFF"))
        app.setPalette(palette)

        app.setStyleSheet(
            f"""
            QMainWindow {{ background: {palette_data['window']}; }}
            QPlainTextEdit {{
                border: 1px solid {palette_data['editor_border']};
                border-radius: 10px;
                background: {palette_data['base']};
                selection-background-color: {palette_data['editor_selection']};
                padding: 6px;
            }}
            QPushButton {{
                border: 1px solid {palette_data['button_border']};
                border-radius: 8px;
                background: {palette_data['button_bg']};
                padding: 6px 10px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background: {palette_data['button_hover']}; }}
            QComboBox, QLineEdit {{
                border: 1px solid {palette_data['combo_border']};
                border-radius: 8px;
                padding: 5px 8px;
                background: {palette_data['base']};
            }}
            QMenuBar {{ background: {palette_data['menu_bg']}; }}
            QStatusBar {{ background: {palette_data['menu_bg']}; }}
            QTabWidget::pane {{
                border: 1px solid {palette_data['editor_border']};
                border-radius: 8px;
                background: {palette_data['base']};
            }}
            QTabBar::tab {{
                background: {palette_data['tab_bg']};
                color: {palette_data['text']};
                border: 1px solid {palette_data['editor_border']};
                padding: 6px 10px;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }}
            QTabBar::tab:selected {{
                background: {palette_data['tab_active_bg']};
                color: {palette_data['text']};
            }}
            """
        )

        self.highlighter.set_theme(theme_name)
        self.c_highlighter.set_theme(theme_name)
        self.editor.apply_visual_theme(palette_data)

    def show_about(self) -> None:
        QMessageBox.about(
            self,
            "About Noin IDE",
            "Noin IDE\n\n"
            "A compact Noin DSL editor inspired by Arduino IDE.\n"
            "- Syntax highlighting\n"
            "- Bootloader and programmer selection\n"
            "- One-click build and upload\n"
            "- Serial monitor\n"
            "- Generated C preview\n"
            "- toggle() and elseif support",
        )

    @staticmethod
    def _error_code_for_message(message: str) -> str:
        msg = message.lower()
        if "missing 'end'" in msg or "unclosed function" in msg:
            return "NOIN-E1101"
        if "unknown statement" in msg:
            return "NOIN-E1201"
        if "usage:" in msg:
            return "NOIN-E1202"
        if "undefined function" in msg:
            return "NOIN-E1301"
        if "invalid" in msg:
            return "NOIN-E1401"
        return "NOIN-E1999"

    def _go_to_line(self, line_no: int) -> None:
        cursor = self.editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        cursor.movePosition(QTextCursor.MoveOperation.Down, QTextCursor.MoveMode.MoveAnchor, max(line_no - 1, 0))
        self.editor.setTextCursor(cursor)
        self.editor.setFocus()
        self.editor.set_error_line(line_no)

    def format_code(self) -> None:
        original = self.editor.toPlainText()
        had_trailing_newline = original.endswith("\n")
        lines = original.splitlines()
        indent = 0
        out: list[str] = []

        for raw in lines:
            stripped = raw.strip()
            if not stripped:
                out.append("")
                continue

            lower = stripped.lower()
            if lower == "end" or lower == "else" or (lower.startswith("elseif ") and lower.endswith(" then")):
                indent = max(0, indent - 1)

            out.append(("  " * indent) + stripped)

            if lower.startswith("function "):
                indent += 1
            elif lower.startswith("if ") and lower.endswith(" then"):
                indent += 1
            elif lower.startswith("elseif ") and lower.endswith(" then"):
                indent += 1
            elif lower.startswith("while ") and lower.endswith(" do"):
                indent += 1
            elif lower.startswith("repeat ") and lower.endswith(" do"):
                indent += 1
            elif lower == "else":
                indent += 1

        self.editor.setPlainText("\n".join(out) + ("\n" if had_trailing_newline else ""))
        self.statusBar().showMessage("Code formatted", 2500)

    def check_syntax(self) -> None:
        if not self.save_file():
            return

        temp_output = Path(tempfile.gettempdir()) / "noin_syntax_check.generated.c"
        try:
            compile_file(self.current_file, temp_output)
        except CompileError as err:
            code = self._error_code_for_message(err.message)
            self.log.appendPlainText(f"[{code}] Syntax error: Line {err.line_no}: {err.message}\n")
            self.statusBar().showMessage(f"Syntax error [{code}]", 5000)
            self._go_to_line(err.line_no)
            return
        except Exception as exc:
            self.log.appendPlainText(f"[NOIN-E9000] Syntax check failed: {exc}\n")
            self.statusBar().showMessage("Syntax check failed", 5000)
            return
        finally:
            if temp_output.exists():
                try:
                    temp_output.unlink()
                except OSError:
                    pass

        self.log.appendPlainText("[NOIN-E0000] Syntax clean.\n")
        self.statusBar().showMessage("Syntax clean", 3000)

    def refresh_generated_c_view(self) -> None:
        if GENERATED_C.exists():
            try:
                content = GENERATED_C.read_text(encoding="utf-8")
            except OSError as exc:
                self.c_preview.setPlainText(f"Generated C could not be read: {exc}")
                return
            self.c_preview.setPlainText(content)
            self.statusBar().showMessage("Generated C refreshed", 2500)
            return

        self.c_preview.setPlainText("No generated C file exists yet. Build the project to create one.")

    def toggle_monitor(self) -> None:
        if self.serial_port is None:
            self.monitor_start()
        else:
            self.monitor_stop()

    def monitor_start(self) -> None:
        if self.monitor_start_pending:
            return

        port = self._selected_port()
        if not port:
            QMessageBox.warning(self, "Port Required", "Select a COM port for the serial monitor.")
            return

        try:
            baud = int(self.monitor_baud_combo.currentText().strip())
            if baud <= 0:
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, "Baud Error", "Monitor baud must be a positive number.")
            return

        try:
            self.serial_port = Serial(port=port, baudrate=baud, timeout=0)
            self.serial_port.reset_input_buffer()
            self.serial_port.reset_output_buffer()
        except SerialException as exc:
            QMessageBox.critical(self, "Monitor Error", str(exc))
            self.serial_port = None
            return

        self.monitor_start_pending = True
        QTimer.singleShot(600, self._finish_monitor_start)
        self.monitor_toggle_btn.setText("Stop Monitor")
        self.statusBar().showMessage(f"Opening serial monitor: {port} @ {baud}", 4000)

    def _finish_monitor_start(self) -> None:
        self.monitor_start_pending = False
        if self.serial_port is None:
            return
        self.monitor_timer.start()
        self.statusBar().showMessage("Serial monitor active", 2500)

    def monitor_stop(self) -> None:
        self.monitor_timer.stop()
        self.monitor_start_pending = False
        if self.serial_port is not None:
            try:
                self.serial_port.close()
            except SerialException:
                pass
            self.serial_port = None

        self.monitor_toggle_btn.setText("Start Monitor")
        self.statusBar().showMessage("Serial monitor closed", 3000)

    def monitor_clear(self) -> None:
        self.monitor_output.clear()

    def monitor_send(self) -> None:
        if self.serial_port is None:
            QMessageBox.information(self, "Monitor Closed", "Start the monitor first.")
            return

        text = self.monitor_input.text()
        if not text:
            return

        try:
            self.serial_port.write((text + "\n").encode("utf-8", errors="replace"))
        except SerialException as exc:
            QMessageBox.critical(self, "Send Error", str(exc))
            self.monitor_stop()
            return

        self.monitor_input.clear()

    def _poll_serial(self) -> None:
        if self.serial_port is None:
            return

        try:
            waiting = self.serial_port.in_waiting
            data = self.serial_port.read(waiting or 1)
        except SerialException as exc:
            self.monitor_output.appendPlainText(f"[Monitor hata] {exc}")
            self.monitor_stop()
            return

        if data:
            mode = self.monitor_decode_combo.currentText()
            if mode == "HEX":
                text = " ".join(f"{byte:02X}" for byte in data) + "\n"
            elif mode == "Latin-1":
                text = data.decode("latin-1", errors="replace")
            else:
                text = data.decode("utf-8", errors="replace")
            self.monitor_output.moveCursor(QTextCursor.MoveOperation.End)
            self.monitor_output.insertPlainText(text)
            self.monitor_output.moveCursor(QTextCursor.MoveOperation.End)

    def build_project(self) -> None:
        if not self.save_file():
            return
        if not self._preflight_syntax_check():
            return
        self._start_build(flash=False)

    def upload_project(self) -> None:
        if not self.save_file():
            return
        if not self._preflight_syntax_check():
            return

        port = self._selected_port()
        if not port:
            QMessageBox.warning(self, "Port Gerekli", "Yukleme icin bir COM port sec.")
            return

        self._start_build(flash=True)

    def _preflight_syntax_check(self) -> bool:
        try:
            Compiler(self.editor.toPlainText().splitlines()).parse()
        except CompileError as err:
            code = self._error_code_for_message(err.message)
            self.log.appendPlainText(f"[{code}] Otomatik syntax hata: Line {err.line_no}: {err.message}")
            self.statusBar().showMessage(f"Syntax hata [{code}]", 5000)
            self._go_to_line(err.line_no)
            return False
        except Exception as exc:
            self.log.appendPlainText(f"[NOIN-E9000] Otomatik syntax kontrol hatasi: {exc}")
            self.statusBar().showMessage("Otomatik syntax kontrol hatasi", 5000)
            return False

        return True

    def _start_build(self, flash: bool) -> None:
        if self.process.state() != QProcess.ProcessState.NotRunning:
            QMessageBox.information(self, "Operation In Progress", "Wait for the current operation to finish first.")
            return

        if flash and self.serial_port is not None:
            self.log.appendPlainText("Monitor closed automatically: the port was released before upload.")
            self.reopen_monitor_after_process = self.auto_reopen_monitor_checkbox.isChecked()
            self.monitor_stop()
        elif flash:
            self.reopen_monitor_after_process = False

        if not BUILD_SCRIPT.exists():
            QMessageBox.critical(self, "Missing Script", f"Not found: {BUILD_SCRIPT}")
            return

        args = [
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(BUILD_SCRIPT),
            "-Generate",
            "-Source",
            str(self.current_file),
            "-BoardProfile",
            str(self.board_combo.currentData()),
        ]

        command_label = "Build"
        self.last_build_output = ""
        if flash:
            command_label = "Build + Upload"
            args.extend(
                [
                    "-Flash",
                    "-Port",
                    self._selected_port(),
                    "-Baud",
                    self.baud_combo.currentText(),
                    "-Programmer",
                    str(self.programmer_combo.currentData()),
                ]
            )
            if self._is_make_avr_board():
                args.extend(["-VerboseLevel", self.avrdude_verbose_combo.currentText()])
                if self.avrdude_chip_erase_checkbox.isChecked():
                    args.append("-ChipErase")
                if self.avrdude_no_verify_checkbox.isChecked():
                    args.append("-NoVerify")
                extra = self.avrdude_extra_edit.text().strip()
                if extra:
                    args.extend(["-AvrdudeExtraArgs", extra])

        self.log.appendPlainText(f"\n=== {command_label} started ===")
        self.log.appendPlainText("powershell " + " ".join(args))
        self.statusBar().showMessage(f"{command_label} running...")
        self.process.setWorkingDirectory(str(ROOT_DIR))
        self.process.start("powershell", args)

    def _on_process_output(self) -> None:
        raw_chunk = self.process.readAllStandardOutput().data()
        raw = bytes(raw_chunk).decode("utf-8", errors="replace")
        if raw:
            self.last_build_output += raw
            self.log.moveCursor(QTextCursor.MoveOperation.End)
            self.log.insertPlainText(raw)
            self.log.moveCursor(QTextCursor.MoveOperation.End)

    def _jump_to_compile_error_line(self) -> None:
        match = re.search(r"Compile error:\s*Line\s*(\d+):\s*(.+)", self.last_build_output)
        if not match:
            return

        line_no = int(match.group(1))
        message = match.group(2).strip()
        code = self._error_code_for_message(message)
        self.log.appendPlainText(f"[{code}] Compile error: Line {line_no}: {message}")
        self._go_to_line(line_no)
        self.statusBar().showMessage(f"Jumped to compile error line: {line_no}", 4000)

    def _on_process_finished(self, exit_code: int, _status: QProcess.ExitStatus) -> None:
        if exit_code == 0:
            self.log.appendPlainText("=== Operation succeeded ===\n")
            self.statusBar().showMessage("Operation succeeded", 5000)
            self.refresh_generated_c_view()
            self.refresh_ports()
            if self._selected_board_profile() == "promicro_avr":
                QTimer.singleShot(2000, self.refresh_ports)
            if self.reopen_monitor_after_process:
                self.reopen_monitor_after_process = False
                self.monitor_start()
        else:
            self.log.appendPlainText(f"=== Operation failed (code={exit_code}) ===\n")
            self.statusBar().showMessage("Operation failed", 5000)
            self._jump_to_compile_error_line()
            self.reopen_monitor_after_process = False

    def closeEvent(self, event: QCloseEvent) -> None:
        self._save_settings()
        self.monitor_stop()
        super().closeEvent(event)


def _apply_light_theme(app: QApplication) -> None:
    app.setStyle("Fusion")


def main() -> int:
    app = QApplication(sys.argv)
    _apply_light_theme(app)

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
