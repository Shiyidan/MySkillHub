---
name: exam-paper-workflow
description: 统一调度英文试卷识别、基于真题生成新题和 ESAT legacy 年度六套诊断组卷。适用于用户从前台上传 PDF、图片、答案 PDF 或 canonical JSON 后，需要自动判断并启动 exam-paper-parser、exam-paper-generator 或 exam-paper-assembler 的场景；也用于创建可恢复任务清单、隔离子任务目录和校验跨 Skill 交接。
---

# 英文试卷工作流

把本 Skill 作为套件的最外层入口。先建立任务清单，再把任务交给一个明确的子 Skill；不要同时加载三个子 Skill 的全部参考资料。

## 当前测试配置

启动任何操作前读取 `workflow-features.json`。当前 `parse_assemble_test` 配置只启用 `parse` 和 `assemble-year`，`generate` 已关闭；不得自动路由或直接调用生题流程。以后需要恢复生题时，只把该文件中的 `operations.generate` 改为 `true`，并把 `profile` 改为新的明确名称。

## 入口判断

1. 原始 PDF/图片、答案 PDF 或评分方案：路由到 `exam-paper-parser`。
2. `document_type=parsed_exam` 的 canonical JSON 加生成约束：仅当 `operations.generate=true` 时路由到 `exam-paper-generator`；当前测试配置必须拒绝。
3. 同年 ENGAA+NSAA、`metadata.paper_type=realPaper` 的 ESAT legacy canonical JSON：路由到 `exam-paper-assembler`，生成六套组合诊断卷。
4. 当前测试配置下，仅上传 canonical JSON 且目标不明确时，只确认是否生成六套诊断卷，不询问或建议生成新题。
5. 解析原始材料时，若用户未明确类型，只追问一次真题、普通模考卷或 AI 生成练习卷，并映射为 `realPaper`、`mockPaper`、`aiPaper`。

完整路由与交接规则见 `references/routing.md`。

## 标准流程

先生成不可歧义的任务清单：

```powershell
python scripts/workflow.py plan --operation parse --input question.pdf --input answer.pdf --paper-type realPaper --output-dir run
python scripts/workflow.py validate --manifest run/workflow-manifest.json
```

`plan` 只建立路由、输入哈希、工作目录、预期产物和子 Skill 启动命令，不伪造识别结果。后续执行清单中的 `next_action.command`，并按子 Skill 的阶段门禁推进。

## 子任务执行

- 协调者只持有任务清单、阶段状态和最终交付物。
- 子任务只接收当前步骤所需文件、参数和隔离输出目录。
- 支持子 Agent 的运行环境中，可在 `evidence_packets` 完成后按题并行执行 `question_transactions`；每题必须写入独立事务和最终片段。
- 不支持子 Agent 时，使用同一事务协议顺序执行，结果契约不变。
- 聚合前必须校验每个逐题事务已经原子提交；失败题只局部返工，不重跑已通过题目。
- `exam-paper-assembler` 必须等待年度 canonical 解析结果通过后再运行，不能与解析阶段并行。
- 当前 `workflow-features.json` 关闭 `generate` 时，协调者和子 Agent 均不得调用 `exam-paper-generator`。

## 自动化边界

脚本负责确定性工作：路由、哈希、任务身份、目录和命令。题面识别、独立求解、中文解析、考纲映射和图形复原仍由对应子 Skill 按证据执行。不得把“生成了任务清单”描述成“已经完成试卷解析”。

## 完成条件

- `workflow-manifest.json` 校验通过，输入文件及参数未在任务中途改变。
- 子 Skill 输出通过各自 canonical 或项目 JSON 契约。
- 解析任务的 `paper_type` 与入口选择一致，不能复用其他类型的旧断点。
- 年度 ESAT 组卷输出六个独立 `realPaper` JSON，每套三个模块、每模块固定 40 分钟。
