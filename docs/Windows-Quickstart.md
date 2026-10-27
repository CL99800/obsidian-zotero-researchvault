# Windows 本地：Zotero + Obsidian + Codex

本仓库的 Agent Skills 负责研究判断、写作和来源核验；Python CLI 负责 Vault 初始化、Zotero 只读连接、证据检索与安全草稿创建。CLI 不会自己调用 AI 模型或编造科研结论。

## 1. 环境

- Windows、Python 3.11+、本机 Codex CLI 或桌面版。
- Zotero Desktop + Zotero Connector，负责管理合法可获取的 PDF。
- Obsidian：可以直接打开任意本地 Markdown 文件夹。
- 可选：`py -m pip install pymupdf`，让 CLI 解析实际 PDF 页码；缺少时可使用 Zotero indexed text，但不可声称已核验 PDF 页码。
- 可选 MinerU：需要将 PDF 转换为结构化 Markdown 时另行安装。

## 2. 新建 Vault

推荐将工具仓库放在Vault内部，便于Codex通过固定相对路径找到它：

```powershell
git clone https://github.com/CL99800/obsidian-zotero-researchvault.git ResearchVault/.research-tools/Zotero-Analytical-Workflow-Skills
cd ResearchVault/.research-tools/Zotero-Analytical-Workflow-Skills
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python tools/init_vault.py --vault-root ../.. --with-codex --enable-style
```

初始化器只创建缺失的目录、模板和Codex引导文件，不覆盖已有研究内容。`--enable-style`显式安装并启用背景样式，合并Obsidian属性类型；省略即可保留原外观。之后在Obsidian中选择 **Open folder as vault**，打开外层ResearchVault目录并阅读`00_开始使用.md`。已有Vault需将克隆目标改为其内部同样的相对位置。

工具仓库内的 `config.toml` 不提交 Git。配置实际 `vault_root` 路径；`zotero_data_dir` 只用于本地 API 不可用时的只读 SQLite fallback。

## 3. 连接 Zotero

在 Zotero Settings → Advanced 启用 **Allow other applications on this computer to communicate with Zotero**。保持 Zotero Desktop 运行，只允许本机访问 `127.0.0.1:23119`，不要向公网开放端口。

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:23119/api/users/0/items?limit=1"
python tools/retrieval_gateway.py doctor
```

403 通常表示本地 API 未启用；连接失败可能是 Zotero 未运行。上述命令只读，不需要 Zotero Web API Key。

## 4. 检索和核验

```powershell
# Vault 还没有笔记时，先按标题/关键词查 Zotero，获得父条目 Key
python tools/retrieval_gateway.py search-zotero --query "building energy"

# 搜索 Obsidian Analytical Notes
python tools/retrieval_gateway.py search-notes --query "建筑能耗"

# 默认先从笔记取得候选证据
python tools/retrieval_gateway.py evidence --key ABCD1234 --query "研究方法"

# 显式要求原文核验：Fulltext → Zotero indexed text → 原始 PDF
python tools/retrieval_gateway.py evidence --key ABCD1234 --query "模型参数" --verify-original

# 真实 PDF 页码核验；没有 PDF/解析器时报告证据不足
python tools/retrieval_gateway.py evidence --key ABCD1234 --query "系数" --require-pdf-page
```

`ABCD1234` 是 Zotero **父条目 Key**，不是 PDF 附件 Key 或 Better BibTeX citekey。检索结果是带来源的候选片段，Codex 仍要核对上下文、限定条件与证据充分性后才能回答。没有索引文字时可通过 PyMuPDF 解析可访问的 PDF；扫描版 PDF 可能需要额外 OCR。

当 Note 的 `note_status` 标为 `draft`、`incomplete` 或 `needs_review` 时，即使笔记有关键词命中，网关也会继续寻找原文；其他 Note 是否证据充分则由 Codex 结合实际问题判断，必要时使用 `--verify-original`。

## 5. 创建论文草稿：默认不写入

```powershell
python tools/create_note_draft.py --key ABCD1234 --collection "建筑环境"
python tools/create_note_draft.py --key ABCD1234 --collection "建筑环境" --write
```

第一条是 dry-run。第二条明确创建新笔记，且不会覆盖已有同 Key Note 或已有目标文件。草稿只写已确认元数据和来源链接，不会伪造研究方法与结论。之后让 `zotero-analytical-writer` Skill 结合真实全文补全。

## 6. 在 Codex 使用

`--with-codex`会建立Vault根目录的`AGENTS.md`和`.agents/skills/researchvault-reading/SKILL.md`，已有文件保留。在Codex中打开Vault后检查规则与Skill是否可读；其他专门Skill位于工具仓库的`skills/`中，按任务需要读取，不需要批量覆盖全局Skill。

Codex需要访问整个Vault及其中的工具仓库。完成上述安装后，可从工具仓库目录启动：

```powershell
codex --cd ../..
```

如果用Codex桌面版，将外层Vault作为工作目录。工作流依赖本机目录访问授权；遇到权限不足时如实报告，不越过限制。

示例提问：

> 基于当前 ResearchVault 项目文件检索：ABCD1234 这篇论文采用什么模型？先查我的精读笔记，不足时进入 Zotero 原文，并标明哪些结果经过原文核验。

## 安全边界

- 原始 PDF 保留在 Zotero；Markdown 全文是可再生的派生材料。
- 默认问答只读，不自动修改 Obsidian、Zotero 数据库或 PDF。
- `03原始资料/`及其子目录默认只读；阅读和生成笔记不授权修改、归档、OCR回写、移动或删除原始资料。需要转换时使用该目录外临时工作区。
- `retrieval_gateway.py` 是轻量词面检索，不负责模型推理、语义充分性判定或生成最终答案。
- Zotero indexed text 的字符位置不能当成 PDF 页码；精确公式、图表与 OCR 疑点需要原 PDF 核验。
- 备份 Vault 与 Zotero 数据。源身份冲突、权限不足或原文缺失时，应报告问题而不是猜测。
