# TMUA 生成约束

生成或审计 TMUA 新题时读取本文件，并同时读取 `../exam-paper-core/syllabus/tmua_syllabus.json`。本文件只约束生成过程；正式字段仍以共享 contract 为准。

## 考试结构

- TMUA 生成题只使用 `multiple_choice`。
- Paper 1 写作 `Paper 1: Mathematical Thinking`，字段：
  - `target_exam_scope.modules`: `["Paper 1"]`
  - `primary_module`: `"Paper 1"`
  - `primary_module_code`: `"TMUA-P1"`
  - `primary_module_label`: `"Paper 1: Mathematical Thinking"`
- Paper 2 写作 `Paper 2: Mathematical Reasoning`，字段：
  - `target_exam_scope.modules`: `["Paper 2"]`
  - `primary_module`: `"Paper 2"`
  - `primary_module_code`: `"TMUA-P2"`
  - `primary_module_label`: `"Paper 2: Mathematical Reasoning"`

## 考纲映射

- 所有 `syllabus_codes`、`syllabus_items`、`knowledge_points[].code`、`topic_code`、`syllabus_tags` 必须来自 `tmua_syllabus.json`。
- `syllabus_items[]` 必须与 `tmua_syllabus.json` 中的 code、label、module、parent、path 完全一致。
- TMUA 的 `syllabus_items[].module` 表示知识域，不是 paper：
  - `Mathematics 1`
  - `Mathematics 2`
  - `Logic & Proof`
- Paper 1 可使用 `Mathematics 1`、`Mathematics 2`，不得使用 `Logic & Proof`。
- Paper 2 可使用 `Mathematics 1`、`Mathematics 2`、`Logic & Proof`，但题目必须体现数学论证、判断或推理，而不是只换成 Paper 2 标签。

## 蓝图要求

每道 TMUA 新题在生成前必须写明：

- 唯一母题 `code` 与 `fingerprint`。
- 保留的 TMUA syllabus code。
- 目标 paper 与选择依据。
- 改变的推理结构：例如从一步代数变形成条件判断、从直接计算变成反例排除、从图像读取变成参数影响判断。
- 改变的语境和值。
- 新颖性依据：说明为什么不是只换数字、换变量名或同构选项。

## 题目设计要求

- 题干和选项使用英文，中文只进入解析、学习分析、错因和复核说明。
- 答案必须唯一，且可由题目独立推出。
- 干扰项必须来自本题具体推理误区，例如：
  - 忽略必要/充分条件方向；
  - 把反例当作证明；
  - 混淆恒等式与方程；
  - 漏掉定义域、取值范围或边界情形；
  - 把图像局部性质误当作全局性质。
- 不得为了“像 TMUA”而故意写模糊题干；精确性优先于难度。

## 评分与诊断

- 生成结果可给原始分、正确率、知识点诊断和错因诊断。
- 没有官方转换表时，不得声称可直接计算官方 1.0–9.0 scaled score。
- 如生成整套 TMUA 诊断卷，应在说明中标注每个 paper 的目标题量、实际题量和建议时间；缺题或缩短卷必须按题量比例给出诊断性时间建议。
