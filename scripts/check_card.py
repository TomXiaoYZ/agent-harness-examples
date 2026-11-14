#!/usr/bin/env python3
"""零依赖的 Markdown 任务卡自检，支持 Python 3.9 及以上。"""

import argparse
from pathlib import Path
import re
import sys


REQUIRED_SECTIONS = (
    "目标", "授权", "验收标准", "改动预算", "必须通过的新测试",
    "边界", "完成定义", "回执格式",
)
HEADING = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.+?)\s*$")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
PLACEHOLDER = re.compile(r"<([^<>/:\r\n]{1,40})>")
LINE_BUDGET = re.compile(r"(\d+)[ \t]*行")


class CardArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, "ERROR: " + " ".join(message.splitlines()) + "\n")


def byte_limit(value):
    limit = int(value)
    if limit < 0:
        raise argparse.ArgumentTypeError("字节上限不能为负数")
    return limit


def parse_markdown(body):
    """按顶层标题定位小节；围栏内的标题只是代码内容。"""
    sections = {}
    blocks = []
    section = ""
    fence = ""
    start = 0
    count = 0
    for number, line in enumerate(body.splitlines(), 1):
        marker = FENCE.match(line)
        if fence:
            sections.setdefault(section, []).append(line)
            if (marker and marker[1][0] == fence[0]
                    and len(marker[1]) >= len(fence) and not marker[2].strip()):
                blocks.append((section, start, count))
                fence = ""
            else:
                count += 1
            continue

        if marker and not (marker[1][0] == "`" and "`" in marker[2]):
            fence = marker[1]
            start = number
            count = 0
        else:
            heading = HEADING.match(line)
            if heading and len(heading[1]) <= 2:
                title = re.sub(r"[ \t]+#+$", "", heading[2]).strip()
                section = title if len(heading[1]) == 2 else ""
                sections.setdefault(section, [])
                continue
        sections.setdefault(section, []).append(line)

    if fence:
        blocks.append((section, start, count))
    return sections, blocks


def check_card(body, size, max_bytes, is_template):
    problems = []
    if size > max_bytes:
        problems.append(("size", f"文件 {size} 字节，超过上限 {max_bytes} 字节"))

    sections, blocks = parse_markdown(body)
    for name in REQUIRED_SECTIONS:
        if name not in sections:
            problems.append(("missing-section", f"缺少二级标题：{name}"))

    for section, start, count in blocks:
        if section != "回执格式" and count > 15:
            problems.append((
                "pasted-code", f"第 {start} 行开始的围栏代码块有 {count} 行，超过 15 行",
            ))

    if not is_template:
        for number, line in enumerate(body.splitlines(), 1):
            for match in PLACEHOLDER.finditer(line):
                if match[1].strip():
                    problems.append((
                        "placeholder", f"第 {number} 行残留占位符 {match[0]}",
                    ))

    budget = "\n".join(sections.get("改动预算", []))
    if "理由" not in budget:
        for match in LINE_BUDGET.finditer(budget):
            if int(match[1]) > 300:
                problems.append(("budget", f"改动预算 {match[1]} 行超过 300 行，未写理由"))
    return problems


def main(argv=None):
    parser = CardArgumentParser(
        description="检查任务卡大小、小节、代码块、占位符和改动预算。",
        allow_abbrev=False,
    )
    parser.add_argument("card", metavar="CARD", type=Path, help="UTF-8 任务卡路径")
    parser.add_argument(
        "--max-bytes", metavar="N", type=byte_limit, default=12288,
        help="字节数上限，默认 12288",
    )
    parser.add_argument("--template", action="store_true", help="只跳过占位符检查")
    args = parser.parse_args(argv)

    try:
        content = args.card.read_bytes()
        body = content.decode("utf-8")
    except (OSError, UnicodeError) as error:
        detail = " ".join(str(error).splitlines())
        print(f"ERROR: 无法读取 UTF-8 卡文件：{detail}", file=sys.stderr)
        return 2

    is_template = args.template or "templates" in args.card.absolute().parent.parts
    problems = check_card(body, len(content), args.max_bytes, is_template)
    for rule, detail in problems:
        print(f"FAIL {rule}: {detail}")
    if problems:
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
