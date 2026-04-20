#!/usr/bin/env python3
"""noinc"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Dict, List, Set


@dataclass
class CompileError(Exception):
    line_no: int
    message: str

    def __str__(self) -> str:
        return f"Line {self.line_no}: {self.message}"


IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class Compiler:
    def __init__(self, lines: List[str]) -> None:
        self.lines = lines
        self.run_output: List[str] = []
        self.functions_output: List[str] = []
        self.block_stack: List[str] = []
        self.current_function: str | None = None
        self.defined_functions: Set[str] = set()
        self.function_order: List[str] = []
        self.called_functions: Set[str] = set()
        self.variables_by_scope: Dict[str, Set[str]] = {"run": set()}
        self.indent_level = 1

    def emit(self, code: str, indent: int = 1) -> None:
        line = ("    " * indent) + code
        if self.current_function is None:
            self.run_output.append(line)
        else:
            self.functions_output.append(line)

    def _strip_comment(self, raw: str) -> str:
        line = raw
        if "--" in line:
            line = line.split("--", 1)[0]
        if "#" in line:
            line = line.split("#", 1)[0]
        return line.strip()

    def _scope_name(self) -> str:
        if self.current_function is None:
            return "run"
        return f"fn:{self.current_function}"

    def _declare_var(self, idx: int, name: str) -> None:
        if not IDENT_RE.match(name):
            raise CompileError(idx, f"Invalid variable name: {name}")

        scope = self._scope_name()
        declared = self.variables_by_scope.setdefault(scope, set())
        if name not in declared:
            self.emit(f"int32_t {name} = 0;", indent=self.indent_level)
            declared.add(name)

    def _translate_expr(self, idx: int, expr: str) -> str:
        out = expr.strip()
        if not out:
            raise CompileError(idx, "Expression cannot be empty")

        out = re.sub(r"\btrue\b", "1", out)
        out = re.sub(r"\bfalse\b", "0", out)
        out = re.sub(r"\band\b", "&&", out)
        out = re.sub(r"\bor\b", "||", out)
        out = re.sub(r"\bnot\b", "!", out)
        out = re.sub(r"\bread\s*\(\s*([^\)]+?)\s*\)", r"noin_read(\1)", out)
        out = re.sub(r"\banalog\s*\(\s*([^\)]+?)\s*\)", r"noin_analog_read(\1)", out)
        out = re.sub(r"\bmap\s*\(", "noin_map(", out)

        allowed = re.compile(r"^[A-Za-z0-9_\s\(\)\+\-\*/%<>=!&\|,\.]+$")
        if not allowed.match(out):
            raise CompileError(idx, f"Expression contains unsupported characters: {expr}")
        return out

    @staticmethod
    def _parse_call_args(idx: int, line: str, fn_name: str) -> List[str]:
        m = re.fullmatch(rf"{fn_name}\s*\((.*)\)", line)
        if not m:
            raise CompileError(idx, f"Invalid call syntax for {fn_name}")
        inside = m.group(1).strip()
        if not inside:
            return []
        return [p.strip() for p in inside.split(",")]

    def parse(self) -> str:
        prelude = [
            '#include "noin_runtime.h"',
            '#include "noin_program.h"',
            "",
        ]

        for idx, raw in enumerate(self.lines, start=1):
            line = self._strip_comment(raw)
            if not line:
                continue

            if line == "end":
                self._parse_end(idx)
                continue

            if line == "else":
                self._parse_else(idx)
                continue

            if line.startswith("elseif ") and line.endswith(" then"):
                self._parse_elseif(idx, line)
                continue

            if line.startswith("function "):
                self._parse_function(idx, line)
            elif line.startswith("local "):
                self._parse_local(idx, line)
            elif line.startswith("if ") and line.endswith(" then"):
                self._parse_if(idx, line)
            elif line.startswith("while ") and line.endswith(" do"):
                self._parse_while(idx, line)
            elif line.startswith("repeat ") and line.endswith(" do"):
                self._parse_repeat(idx, line)
            elif "=" in line and "==" not in line and "!=" not in line and "<=" not in line and ">=" not in line:
                self._parse_assign(idx, line)
            else:
                self._parse_statement(idx, line)

        if self.block_stack:
            raise CompileError(len(self.lines), f"Missing 'end' for: {self.block_stack[-1]}")

        if self.current_function is not None:
            raise CompileError(len(self.lines), "Unclosed function block")

        missing_functions = sorted(self.called_functions - self.defined_functions)
        if missing_functions:
            raise CompileError(
                len(self.lines),
                f"Undefined function call(s): {', '.join(missing_functions)}",
            )

        has_setup = "setup" in self.defined_functions
        has_run = "run" in self.defined_functions
        has_loop = "loop" in self.defined_functions

        if has_run and has_loop:
            raise CompileError(
                len(self.lines),
                "Use only one main loop function: run() or loop()",
            )

        result: List[str] = []
        result.extend(prelude)
        if self.function_order:
            for name in self.function_order:
                result.append(f"static void {name}(void);")
            result.append("")
        if self.functions_output:
            result.extend(self.functions_output)
            result.append("")
        result.append("void noin_run(void)")
        result.append("{")

        if has_setup:
            result.append("    setup();")

        if self.run_output:
            result.extend(self.run_output)

        if has_run:
            result.append("    while (1)")
            result.append("    {")
            result.append("        run();")
            result.append("    }")
        elif has_loop:
            result.append("    while (1)")
            result.append("    {")
            result.append("        loop();")
            result.append("    }")

        result.append("}")
        result.append("")
        return "\n".join(result)

    def _parse_function(self, idx: int, line: str) -> None:
        if self.current_function is not None:
            raise CompileError(idx, "Nested functions are not supported")

        m = re.fullmatch(r"function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*\)", line)
        if not m:
            raise CompileError(idx, "Usage: function <name>()")

        name = m.group(1)
        self.defined_functions.add(name)
        self.function_order.append(name)
        self.current_function = name
        self.variables_by_scope.setdefault(f"fn:{name}", set())
        self.indent_level = 1
        self.functions_output.append(f"static void {name}(void)")
        self.functions_output.append("{")
        self.block_stack.append("function")

    def _parse_local(self, idx: int, line: str) -> None:
        m = re.fullmatch(r"local\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?:=\s*(.+))?", line)
        if not m:
            raise CompileError(idx, "Usage: local <name> = <expr>")

        name = m.group(1)
        expr = m.group(2)
        self._declare_var(idx, name)
        if expr is not None:
            self.emit(f"{name} = {self._translate_expr(idx, expr)};", indent=self.indent_level)

    def _parse_assign(self, idx: int, line: str) -> None:
        left, right = [p.strip() for p in line.split("=", 1)]
        if not IDENT_RE.match(left):
            raise CompileError(idx, "Assignment left side must be a variable name")
        self._declare_var(idx, left)
        self.emit(f"{left} = {self._translate_expr(idx, right)};", indent=self.indent_level)

    def _parse_if(self, idx: int, line: str) -> None:
        cond = line[len("if ") : -len(" then")].strip()
        self.emit(f"if ({self._translate_expr(idx, cond)})", indent=self.indent_level)
        self.emit("{", indent=self.indent_level)
        self.block_stack.append("if")
        self.indent_level += 1

    def _parse_else(self, idx: int) -> None:
        if not self.block_stack or self.block_stack[-1] != "if":
            raise CompileError(idx, "'else' must be inside an 'if' block")
        self.indent_level -= 1
        self.emit("}", indent=self.indent_level)
        self.emit("else", indent=self.indent_level)
        self.emit("{", indent=self.indent_level)
        self.block_stack[-1] = "if_else"
        self.indent_level += 1

    def _parse_elseif(self, idx: int, line: str) -> None:
        if not self.block_stack or self.block_stack[-1] != "if":
            raise CompileError(idx, "'elseif' must be inside an 'if' block")

        cond = line[len("elseif ") : -len(" then")].strip()
        self.indent_level -= 1
        self.emit("}", indent=self.indent_level)
        self.emit(f"else if ({self._translate_expr(idx, cond)})", indent=self.indent_level)
        self.emit("{", indent=self.indent_level)
        self.indent_level += 1

    def _parse_while(self, idx: int, line: str) -> None:
        cond = line[len("while ") : -len(" do")].strip()
        self.emit(f"while ({self._translate_expr(idx, cond)})", indent=self.indent_level)
        self.emit("{", indent=self.indent_level)
        self.block_stack.append("while")
        self.indent_level += 1

    def _parse_repeat(self, idx: int, line: str) -> None:
        count_expr = line[len("repeat ") : -len(" do")].strip()
        expr = self._translate_expr(idx, count_expr)
        loop_var = f"_noin_i_{idx}"
        self.emit(f"for (int32_t {loop_var} = 0; {loop_var} < ({expr}); ++{loop_var})", indent=self.indent_level)
        self.emit("{", indent=self.indent_level)
        self.block_stack.append("repeat")
        self.indent_level += 1

    def _parse_statement(self, idx: int, line: str) -> None:
        parts = line.split()
        if parts and parts[0].lower() == "pin":
            if len(parts) != 3:
                raise CompileError(idx, "Usage: pin <number> output|input")
            pin = self._parse_int(idx, parts[1], "pin")
            mode = parts[2].lower()
            if mode == "output":
                self.emit(f"noin_pin_output({pin});", indent=self.indent_level)
                return
            if mode == "input":
                self.emit(f"noin_pin_input({pin});", indent=self.indent_level)
                return
            raise CompileError(idx, "Mode must be output or input")

        if parts and parts[0].lower() in {"high", "low", "wait"}:
            if len(parts) != 2:
                raise CompileError(idx, f"Usage: {parts[0]} <number>")
            val = self._parse_int(idx, parts[1], parts[0])
            name = parts[0].lower()
            if name == "high":
                self.emit(f"noin_high({val});", indent=self.indent_level)
                return
            if name == "low":
                self.emit(f"noin_low({val});", indent=self.indent_level)
                return
            self.emit(f"noin_wait_ms({val});", indent=self.indent_level)
            return

        if line.startswith("pin("):
            args = self._parse_call_args(idx, line, "pin")
            if len(args) != 2:
                raise CompileError(idx, "Usage: pin(<n>, output|input)")
            pin = self._parse_int(idx, args[0], "pin")
            mode = args[1].strip().lower().strip('"\'')
            if mode == "output":
                self.emit(f"noin_pin_output({pin});", indent=self.indent_level)
            elif mode == "input":
                self.emit(f"noin_pin_input({pin});", indent=self.indent_level)
            else:
                raise CompileError(idx, "Mode must be output or input")
            return

        if line.startswith("write("):
            args = self._parse_call_args(idx, line, "write")
            if len(args) != 2:
                raise CompileError(idx, "Usage: write(<n>, high|low)")
            pin = self._parse_int(idx, args[0], "pin")
            level = args[1].strip().lower().strip('"\'')
            if level == "high":
                self.emit(f"noin_high({pin});", indent=self.indent_level)
            elif level == "low":
                self.emit(f"noin_low({pin});", indent=self.indent_level)
            else:
                raise CompileError(idx, "Level must be high or low")
            return

        if line.startswith("high("):
            args = self._parse_call_args(idx, line, "high")
            if len(args) != 1:
                raise CompileError(idx, "Usage: high(<n>)")
            pin = self._parse_int(idx, args[0], "pin")
            self.emit(f"noin_high({pin});", indent=self.indent_level)
            return

        if line.startswith("low("):
            args = self._parse_call_args(idx, line, "low")
            if len(args) != 1:
                raise CompileError(idx, "Usage: low(<n>)")
            pin = self._parse_int(idx, args[0], "pin")
            self.emit(f"noin_low({pin});", indent=self.indent_level)
            return

        if line.startswith("toggle("):
            args = self._parse_call_args(idx, line, "toggle")
            if len(args) != 1:
                raise CompileError(idx, "Usage: toggle(<n>)")
            pin = self._parse_int(idx, args[0], "pin")
            self.emit(f"noin_toggle({pin});", indent=self.indent_level)
            return

        if line.startswith("wait("):
            args = self._parse_call_args(idx, line, "wait")
            if len(args) != 1:
                raise CompileError(idx, "Usage: wait(<ms>)")
            ms = self._translate_expr(idx, args[0])
            self.emit(f"noin_wait_ms({ms});", indent=self.indent_level)
            return

        if line.startswith("pwm("):
            args = self._parse_call_args(idx, line, "pwm")
            if len(args) != 2:
                raise CompileError(idx, "Usage: pwm(<pin>, <value>)")
            pin = self._translate_expr(idx, args[0])
            value = self._translate_expr(idx, args[1])
            self.emit(f"noin_pwm_write({pin}, {value});", indent=self.indent_level)
            return

        if line.startswith("serial("):
            args = self._parse_call_args(idx, line, "serial")
            if len(args) != 1:
                raise CompileError(idx, "Usage: serial(<baud>)")
            baud = self._translate_expr(idx, args[0])
            self.emit(f"noin_serial_begin({baud});", indent=self.indent_level)
            return

        if line.startswith("print("):
            args = self._parse_call_args(idx, line, "print")
            if len(args) != 1:
                raise CompileError(idx, "Usage: print(<expr>|\"text\")")

            arg = args[0].strip()
            if len(arg) >= 2 and ((arg[0] == '"' and arg[-1] == '"') or (arg[0] == "'" and arg[-1] == "'")):
                c_string = self._to_c_string_literal(arg)
                self.emit(f"noin_print_str({c_string});", indent=self.indent_level)
                return

            expr = self._translate_expr(idx, arg)
            self.emit(f"noin_print_int({expr});", indent=self.indent_level)
            return

        m = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*\)", line)
        if m:
            name = m.group(1)
            self.called_functions.add(name)
            self.emit(f"{name}();", indent=self.indent_level)
            return

        raise CompileError(idx, f"Unknown statement: {line}")

    @staticmethod
    def _to_c_string_literal(raw: str) -> str:
        quote = raw[0]
        inner = raw[1:-1]
        if quote == "'":
            inner = inner.replace('\\', '\\\\').replace('"', '\\"')
            return f'"{inner}"'
        return raw

    def _parse_end(self, idx: int) -> None:
        if not self.block_stack:
            raise CompileError(idx, "Unexpected 'end'")

        kind = self.block_stack.pop()
        if kind == "function":
            if self.current_function is None:
                raise CompileError(idx, "Internal state error for function end")
            self.functions_output.append("}")
            self.current_function = None
            self.indent_level = 1
            return

        self.indent_level -= 1
        self.emit("}", indent=self.indent_level)

    @staticmethod
    def _parse_int(idx: int, raw: str, label: str) -> int:
        try:
            value = int(raw)
        except ValueError as exc:
            raise CompileError(idx, f"Invalid {label}: {raw}") from exc

        if value < 0 or value > 65535:
            raise CompileError(idx, f"{label.capitalize()} out of range: {value}")
        return value


def compile_file(input_path: Path, output_path: Path) -> None:
    compiler = Compiler(input_path.read_text(encoding="utf-8").splitlines())
    c_code = compiler.parse()
    output_path.write_text(c_code, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Compile .noin DSL into C")
    parser.add_argument("input", type=Path, help="Input DSL file")
    parser.add_argument("output", type=Path, help="Output C file")
    args = parser.parse_args()

    try:
        compile_file(args.input, args.output)
    except CompileError as err:
        print(f"Compile error: {err}")
        return 1

    print(f"Generated: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
