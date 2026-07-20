# 工作流路由与交接

## 路由表

| 输入 | 目标 | 子 Skill | 主要输出 |
|---|---|---|---|
| PDF/图片，可附答案或评分方案 | 识别试题 | `exam-paper-parser` | `parsed_exam` canonical JSON |
| `parsed_exam` + 生成约束 | 生成新题 | `exam-paper-generator` | 当前 `parse_assemble_test` 配置已关闭，拒绝执行 |
| 同年 ENGAA+NSAA ESAT legacy `realPaper` | 诊断组卷 | `exam-paper-assembler` | 六个项目 `realPaper` JSON |

## 不可自动判断的情况

当前测试配置只允许解析和组卷。单独上传 `parsed_exam` 时，满足 ENGAA+NSAA 年度题库条件即可路由到组卷；不满足时应说明暂不能组卷，不再追问是否生题。

所有路由先读取 `../workflow-features.json`。当 `operations.generate=false` 时，总入口必须拒绝 `generate`，生成脚本也必须拒绝除 `preflight` 之外的命令。

## 交接契约

协调者向子任务提供：

1. 已校验的绝对输入路径和 SHA-256。
2. 唯一 `task_id`、隔离 `workdir` 和预期输出路径。
3. 明确的 `paper_type`、操作类型和约束文件。
4. 只读源文件；子任务不得覆盖源文件。

子任务返回：

1. 阶段状态或最终 JSON 路径。
2. 阶段凭据与逐题事务路径。
3. 未通过项及其局部返工步骤。

## 并行规则

- 来源盘点、页面检查和证据包制作存在顺序依赖，顺序执行。
- 证据包完成后，不同题目的逐题事务可以并行；同一道题内部步骤必须顺序执行。
- 独立复核必须读取已提交题目片段，不能与该题事务并行。
- 六套组合卷可在年度 canonical 通过后并行导出，但必须共用同一份只读输入。

## 失败恢复

- 输入哈希或入口参数改变：建立新任务目录，不复用旧断点。
- 单题失败：使该题事务失效，只重做对应步骤。
- 逐题事务统一通过 `exam-paper-core/scripts/question_transaction.py` 操作；禁止手工修改事务状态或伪造已完成步骤。
- 最终契约失败：定位到字段所属生产步骤返工，不用清理脚本静默删改。
- 组卷缺题：仍输出并在最终 `metadata.remarks` 提示管理员；每模块时间保持 40 分钟。
