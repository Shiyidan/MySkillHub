# 生成主流程

生成质量来自蓝图、推理结构重构和逐题闭环。质量门只做兜底拦截，不负责把低质量草稿修成可发布题目。

## 1. input_validation

- 使用 `prepare` 校验 `parsed_exam`、`validation_status=passed` 和约束文件。
- 约束至少包含正整数 `question_count`。
- 输入 JSON 或约束文件变化后，旧检查点不得继续复用。

## 2. generation_blueprints

- 每道新题先锁定一个母题，记录母题 `code` 和 `fingerprint`。
- 每道题必须读取 `references/generation-quality-blueprint.md`，先完成母题解剖，再设计新题，不得直接从原题改写。
- 蓝图必须包含 `source_deconstruction`、`structural_transformation`、`changed_reasoning_structure`、`changed_context`、`changed_values`、`difficulty_reassessment`、`diagram_generation_spec` 和 `novelty_rationale`。
- `source_deconstruction` 必须拆出母题的知识点、推理骨架、题面表层元素、图形元素、选项陷阱和真实难度来源；这些内容用于判断哪些可继承、哪些必须改变。
- `structural_transformation` 必须说明新题在条件组织、推理路径、变量关系、作答判断或干扰项逻辑上的结构性变化；只改数字、单位、人名、物体或选项顺序必须返工。
- `difficulty_reassessment` 必须独立评估新题难度，说明计算量、抽象程度、步骤数、陷阱强度、图形负荷和考试匹配度；不得直接复制母题 difficulty。
- `diagram_generation_spec` 必须说明是否需要图形。需要图形时，读取 `references/diagram-generation-standard.md`，先写图形语义、信息披露边界、几何/物理关系、标签、单位、坐标/比例、SVG 元素和题文引用；不需要图形时必须说明为什么 `images=[]`、`diagram=null` 合理。
- 不明确的约束写入工作目录供用户确认，不擅自扩展考试范围。
- TMUA 生成蓝图必须明确 `Paper 1` 或 `Paper 2`、`TMUA-P1/TMUA-P2`、`tmua_syllabus.json` 中的考纲 code/path，以及该题为什么符合对应 paper 的考查方式。
- TMUA Paper 1 生成题不得使用 `Logic & Proof`；Paper 2 可以使用 Mathematics 1、Mathematics 2 和 Logic & Proof，但必须体现数学论证、判断或推理能力。

## 3. question_transactions

每题按固定顺序闭环：

`唯一母题锁定 → 生成蓝图 → 图形信息设计 → 推理结构重构 → 独立求解 → 干扰项设计 → 解题轨迹构建 → 学习分析构建 → SVG排版与渲染 → 精确溯源 → 新颖性核验 → 题内微验证 → 原子提交`

- 每题只能有一个母题；不做多母题拼接。
- 干扰项必须来自本题可能错误，不得写泛化错因；每个错误选项在“干扰项设计”步骤就必须产出中文教学级解释，不能等质量门补写。
- 干扰项解释必须说明学生会如何误入该选项、错在知识点/推理/计算/读图/逻辑的哪一步，以及如何用本题条件排除。
- `solution_trace` 必须由新题独立求解得到，不能复用母题解析。
- 图形题必须先在“图形信息设计”步骤产出 `information_disclosure`，区分题面已知、视觉已知和必须由考生推出的隐藏关系；图形不得泄露关键中间量或答案。
- 图形题必须在“SVG排版与渲染”步骤产出 `layout_plan`、可编辑 SVG 和 PNG 预览记录；先检查标签碰撞、裁切、视觉比例和考试风格，再允许进入题内微验证。
- 无图题的两个图形步骤也必须记录“不需要图形”的一致决定，不能使用占位图。
- 难度必须在“题内微验证”中重新核对；如果新题实际难度与草稿 difficulty 不一致，回到生成蓝图或推理结构重构步骤返工。
- TMUA 生成题必须是 `multiple_choice`，并在 `target_exam_scope.modules` 中写入 Paper，而不是 ESAT 模块。
- 原子提交后题目片段不可再改；发现问题时回到对应步骤局部返工。

## 4. novelty_review

- 与输入题库和同批生成题比较指纹、题干结构、选项结构、数值关系和推理路径。
- 指纹不重复只是最低门槛；语义近似、只换数字或答案模式泄露都必须返工。
- 逐项比较母题和新题的题面句式、变量/对象、数值关系、图形拓扑、求解步骤、选项陷阱、答案位置和难度来源；任一核心维度同构且只有表层变化时必须返工。
- 图形题还要比较母题图形和新图形的拓扑结构、标注位置、已知量/未知量关系和视觉解题线索；只是重画同一图形或换数值必须返工。

## 5. independent_review

- 独立复算答案，检查条件充分性、唯一答案、语言、图形、难度、考纲和约束覆盖；TMUA 还必须检查 paper、TMUA syllabus code/path、选择题属性和 Paper 1/2 范围。
- 独立复核必须确认所有学习分析、错因、复习建议和选项反馈均为简体中文；不得保留英文占位错因或母题原英文解析片段。
- 独立复核必须重新判断 difficulty，不参考母题 difficulty 作为默认值；如判断依据不能支持当前难度标签，必须返工。
- 复核只定位问题，不直接补写质量字段。

## 6. export

- 使用 `pipeline.py finalize` 校验题量、唯一母题引用、重复情况和正式契约后原子写出。
- 只有所有阶段凭据和逐题事务均通过，才允许写出 `generated_exam`。
