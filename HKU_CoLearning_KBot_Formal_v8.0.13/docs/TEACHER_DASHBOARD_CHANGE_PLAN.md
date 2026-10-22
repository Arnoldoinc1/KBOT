# Teacher Dashboard and RAG Change Plan

## 1. 背景

当前项目已经形成三个主要服务：

- `student_app`：学生注册、登录、练习、Notes QA、历史记录。
- `teacher_app`：教师登录、dashboard、课程材料管理、记录审阅、导出。
- `knowledge_service`：课程材料上传、解析、chunk 存储、检索。

目前已经确认几个需要改进的方向：

- 教师端 dashboard 对 `MCQ`、`True/False`、`Matching` 的结构化信息展示不完整。
- Excel 导出接口目前返回的是 CSV，而不是真正的 `.xlsx`。
- Kahoot 导出需要稳定按官方模板生成，并只导出适合 Kahoot 的题型。
- CSV 导入入口暂时保留作为兜底入口，但不作为主要数据流。
- 教师端混合检索后续应接入 Chroma，MySQL 继续作为业务主库。
- 知识服务侧 RAG 后续也需要 embedding/hybrid retrieval，但不和教师端展示改造放在同一轮。

本计划的原则是：先把教师端数据展示和导出修稳，再上教师端 Chroma，最后再升级课程知识库 RAG。

## 2. 总体目标

### 2.1 第一优先级

教师端能够正确、统一地展示学生答题记录中的结构化题目信息。

重点题型：

- `MCQ`
- `True/False`
- `Matching`

教师看到一条记录时，应能直接判断：

- 题干是什么
- 学生答了什么
- 正确答案是什么
- 选择题有哪些选项
- 判断题的正确 True/False 是什么
- Matching 的学生配对和正确配对分别是什么

### 2.2 第二优先级

导出能力收口：

- Excel 导出必须生成真正的 `.xlsx`
- Kahoot 导出必须使用模板生成
- Kahoot 只导出 `MCQ` 和 `True/False`
- 导出逻辑应优先使用结构化字段，正则只作为兜底

### 2.3 第三优先级

教师端加入 Chroma 语义检索：

- MySQL 继续作为业务主库
- Chroma 作为教师端学生记录的语义索引
- embedding 模型采用 `bge-base-en-v1.5`
- 搜索采用语义召回和关键词召回融合

### 2.4 第四优先级

知识服务 RAG 升级：

- 课程知识库也复用 `bge-base-en-v1.5`
- 从固定 chunk + SQLite 词法召回升级为 hybrid RAG
- 后续再增强 PPTX、表格、图片/OCR 等处理

## 3. 已确认决策

- 暂时不一次性大改所有模块。
- 第一轮先做教师端结构化展示。
- 第二轮做 Excel/Kahoot 导出。
- 第三轮再做教师端 Chroma。
- 知识服务 RAG 后续单独规划。
- CSV 导入入口保留，但只作为兜底入口。
- CSV 字段按学生端当前记录结构兼容。
- 英文业务 embedding 模型采用 `BAAI/bge-base-en-v1.5`。
- 教师端记录检索和知识库 RAG 可以复用同一个 embedding 模型。
- MySQL 不被 Chroma 替换。
- Chroma 只保存语义检索需要的索引数据，完整业务数据仍从 MySQL 读取。

## 4. 当前代码中的主要问题

### 4.1 教师端记录展示不完整

学生端提交时，会把题目的结构化字段写入 `options_or_pairs`。

这些字段包括：

- `options`
- `correct_index`
- `left`
- `right`
- `correct_mapping`
- `answer`
- `reference`
- `key_points`

但教师端 `_record_dict()` 目前主要返回：

- `question`
- `answer`
- `correct_answer`
- `ai_feedback`
- `teacher_feedback`
- `rag_cited`

它没有把 `options_or_pairs` 解析成教师端可直接使用的结构化 view model。

结果是：

- MCQ 可能只显示题干，不显示四个选项。
- True/False 只看到题干和答案，不清楚正确选项索引。
- Matching 不能清楚看到左右配对。
- 教师端、学生历史、Kahoot 导出可能用不同逻辑还原同一条记录。

### 4.2 多套解析逻辑容易不一致

目前类似逻辑分散在多个位置：

- 教师端 dashboard 组装记录
- 学生端 history 回看
- Kahoot 导出恢复选项和正确答案
- 详细反馈文本里也保存了一份可读信息

如果每个模块各自解析 `options_or_pairs`、`correct_answer`、`ai_feedback`，就可能出现同一条记录在不同地方展示不一致。

### 4.3 Excel 导出名实不符

当前 `export_excel` 实际仍走 CSV 响应。

需要改为：

- 使用 `openpyxl`
- 返回 `.xlsx`
- 设置正确 mimetype
- 使用合理文件名
- 支持换行、列宽、冻结首行等基础可读性设置

### 4.4 Kahoot 导出需要统一数据来源

Kahoot 导出应只处理：

- `MCQ`
- `True/False`

数据来源优先级应为：

1. 结构化字段
2. `options_or_pairs`
3. `ai_feedback` 中的详细反馈文本
4. 题干中的选项正则兜底

正则只能兜底，不能作为主要解析路径。

### 4.5 CSV 导入入口需要宽容但不能吞掉结构

CSV 导入保留为兜底入口，但不能只导入 `question/answer/score`。

它应尽量兼容学生端记录结构：

- `student_name`
- `chapter`
- `chapter_id`
- `question_type`
- `topic`
- `question`
- `answer`
- `options_or_pairs`
- `correct_answer`
- `score`
- `ai_feedback`
- `teacher_feedback`
- `generation_source`
- `grading_source`
- `citations_json`

最小必填可以保持宽松，但如果 CSV 中存在结构化字段，应保留下来。

## 5. 分阶段实施计划

## Phase 1：教师端结构化展示

### Feat 1：统一答题记录解析层

#### 目标

新增一个统一的 record review / attempt payload 解析层，让教师端展示、导出、历史回看都能复用同一套规则。

#### 建议范围

可考虑在 `common` 下新增或扩展一个模块，用来将 `StudentQARecord` 解析成稳定 view model。

输出结构建议包含：

- `question_type`
- `question`
- `student_answer`
- `correct_answer`
- `options`
- `correct_index`
- `selected_index`
- `left`
- `right`
- `submitted_pairs`
- `correct_pairs`
- `reference_answer`
- `key_points`
- `teacher_feedback`
- `citations`

#### 解析优先级

1. 优先解析 `options_or_pairs` 中的结构化 JSON。
2. 其次使用 `correct_answer`。
3. 再从 `ai_feedback` 的详细反馈文本中恢复。
4. 最后才用题干正则兜底。

#### 验收标准

- MCQ 能解析出选项、学生选择、正确选项。
- True/False 能解析出 `True/False` 两个选项和正确项。
- Matching 能解析出左右列、学生配对、正确配对。
- 老记录缺字段时不会报错。
- 解析失败时返回可展示的降级结果，而不是空白页面。

#### 暂不做

- 不改数据库 schema。
- 不接 Chroma。
- 不改知识服务。

### Feat 2：教师端列表页结构化展示

#### 目标

让 dashboard 列表页在有限空间里展示更多关键结构信息。

#### 建议展示

MCQ：

- 题干
- 学生选择，例如 `B. ...`
- 正确选择，例如 `A. ...`

True/False：

- 题干
- 学生选择 `True/False`
- 正确答案 `True/False`

Matching：

- 题干
- 简短显示 `x/y pairs matched`
- 详情页再展开完整配对

#### 验收标准

- 列表页仍然保持可读，不因选项过多撑爆表格。
- 鼠标 hover 或截断标题中能看到更完整内容。
- 搜索结果渲染和普通分页列表渲染一致。

### Feat 3：教师端详情页结构化展示

#### 目标

详情弹窗展示完整题目信息，供教师审阅。

#### 建议展示

MCQ：

- 题干
- A/B/C/D 选项
- 标记学生选择
- 标记正确选项

True/False：

- 题干
- True/False 两项
- 标记学生选择
- 标记正确选项

Matching：

- 左侧 term
- 学生选择的 definition
- 正确 definition
- 每一行显示是否匹配

Short Answer / Fill Blank：

- 保持现有展示
- 可补充 reference answer / key points

#### 验收标准

- 教师无需打开 `ai_feedback` 文本也能看懂题目结构。
- `ai_feedback` 仍保留，作为完整审计文本。
- 教师修改分数和反馈不影响结构化题目展示。

## Phase 2：导出与兜底导入

### Feat 4：真正的 Excel `.xlsx` 导出

#### 目标

将 `export_excel` 从 CSV 改为真正的 `.xlsx`。

#### 建议字段

基础字段：

- Student
- Chapter
- Topic
- Question Type
- Question
- Student Answer
- Correct Answer
- AI Score
- Teacher Score
- AI Feedback
- Teacher Feedback
- Generation Source
- Grading Source
- Source Pages
- Created At

结构化字段：

- Options
- Correct Option
- Matching Submitted Pairs
- Matching Correct Pairs
- Key Points
- Citations

#### 格式建议

- 首行加粗
- 冻结首行
- 自动换行
- 设置基础列宽
- 时间字段格式统一

#### 验收标准

- 下载文件扩展名为 `.xlsx`。
- Excel/WPS 可以直接打开。
- MCQ 选项不会丢失。
- Matching 配对不会只剩 JSON 字符串。
- 老记录缺字段时仍能导出。

### Feat 5：Kahoot 模板导出收口

#### 目标

稳定生成 Kahoot 官方模板格式。

#### 规则

只导出：

- `MCQ`
- `True/False`

不导出：

- `Matching`
- `Fill Blank`
- `Short Answer`

#### 数据解析

优先级：

1. 统一解析层输出的结构化字段
2. `options_or_pairs`
3. `ai_feedback`
4. 题干正则

#### Kahoot 填表规则

- 读取已有 `kahoot_template.xlsx`
- 从模板指定起始行写入
- Question 写题干
- Answer 1-4 写选项
- Time limit 写默认值
- Correct answer(s) 写正确选项编号

#### 注意事项

- 先确定正确答案索引，再截断 Kahoot 选项长度。
- True/False 固定生成两个选项。
- 不合格记录跳过，并统计跳过数量。

#### 验收标准

- 导出文件能被 Kahoot 模板识别。
- 长选项不会导致正确答案错位。
- 结构化记录优先，不依赖正则。
- 老记录能通过兜底逻辑尽量恢复。

### Feat 6：CSV 兜底导入增强

#### 目标

保留 CSV 导入入口，但让它尽量不丢结构。

#### 最小必填字段

- `question`
- `answer`

#### 推荐字段

- `student_name`
- `chapter`
- `chapter_id`
- `question_type`
- `topic`
- `question`
- `answer`
- `options_or_pairs`
- `correct_answer`
- `score`
- `ai_feedback`
- `teacher_feedback`
- `citations_json`

#### 宽容规则

- 支持 `student name` 和 `student_name`
- 支持 `question type` 和 `question_type`
- `options_or_pairs` 如果是 JSON 字符串，尽量原样保存
- 如果 CSV 分列提供 `option_a`、`option_b`、`option_c`、`option_d`，可以组装成 `options_or_pairs`
- 如果提供 `correct_index`，应保存进 `options_or_pairs`

#### 验收标准

- 老 CSV 仍能导入。
- 新 CSV 能保留 MCQ/True-False 的选项结构。
- 导入后教师端详情页能显示结构化信息。
- 导入后 Kahoot 导出能识别合格 MCQ/True-False。

## Phase 3：教师端 Chroma 混合检索

### Feat 7：建立教师记录语义索引层

#### 目标

为教师端 dashboard 搜索建立 Chroma 索引。

#### 架构

MySQL：

- 业务主库
- 保存完整学生记录
- 保存教师反馈
- 保存导出所需字段

Chroma：

- 保存 record id
- 保存 search text embedding
- 保存少量 metadata
- 不作为业务真相来源

#### embedding 模型

默认：

- `BAAI/bge-base-en-v1.5`

使用方式：

- query 侧添加 BGE 检索 instruction
- passage/search text 侧不添加 query instruction

#### search text 组成

建议包含：

- question
- options
- student answer
- correct answer
- topic
- chapter
- question type
- AI feedback
- teacher feedback
- explanation

#### 验收标准

- 新增记录后能在 Chroma 中查到。
- 更新教师反馈后索引同步更新。
- 删除记录后 Chroma 中对应索引删除。
- Chroma 不可用时，教师端搜索能降级到当前关键词/稀疏检索。

### Feat 8：教师端 hybrid search 编排

#### 目标

搜索时融合语义检索和关键词检索。

#### 检索流程

1. 用户输入 query。
2. Chroma 返回语义 topK record ids。
3. 当前关键词/BM25/sparse 检索返回 topK record ids。
4. 合并候选集合。
5. 计算融合分数。
6. 回 MySQL 取完整记录。
7. 用统一解析层返回 dashboard view model。

#### 排序建议

可以先用简单权重：

- semantic score
- keyword score
- exact student name boost
- exact topic/chapter boost
- recent record tie-breaker

后续再加 reranker。

#### 验收标准

- 同义表达能召回相关记录。
- 精确学生名搜索仍然稳定。
- 精确关键词搜索不被语义结果淹没。
- 搜索结果展示结构化题目信息。

## Phase 4：知识服务 RAG 升级

### Feat 9：课程知识库 embedding 索引

#### 目标

将课程材料 chunk 写入向量索引，学生端问答和出题使用 hybrid retrieval。

#### 架构

SQLite：

- 继续保存 documents/pages/chunks/facts/term_pairs metadata

Chroma 或其他向量库：

- 保存 chunk embedding
- 保存 chunk id
- 保存 document/chapter/page metadata

#### 验收标准

- 上传课程材料后生成 chunk embedding。
- 学生提问时先走 hybrid retrieval。
- 返回结果仍带 page/source/citation。
- 向量库不可用时可降级到现有 SQLite 词法检索。

### Feat 10：文档解析增强

#### 目标

逐步解决课程材料中的 PPTX、表格、图片、扫描 PDF 问题。

#### 建议顺序

1. PPTX 文本和表格提取
2. PDF 表格提取
3. PDF layout-aware parsing
4. 图片 caption / OCR
5. 图表摘要

#### 暂不一次性完成

这块建议单独开计划，不和教师端 dashboard 同一轮改。

## 6. 推荐实施顺序

### 第一轮

1. Feat 1：统一记录解析层
2. Feat 2：教师端列表页结构化展示
3. Feat 3：教师端详情页结构化展示

第一轮完成后，教师端审阅体验应明显改善。

### 第二轮

4. Feat 4：真正的 Excel `.xlsx` 导出
5. Feat 5：Kahoot 模板导出收口
6. Feat 6：CSV 兜底导入增强

第二轮完成后，教师端数据导出和兜底导入应稳定。

### 第三轮

7. Feat 7：教师记录 Chroma 索引
8. Feat 8：教师端 hybrid search 编排

第三轮完成后，教师端 dashboard 搜索应具备真正语义召回。

### 第四轮

9. Feat 9：知识服务 embedding 索引
10. Feat 10：文档解析增强

第四轮完成后，再逐步升级学生端 RAG 和课程知识召回。

## 7. 测试策略

### 7.1 记录解析测试

覆盖：

- 新 MCQ 记录
- 老 MCQ 记录
- True/False 记录
- Matching 记录
- 缺 `options_or_pairs` 的 legacy 记录
- `ai_feedback` 中可恢复选项的记录

只测试外部行为：

- 输入一条记录
- 输出稳定 view model

不测试内部正则细节。

### 7.2 教师端展示测试

覆盖：

- dashboard 初始分页列表
- 搜索结果列表
- 详情弹窗

重点断言：

- 选项出现
- 学生答案出现
- 正确答案出现
- Matching 配对出现

### 7.3 Excel 导出测试

覆盖：

- 文件是 `.xlsx`
- 表头正确
- MCQ 选项列存在
- Matching 配对可读
- 空字段不会导致导出失败

### 7.4 Kahoot 导出测试

覆盖：

- MCQ 导出
- True/False 导出
- Matching 被跳过
- Short Answer 被跳过
- 老记录兜底恢复
- 长选项先解析正确答案再截断

### 7.5 CSV 导入测试

覆盖：

- 最小字段导入
- 完整结构字段导入
- option_a/option_b 分列导入
- `options_or_pairs` JSON 字符串导入

### 7.6 Chroma 检索测试

覆盖：

- upsert
- delete
- update after teacher feedback
- Chroma unavailable fallback
- semantic-only query
- exact keyword query

## 8. 风险与规避

### 风险 1：历史数据结构不统一

规避：

- 统一解析层必须宽容。
- 缺字段时不报错。
- 尽量从详细反馈文本恢复。

### 风险 2：展示和导出口径不一致

规避：

- 教师端展示、Excel、Kahoot 都调用同一套解析层。
- 不在导出模块里再单独写一份完整解析逻辑。

### 风险 3：教师修改正确答案后结构不同步

规避：

- 第一阶段先保留文本修改能力。
- 后续可以把正确答案编辑改为结构化编辑。
- Kahoot 导出优先使用结构化字段，但需要明确教师覆盖字段的优先级。

### 风险 4：Chroma 索引和 MySQL 脱节

规避：

- 新增、更新、删除都走统一索引同步函数。
- 增加重建索引脚本。
- health 页面显示未索引记录数量。

### 风险 5：embedding 模型部署慢

规避：

- 使用 `bge-base-en-v1.5`，不先上 large。
- 模型下载作为部署步骤，不在请求时下载。
- Chroma 或 embedding 服务启动时加载本地模型。

## 9. 暂不做事项

第一轮不做：

- Chroma 接入
- 知识服务 RAG 重构
- 数据库 schema 大改
- 删除 CSV 导入
- 替换 MySQL
- 重写学生端练习流程

第二轮不做：

- 教师端复杂 reranker
- 多模型 embedding 对比
- OCR 和 PPTX 解析

第三轮不做：

- 彻底替换现有 SQLite 知识库
- 将 Chroma 作为业务主库

## 10. 最小可交付路径

如果希望最快看到效果，建议只做下面三步：

1. 统一记录解析层。
2. 教师端详情页显示 MCQ / True-False / Matching。
3. Excel 导出改为真正 `.xlsx`。

这三步完成后，即使暂时不上 Chroma，也能明显改善教师端可用性。

