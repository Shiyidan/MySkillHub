from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


CORE_PYTHON = Path(__file__).resolve().parents[1] / "python"
if str(CORE_PYTHON) not in sys.path:
    sys.path.insert(0, str(CORE_PYTHON))

from exam_paper_core import QuestionTransaction  # noqa: E402


METHOD = {
    "objective": "确认当前题目的来源证据是否足以支持后续解析工作。",
    "procedure": "逐项检查题面页面、选项区域与答案来源，并把检查结果写入独立证据充分性报告。",
    "decision_basis": "依据源页面可读性、题号对应关系和答案材料中的明确记录作出判断。",
    "result": "来源证据完整，可以继续恢复题面结构。",
    "exceptions": "无",
}


class QuestionTransactionTest(unittest.TestCase):
    def test_completed_step_can_be_rolled_back_with_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "evidence.json"
            output = root / "sufficiency.json"
            source.write_text('{"source": "page 1"}', encoding="utf-8")
            output.write_text('{"status": "enough"}', encoding="utf-8")
            transaction = QuestionTransaction.open_or_create(
                root / "Q1.transaction.json",
                mode="parser",
                question_id="Q1",
                source_fingerprint="a" * 64,
            )
            transaction.complete_step(
                "证据充分性确认",
                method=METHOD,
                input_evidence=[{"role": "题目证据包", "path": source}],
                output_evidence=[{"role": "证据充分性报告", "path": output}],
            )
            self.assertEqual(transaction.next_step, "题面结构恢复")

            transaction.rollback_to("证据充分性确认", reason="复核发现题号与答案页对应错误，需要重新制作证据包。")

            self.assertEqual(transaction.next_step, "证据充分性确认")
            self.assertEqual(transaction.data["completed_steps"], [])
            self.assertEqual(len(transaction.data["rollback_history"]), 1)
            self.assertEqual(
                transaction.data["rollback_history"][0]["removed_steps"],
                ["证据充分性确认"],
            )


if __name__ == "__main__":
    unittest.main()
