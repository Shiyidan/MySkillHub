#!/usr/bin/env python3
"""Apply concise Chinese learning-analysis summaries to an existing question JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SHORT_ANALYSIS = {
    1: ("表面积公式与根式化简", "圆柱总面积等于球面积，化简得$R=5r$。", "复习球、圆柱表面积和根式化简。"),
    2: ("功-能关系与制动距离", "$Fs=\\frac{1}{2}mv^2$，代入得$s=20\\mathrm{m}$。", "复习动能、功和制动距离模型。"),
    3: ("分式方程与公式变形", "$p-y=\\frac{q-r}{s-x}$，变形得选项C。", "复习分式移项和符号处理。"),
    4: ("并联电路与电功率", "闭合后总电流$1.5A$，A表仍为$1.0A$。", "复习支路电流、并联和$P=IV$。"),
    5: ("比例定点与三角形面积", "按比例建坐标，三角形面积为$\\frac{23}{60}$。", "复习坐标面积公式和边上比例。"),
    6: ("图像读取与弹性势能", "$x^2=25$，由$F=2E/x$得$0.60N$。", "复习图像读数、单位换算和弹簧能量。"),
    7: ("指数运算与同底化简", "化为底数$3$，解指数方程得$x=6$。", "复习指数律和同底指数方程。"),
    8: ("压强、重力与密度", "$F=PA$求重力，再由体积求密度。", "复习$P=F/A$、重力和密度单位。"),
    9: ("百分比增长与比例", "设球员原薪$100$，计算新薪比例。", "复习百分比增长和比例比较。"),
    10: ("半衰期与指数衰减", "列$2(1/2)^{t/2}=(1/2)^{t/3}$得$t=6$。", "复习半衰期模型和指数方程。"),
    11: ("平均速度与分段时间", "总路程除以总时间，先统一各段时间单位。", "复习平均速度和单位换算。"),
    12: ("热传递与图像斜率", "稳态导热中绝缘层温度下降更陡。", "复习热传导和图像斜率。"),
    13: ("相似体面积体积比", "面积比给长度比，再用体积差求未知量。", "复习相似图形面积体积比。"),
    14: ("变压器与功率守恒", "先由功率求输电电压，再用匝数比反推。", "复习变压器公式和$P=IV$。"),
    15: ("标准形式与方程", "先化简括号系数，再开平方求两解差。", "复习指数运算和二次方程。"),
    16: ("波动中质点运动", "每周期路程为$4A$，乘频率得平均速率。", "复习振幅、频率和周期。"),
    17: ("向量与线段比例", "用$XP$求$Y$，再由$QY$反求$Q$。", "复习向量方向和坐标加减。"),
    18: ("串联电路与功率", "联立$P=IV$和$V_X=IR$求电流。", "复习串联电路和$P=IV$。"),
    19: ("三角范围与指数", "化为$(2/3)^{\\sin x}$，取最小指数。", "复习三角函数值域和指数。"),
    20: ("等温气体定律", "温度不变用$PV$恒定，处理中间深度压强。", "复习波义耳定律和比例。"),
}


def source_knowledge_points(question: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for item in question.get("knowledge_points", [])[:3]:
        if not isinstance(item, dict):
            continue
        if item.get("code"):
            names.append(str(item["code"]))
        elif item.get("name"):
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
            "exam_focus": focus,
            "solution": solution,
            "review_guidance": review,
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
