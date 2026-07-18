"""为试卷 Skill 提供全中文的命令行帮助与错误消息。"""

from __future__ import annotations

import argparse
import sys


def _translate_error(message: str) -> str:
    """翻译 argparse 会自动生成的常见错误消息。"""

    replacements = (
        ("the following arguments are required:", "缺少必填参数："),
        ("unrecognized arguments:", "无法识别的参数："),
        ("invalid choice:", "无效选项："),
        ("choose from", "可选值为"),
        ("expected one argument", "需要一个参数值"),
        ("expected at least one argument", "至少需要一个参数值"),
        ("not allowed with argument", "不能与此参数同时使用："),
        ("argument ", "参数 "),
    )
    for source, target in replacements:
        message = message.replace(source, target)
    return message


class ChineseArgumentParser(argparse.ArgumentParser):
    """使用中文标题、帮助说明和错误前缀的参数解析器。"""

    def __init__(self, *args: object, **kwargs: object) -> None:
        kwargs.setdefault("add_help", False)
        super().__init__(*args, **kwargs)
        self._positionals.title = "位置参数"
        self._optionals.title = "选项"
        self.add_argument(
            "-h",
            "--help",
            action="help",
            help="显示此帮助信息并退出。",
        )

    def format_usage(self) -> str:
        return super().format_usage().replace("usage:", "用法：", 1)

    def format_help(self) -> str:
        return super().format_help().replace("usage:", "用法：", 1)

    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}：错误：{_translate_error(message)}\n")
