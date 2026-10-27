# ResearchVault

连接 **Zotero、Obsidian 与 Codex** 的研究资料阅读工作流。

- **Zotero** 管理论文原件、PDF、书目信息与批注。
- **Obsidian** 保存中文阅读笔记及知识图谱。
- **Codex** 根据明确请求读取资料、核验原文、生成笔记，并回答后续问题。

本仓库发布工作流代码、Skills、模板和样式，不包含个人论文库、阅读笔记、PDF、本机配置或凭据。命令行工具负责文件、元数据与证据路由，研究分析由阅读者或已配置的Agent完成。

## 目录与资料路由

```text
ResearchVault/
├── 01知识图谱/              # 跨资料的概念、方法、关系与综合
├── 02阅读笔记/              # 按类别和主题保存阅读笔记
│   ├── 网页/  论文/  笔记/  收件箱/
│   └── 数据/  日记/  书籍/  附件/
├── 03原始资料/              # 同样的八类目录；默认只读
├── 模板/
│   ├── 论文精读模板.md
│   ├── 资料阅读模板.md
│   └── 知识库模板/
├── .agents/skills/researchvault-reading/
└── .research-tools/Zotero-Analytical-Workflow-Skills/
```

Zotero论文笔记进入 `02阅读笔记/论文/<集合>/<原始标题>.md`。其他资料按来源目录对应：

```text
03原始资料/书籍/神经科学/某本书.pdf
             ↓ 阅读并生成笔记
02阅读笔记/书籍/神经科学/笔记标题.md
```

新增主题子目录时继续保留相同相对目录。已有同源笔记时原位补全，保留人工判断。

## 核心约定

1. **03原始资料默认只读。** 未经用户明确允许，不新增、修改、覆盖、重命名、移动或删除其中内容。“精读”“总结”“生成笔记”不自动授权写入原始资料；转换使用目录外临时工作区。
2. **普通问答默认只读。** 先查阅读笔记，证据不足再定向查原文。检索片段是候选证据，不能自动视为结论已成立。
3. **论文标题保持原文。** 英文论文使用英文原题，中文论文使用中文原题；已有笔记路径保留，避免破坏引用。
4. **18项中文属性。** 类型、标题、作者、期刊标签、标签、年份、创建日期、主题、研究对象、数据来源、研究方法、核心变量、主要发现、研究关联、原文链接、文献集合、原始资料路径、核验日期。
5. **身份与引文可追溯。** 父条目键、PDF附件键、库身份与DOI等保存在隐藏元数据中。关键引文和页码必须核对原文，缺失时如实说明。
6. **精读保持精简。** 方法分析围绕六项问题；结论采用“主要发现 n + 原文引用 n”配对并注明页码。

期刊标签来自Zotero期刊名称、相关Tags和Extra。分区和影响因子仅表示库中的元数据快照，不自动声称为最新年度。

## 快速开始

需要Python 3.11+。日常CLI使用标准库；Zotero Desktop用于读取本地文献，Obsidian用于浏览笔记。PyMuPDF、MinerU是可选能力，不自动安装。

推荐把工具放在Vault内部的固定相对位置：

```sh
git clone https://github.com/CL99800/obsidian-zotero-researchvault.git ResearchVault/.research-tools/Zotero-Analytical-Workflow-Skills
cd ResearchVault/.research-tools/Zotero-Analytical-Workflow-Skills
python tools/init_vault.py --vault-root ../.. --with-codex --enable-style
```

Windows可使用 `py -3.11`，macOS/Linux可使用 `python3.11`。

初始化器保留已有模板、笔记和资料，只创建缺少的目录与引导文件。`--with-codex`同时建立项目规则和本地阅读Skill；`--enable-style`显式安装并启用背景样式，合并属性类型设置。不希望改外观时省略该参数。

在Obsidian中打开Vault。在Zotero设置中启用本地API并保持Zotero运行，然后检查：

```sh
python tools/retrieval_gateway.py --vault ../.. doctor
python tools/retrieval_gateway.py --vault ../.. search-zotero --query "paper title"
python tools/retrieval_gateway.py --vault ../.. search-notes --query "研究主题"
```

在Codex中打开Vault，并确认能读取根目录AGENTS.md与 `.agents/skills/researchvault-reading/SKILL.md`。可直接提出：

- “精读Zotero中的某篇论文，按当前模板生成笔记。”
- “阅读03原始资料/书籍/某主题中的这个文件，生成对应笔记。”
- “这篇论文如何处理神经信号与行为数据同步？请核对原文。”

生成的 `config.toml` 仅供本机使用，不提交Git。完整说明见 [Windows快速上手](docs/Windows-Quickstart.md)。

## 工具

| 工具 | 用途 |
| --- | --- |
| `init_vault.py` | 建立目录、模板、项目规则与可选样式 |
| `retrieval_gateway.py` | 笔记优先检索与定向Zotero原文回查 |
| `create_note_draft.py` | 从已确认元数据准备论文草稿 |
| `create_material_note.py` | 按来源目录准备其他资料草稿 |
| `journal_metadata.py` | 识别期刊标签，过滤无关主题标签 |
| `vault_schema.py` | 读取中文属性及隐藏来源身份 |
| `validate_research_vault_literature_links.py` | 检查来源路径、身份及双向链接 |

草稿命令默认不写文件，必须明确传入 `--write`；草稿不等于已精读完成。目录只读限制来自项目规则与工作流约定，并非操作系统级写保护。

## 测试

```sh
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

测试使用临时目录及回环模拟API，不需要真实Zotero库。可选安装PyMuPDF后可运行真实PDF页码提取检查。

## 来源

基于 [cheneternity/Zotero-Analytical-Workflow-Skills](https://github.com/cheneternity/Zotero-Analytical-Workflow-Skills) 整理与扩展，公开基线为提交 `6b3202cfb74b9221c3b8048b1dab99e0a294a496`。扩展包括本地API、中文资料分类、中文属性、原始资料只读约定、精简模板与期刊标签样式。
