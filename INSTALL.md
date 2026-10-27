# 安装

完整说明见 [README](README.md)，Windows操作示例见 [快速上手](docs/Windows-Quickstart.md)。

```sh
git clone https://github.com/CL99800/obsidian-zotero-researchvault.git ResearchVault/.research-tools/Zotero-Analytical-Workflow-Skills
cd ResearchVault/.research-tools/Zotero-Analytical-Workflow-Skills
python tools/init_vault.py --vault-root ../.. --with-codex --enable-style
```

需要Python 3.11+。已有Vault省略`--enable-style`可保留外观设置。初始化不覆盖已有笔记、模板和资料。
