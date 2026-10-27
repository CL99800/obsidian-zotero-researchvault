---
name: zotero-analytical-writer
description: "使用 Zotero metadata、批注和可访问的全文证据，按当前 Vault 模板创建或更新中文精读笔记，并确保 Zotero 链接、公式与原文引用真实可追溯。"
---

# Zotero Analytical Writer

## Canonical template

Resolve `vault_root` from the user-specified Vault or the current agent workspace that contains the target Note. For every Note creation or content update, first read the current Vault's own 精读模板 when it exists. Otherwise use the bundled fallback at `../../templates/论文精读模板.md`. The selected template is the structural authority for this task. Start a new Note from it; update an existing Note in place rather than introducing a parallel structure. All output paths must be real paths relative to `vault_root`, never machine-specific examples.

Keep the visible section order exactly as follows:

`基本信息 → 一句话摘要 → 研究对象 → 研究方法（方法概述 → 方法分析） → 数据来源 → 研究结论 → 关联精读笔记 → 我的判断`

Keep the template's table, field labels, heading levels, and frontmatter fields. Replace every retained placeholder with verified content; remove unused optional formula blocks, surplus finding/quote pairs, and placeholder related-note links. Do not add legacy headings such as `研究对象与问题`, `整体流程`, `数据与证据定位`, `局限与后续问题`, or `Zotero信息`. 将方法与数据局限写入精简模板的“优势与局限”“数据与代码”或“我的判断”，不额外增加长篇结构。

`tools/create_note_draft.py` 可以先只用已确认的 Zotero 元数据生成 隐藏元数据中的`note_status: draft` 的新文件；草稿不代表正式精读完成。Writer 必须在阅读真实 Fulltext/PDF 后才能将状态升级。更新已有笔记时保护“我的判断”中的人工内容，不擅自整体重写。

## 职责与语料顺序

Writer 只负责分析层：`metadata + annotations + MinerU Fulltext + 必要时 PDF → 中文 analytical note`。

- Fulltext 是原文证据，分析笔记是中文理解层；不得把二者混为一谈。
- 仍保留现有的 `theme`、`study_area`、`data_source`、`methodology`、`core_variable`、`key_finding`、`relevance`、中文逻辑重构、学术垃圾过滤、公式防乱码、Zotero URI 和 Dataview 刷新逻辑。
- 不负责 PDF→MinerU；缺全文时交给 `zotero-fulltext-archiver`，不要自行伪造原文。
- 若已有正式 Fulltext，先复用并校验，不因 Note 模板修整而重新运行 MinerU。

## Knowledge handoff contract

The Analytical Note is the structural-library layer for later Knowledge synthesis; it is not a substitute for the Knowledge Page template. Preserve machine-readable fields and make the following handoff explicit whenever the Note will feed Knowledge:

- distinguish author-reported findings, methods, limitations, and the writer's interpretation;
- retain the exact `zotero_key`, `note_path`, `fulltext_path`, formulas, quotations, and PDF/Fulltext entry points;
- record which conclusions were checked against Fulltext and which remain Note-only;
- never mark a Knowledge claim as `fulltext_verified` merely because the Note contains a summary;
- if a field or conclusion cannot be located in the Note or Fulltext, write “未在当前材料中定位到可核验原文”，not a reconstructed quote or inferred page number.

When a later Knowledge task asks for “all papers”, the Knowledge Maintainer must read the Note's structured fields and the linked Fulltext independently; the Writer must not collapse the two layers into a single unsupported summary.

## 中文属性与稳定身份

以当前Vault的中文模板为准，可见属性严格为：类型、标题、作者、期刊标签、标签、年份、创建日期、主题、研究对象、数据来源、研究方法、核心变量、主要发现、研究关联、原文链接、文献集合、原始资料路径、核验日期。不要额外添加英文属性或aliases、source、zotero_key等可见字段；后台身份使用`<!-- researchvault-metadata {...} -->`JSON注释，包括父键、附件键、库类型/ID、DOI、原题、笔记路径、处理状态。`tools/vault_schema.py`将中文字段归一化供检索。

论文笔记的标题属性、一级标题和基本信息保留论文原始标题：英文论文用英文原题，中文论文用中文原题，不再强制翻译。新论文笔记文件名默认使用原题（仅清理文件名非法字符）；已有笔记原路径保留，避免改写03原始资料中的反向链接。其他资料的目录对应关系不变，原始资料仍默认只读。Zotero笔记固定进入`02阅读笔记/论文/<集合>/<原始标题>.md`，全文在`03原始资料/论文/<集合>/<zotero_key>.md`。已存在同源笔记原位更新并保护人工判断。

期刊标签使用`tools/journal_metadata.py`从publicationTitle、Tags及Extra识别；不混入主题标签或TLDR，不猜分区/年份/IF。标签为原生列表，样式由researchvault-journal-tags片段提供。中英文字段仅在工具内部兼容，可见属性全中文。

## 原文引用规则

- “主要发现 + 原文引用”中的原文必须真实出现在 MinerU Fulltext 或 Original PDF。
- 严禁根据中文摘要反向生成英文 quote；定位不到时写“未在当前全文中定位到可核验原句”。
- 引用要保留必要上下文，检查否定、条件、稳健性限定、假设和局限。
- PDF 页码只有在可靠映射或实际 PDF 验证后才写入 `zotero://open-pdf/...?...page=` 或写入“PDF 第 n 页”；否则保留 Fulltext 链接并写“PDF 页码未验证”。不能因为 Fulltext 的 `page_mapping: unknown` 就猜页码，也不能因为页码未知而阻止通过原 PDF 直接核验引文。
- 结论区每一条“主要发现”都要紧邻至少一条真实原文引用；先在 MinerU Fulltext 定位，再在 Original PDF 核对上下文、否定、条件、稳健性和页码。找不到原句时明确写“未在当前全文中定位到可核验原句”，不得反向生成 quote。

## 内容与格式约束

- `theme` 概括研究问题；`study_area`、`data_source`、`methodology`、`core_variable`、`key_finding`、`relevance` 必须来自真实材料，不复制大段摘要。
- 过滤作者地址、单位、邮编、邮箱、基金号和排版垃圾；数据与方法缺失时如实说明。
- 公式仅在原文可靠时保留；乱码或残片不强行解释，也不为占位符生成符号拆解。
- 写入前检查 YAML、美元符号配对、`zotero://select/...` 和 PDF/Fulltext 入口。
- 写入前检查标题层级、模板占位符是否清除、结论是否成对、公式是否闭合，以及 `fulltext_path` 与 Note↔Fulltext 双向入口是否存在。
- `关联精读笔记` 只保留与研究问题、方法或结论存在直接关系的真实 Note；没有可确认的关联时，保留章节说明但移除示例链接。

## 写入与索引

1. 先判定是新建还是更新指定 Note；两种情况都先读取当前 Vault 模板或仓库随附模板。更新时允许重排正文以匹配模板，但不得改变稳定身份或制造重复 Note。
2. 在基本信息区的链接行加入 `全文 Markdown：[[03原始资料/论文/<collection>/<zotero_key>]]`（路径存在时），并保留可验证的 Zotero 入口。
3. 新建论文笔记时才刷新四个根 Dataview 索引；更新既有 Note 不触发全库批量重写，但若标题、路径或索引字段变化，定向刷新受影响索引。

## 当前精简模板

方法分析只保留六项：任务与数据、同步与处理、核心方法、结果验证、优势与局限、对我的借鉴。结合用户明确提供的研究背景选择分析重点，但不强行填写论文没有涉及的模块。不设置公式分析或推导占位。研究结论按实际发现自由增减，逐条采用“主要发现 n + 原文引用 n”结构并注明核验页码。已有人工判断保持原内容。
