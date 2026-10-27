"""Safely create the canonical empty ResearchVault structure and local config."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from config import REPO_ROOT
from vault_schema import CATEGORIES, FIELDS

DIRECTORIES = (
    "01知识图谱", "01知识图谱/.meta/claims", "01知识图谱/.meta/gaps",
    "01知识图谱/_index", "02阅读笔记", "02阅读笔记/_index", "03原始资料",
    "模板", "模板/知识库模板",
)
DIRECTORIES += tuple(f"{root}/{category}" for root in ("02阅读笔记", "03原始资料") for category in CATEGORIES)

TEMPLATES = (
    ("templates/论文精读模板.md", "模板/论文精读模板.md"),
    ("templates/资料阅读模板.md", "模板/资料阅读模板.md"),
    ("templates/知识库模板/主题模板.md", "模板/知识库模板/主题模板.md"),
    ("templates/知识库模板/概念模板.md", "模板/知识库模板/概念模板.md"),
    ("templates/知识库模板/方法模板.md", "模板/知识库模板/方法模板.md"),
    ("templates/知识库模板/关系模板.md", "模板/知识库模板/关系模板.md"),
    ("templates/知识库模板/争议模板.md", "模板/知识库模板/争议模板.md"),
    ("templates/知识库模板/综合模板.md", "模板/知识库模板/综合模板.md"),
)

CODEX_STARTER_FILES = (
    ("templates/ResearchVault_AGENTS.md", "AGENTS.md"),
    ("templates/ResearchVault_开始使用.md", "00_开始使用.md"),
    ("templates/ResearchVault_knowledge_index.md", "01知识图谱/index.md"),
    ("templates/ResearchVault_literature_index.md", "02阅读笔记/_index/文献索引.md"),
    ("skills/researchvault-reading/SKILL.md", ".agents/skills/researchvault-reading/SKILL.md"),
)


def initialize(root: Path, config_path: Path | None = None, *, with_codex: bool = False,
               enable_style: bool = False) -> list[str]:
    root = root.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    for relative in DIRECTORIES:
        target = root / relative
        if not target.exists():
            target.mkdir(parents=True)
            created.append(f"directory: {target}")
    for source_rel, target_rel in TEMPLATES + (CODEX_STARTER_FILES if with_codex else ()):
        source, target = REPO_ROOT / source_rel, root / target_rel
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            created.append(f"template: {target}")
    destination = config_path or REPO_ROOT / "config.toml"
    if not destination.exists():
        example = (REPO_ROOT / "config.example.toml").read_text(encoding="utf-8")
        example = example.replace('vault_root = ""', f'vault_root = "{root.as_posix()}"')
        destination.write_text(example, encoding="utf-8")
        created.append(f"config: {destination}")
    if enable_style:
        snippet = root / ".obsidian/snippets/researchvault-journal-tags.css"
        snippet.parent.mkdir(parents=True, exist_ok=True)
        if not snippet.exists():
            shutil.copyfile(REPO_ROOT / "assets/researchvault-journal-tags.css", snippet)
            created.append(f"style: {snippet}")
        appearance = root / ".obsidian/appearance.json"
        settings = json.loads(appearance.read_text(encoding="utf-8-sig")) if appearance.exists() else {}
        enabled = settings.setdefault("enabledCssSnippets", [])
        if "researchvault-journal-tags" not in enabled:
            enabled.append("researchvault-journal-tags")
            appearance.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            created.append(f"style setting: {appearance}")
        types_file = root / ".obsidian/types.json"
        types = json.loads(types_file.read_text(encoding="utf-8-sig")) if types_file.exists() else {}
        type_map = types.setdefault("types", {})
        changed = not types_file.exists()
        for label in FIELDS.values():
            if label not in type_map:
                type_map[label] = "multitext" if label in {"标签", "期刊标签"} else "date" if label in {"创建日期", "核验日期"} else "text"
                changed = True
        if changed:
            types_file.write_text(json.dumps(types, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            created.append(f"property types: {types_file}")
    return created


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault-root", type=Path, required=True, help="path for the new or existing Vault")
    parser.add_argument("--config", type=Path, help="local config output (created only when missing)")
    parser.add_argument("--with-codex", action="store_true", help="create missing Codex guidance and starter indexes")
    parser.add_argument("--enable-style", action="store_true", help="explicitly install and enable Obsidian property backgrounds")
    args = parser.parse_args()
    for item in initialize(args.vault_root, args.config, with_codex=args.with_codex, enable_style=args.enable_style):
        print(f"CREATED {item}")
    print("PASS: initialized missing files; existing templates preserved; requested style settings merged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
