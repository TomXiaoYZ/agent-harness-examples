"""通过真实命令行检查任务卡；临时文件随每个测试清理。"""

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_card.py"
VALID_CARD = """# 示例任务

## 目标
修复一个可复现的问题。
## 授权
仅修改指定文件。
## 验收标准
运行指定测试。
## 改动预算
300 行
## 必须通过的新测试
覆盖问题的回归用例。
## 边界
不访问网络。
## 完成定义
测试通过并交回回执。
## 回执格式
报告结果。
"""


class CheckCardTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="card-test-", dir=ROOT)
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, "-B", str(SCRIPT), *map(str, args)],
            capture_output=True, text=True, encoding="utf-8", cwd=ROOT,
        )

    def check(self, body=VALID_CARD, *options, name="card.md"):
        path = self.directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        return self.run_cli(path, *options)

    def assert_ok(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "OK\n")
        self.assertEqual(result.stderr, "")

    def assert_failure(self, result, rule):
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("FAIL " + rule + ":", result.stdout)
        self.assertNotIn("OK\n", result.stdout)
        self.assertEqual(result.stderr, "")

    def assert_input_error(self, result):
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertEqual(len(result.stderr.splitlines()), 1)
        self.assertTrue(result.stderr.startswith("ERROR:"), result.stderr)

    def test_valid_card_ok(self):
        self.assert_ok(self.check())

    def test_oversize_fails(self):
        self.assert_failure(self.check(VALID_CARD, "--max-bytes", "100"), "size")

    def test_missing_section_fails(self):
        result = self.check(VALID_CARD.replace("## 边界\n不访问网络。\n", ""))
        self.assert_failure(result, "missing-section")
        self.assertIn("边界", result.stdout)

    def test_pasted_code_fails(self):
        block = "```python\n" + "print(1)\n" * 20 + "```\n"
        self.assert_failure(
            self.check(VALID_CARD.replace("## 目标\n", "## 目标\n" + block)),
            "pasted-code",
        )
        self.assert_ok(self.check(VALID_CARD + block))

    def test_placeholder_fails_unless_template(self):
        card = VALID_CARD.replace("示例任务", "<主题>")
        self.assert_failure(self.check(card), "placeholder")
        self.assert_ok(self.check(card, "--template"))

    def test_budget_without_reason_fails(self):
        card = VALID_CARD.replace("300 行", "500 行")
        self.assert_failure(self.check(card), "budget")
        self.assert_ok(self.check(card.replace("500 行", "500 行\n理由：需同步接口。")))

    def test_missing_file_exit_2(self):
        self.assert_input_error(self.run_cli(self.directory / "absent.md"))

    def test_default_limit_and_utf8_byte_boundary(self):
        body = VALID_CARD + "文" * 4096
        self.assert_failure(self.check(body), "size")
        size = len(VALID_CARD.encode("utf-8"))
        self.assert_ok(self.check(VALID_CARD, "--max-bytes", size))
        self.assert_failure(self.check(VALID_CARD, "--max-bytes", size - 1), "size")

    def test_templates_directory_skips_only_placeholders(self):
        card = VALID_CARD.replace("示例任务", "<主题>")
        self.assert_ok(self.check(card, name="templates/task-card.md"))
        self.assert_failure(self.check(card, name="my-templates/card.md"), "placeholder")
        self.assert_failure(self.check(card, "--template", "--max-bytes", 100), "size")

    def test_angle_brackets_with_url_path_or_empty_text_are_allowed(self):
        self.assert_ok(self.check(VALID_CARD + "<https://example.org> <a/b> <> < >\n"))

    def test_fences_have_fifteen_line_limit_and_matching_delimiters(self):
        for marker in ("```", "~~~~"):
            with self.subTest(marker=marker):
                block = marker + "\n" + "line\n" * 15 + marker + "\n"
                self.assert_ok(self.check(VALID_CARD.replace("## 目标\n", "## 目标\n" + block)))
        block = "````text\n" + "```\n" * 16 + "````\n"
        self.assert_failure(self.check(block + VALID_CARD), "pasted-code")
        self.assert_failure(self.check(VALID_CARD.replace("## 目标\n", "## 目标\n~~~\n") + "x\n" * 20), "pasted-code")

    def test_receipt_exemption_ends_at_next_section(self):
        block = "```\n" + "line\n" * 16 + "```\n"
        self.assert_ok(self.check(VALID_CARD + "### 示例\n" + block))
        self.assert_failure(self.check(VALID_CARD + "## 轮次\n" + block), "pasted-code")

    def test_headings_inside_fences_do_not_count(self):
        card = VALID_CARD.replace("## 边界\n", "```\n## 边界\n```\n")
        self.assert_failure(self.check(card), "missing-section")
        card = VALID_CARD.replace("## 目标\n", "## 目标\n```\n## 回执格式\n" + "x\n" * 16 + "```\n")
        self.assert_failure(self.check(card), "pasted-code")
        self.assert_ok(self.check(VALID_CARD.replace("## 边界", "## 边界 ##")))

    def test_budget_reason_must_be_in_budget_section(self):
        self.assert_failure(self.check(VALID_CARD.replace("300 行", "301行") + "理由：别处说明。\n"), "budget")
        self.assert_ok(self.check(VALID_CARD + "另一个文档有 500 行。\n"))

    def test_all_problems_are_reported_together(self):
        card = VALID_CARD.replace("## 边界\n不访问网络。\n", "").replace("300 行", "500 行")
        card = "```\n" + "line\n" * 16 + "```\n<主题>\n" + card
        result = self.check(card, "--max-bytes", 100)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(
            {line.split(":", 1)[0] for line in result.stdout.splitlines()},
            {"FAIL size", "FAIL missing-section", "FAIL pasted-code", "FAIL placeholder", "FAIL budget"},
        )

    def test_invalid_arguments_exit_2(self):
        for args in ((), ("card.md", "--unknown"), ("card.md", "--max-bytes"),
                     ("card.md", "--max-bytes", "abc"), ("card.md", "--max-bytes", "-1")):
            with self.subTest(args=args):
                self.assert_input_error(self.run_cli(*args))

    def test_invalid_utf8_and_directory_exit_2(self):
        path = self.directory / "invalid.md"
        path.write_bytes(b"\xff")
        self.assert_input_error(self.run_cli(path))
        self.assert_input_error(self.run_cli(self.directory))


if __name__ == "__main__":
    unittest.main()
