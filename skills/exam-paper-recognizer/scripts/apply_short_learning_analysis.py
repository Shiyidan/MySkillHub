#!/usr/bin/env python3
"""Apply concise Chinese learning-analysis summaries to an existing question JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SHORT_ANALYSIS = {
    1: ("表面积公式与根式化简", "圆柱总面积等于球面积，化简得$R=5r$。", "复习球、圆柱表面积和根式化简。"),
    2: ("功-能关系与制动距离", "$Fs=\\frac12mv^2$，代入得$s=20\\mathrm{m}$。", "复习动能、功和制动距离模型。"),
    3: ("分式方程与公式变形", "$p-y=\\frac{q-r}{s-x}$，变形得选项C。", "复习分式移项和符号处理。"),
    4: ("并联电路与电功率", "闭合后总电流$1.5A$，A表仍为$1.0A$。", "复习支路电流、并联和$P=VI$。"),
    5: ("比例定点与三角形面积", "按比例建坐标，三角形面积为$\\frac{23}{60}$。", "复习坐标面积公式和边上比例。"),
    6: ("图像读取与弹性势能", "$x^2=25$，由$F=2E/x$得$0.60N$。", "复习图像读数、单位换算和弹簧能量。"),
    7: ("指数运算与同底化简", "化为底数$3$，解指数方程得$x=6$。", "复习指数律和同底指数方程。"),
    8: ("压强、重力与密度", "$F=PA$求重力，再由体积求密度。", "复习$P=F/A$、重力和密度单位。"),
    9: ("百分比增长与比例", "设球员原薪$100$，计算新薪比例。", "复习百分比增长和比例比较。"),
    10: ("半衰期与指数衰减", "列$2(1/2)^{t/2}=(1/2)^{t/3}$得$t=6$。", "复习半衰期模型和指数方程。"),
}


def source_knowledge_points(question: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for item in question.get("knowledge_points", [])[:3]:
        if isinstance(item, dict) and item.get("name"):
            names.append(str(item["name"]))
    return names


def apply_short_analysis(data: dict[str, Any]) -> None:
    for question in data.get("questions", []):
        if not isinstance(question, dict):
            continue
        number = question.get("number")
        if number not in SHORT_ANALYSIS:
            continue
        focus, solution, review = SHORT_ANALYSIS[number]
        answer = ", ".join(map(str, question.get("answer", [])))
        values = [focus, solution, review]
        too_long = [value for value in values if len(value) > 50]
        if too_long:
            raise ValueError(f"Question {number} has overlong learning-analysis text: {too_long}")

        question["learning_analysis"] = {
            "language": "zh-CN",
            "max_chars_per_section": 50,
            "exam_focus_text": focus,
            "exam_focus": [
                {
                    "title": focus,
                    "description": focus,
                    "source_knowledge_points": source_knowledge_points(question),
                }
            ],
            "solution": {
                "status": "generated",
                "summary": solution,
                "steps": [],
                "final_answer": f"答案{answer}" if answer else "",
                "distractor_analysis": [],
            },
            "review_guidance": {
                "status": "generated",
                "summary": review,
                "recommended_topics": [],
                "practice_suggestions": [],
                "common_mistakes": [],
            },
        }

    data.setdefault("extraction", {})["learning_analysis_policy"] = {
        "language": "zh-CN",
        "max_chars_per_section": 50,
        "formula_format": "markdown_latex",
        "sections": ["exam_focus_text", "solution.summary", "review_guidance.summary"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("question_json")
    args = parser.parse_args()

    path = Path(args.question_json).expanduser().resolve()
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    apply_short_analysis(data)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Updated {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
