"""Chinese visible note properties with hidden, stable retrieval identity."""
from __future__ import annotations
import json
import re
from pathlib import Path

FIELDS = {
    'type': '类型', 'title': '标题', 'author': '作者', 'journal_tags': '期刊标签',
    'tags': '标签', 'year': '年份', 'created': '创建日期', 'theme': '主题',
    'study_area': '研究对象', 'data_source': '数据来源', 'methodology': '研究方法',
    'core_variable': '核心变量', 'key_finding': '主要发现', 'relevance': '研究关联',
    'zotero_pdf': '原文链接', 'collection': '文献集合',
    'fulltext_path': '原始资料路径', 'verified_on': '核验日期',
}
CATEGORIES = ('网页', '论文', '笔记', '收件箱', '数据', '日记', '书籍', '附件')
NOTE_ROOT = '02阅读笔记'
SOURCE_ROOT = '03原始资料'

def read_fields(path: Path) -> dict[str, str]:
    """Read English legacy fields, Chinese fields and non-visible JSON identity."""
    text = path.read_text(encoding='utf-8-sig')
    result = {}
    identity = re.search(r'<!-- researchvault-metadata\s+(\{.*?\})\s*-->', text, re.S)
    if identity:
        try:
            result.update({k: str(v) for k, v in json.loads(identity.group(1)).items() if not isinstance(v, (list, dict))})
        except (ValueError, TypeError):
            pass
    head = re.match(r'\A---\s*\r?\n(.*?)\r?\n---', text, re.S)
    reverse = {v: k for k, v in FIELDS.items()}
    if head:
        for key, value in re.findall(r'(?m)^([^\s:#][^:\r\n]*):[ \t]*([^\r\n]*)', head.group(1)):
            key, value = key.strip(), value.strip()
            try:
                parsed = json.loads(value)
                value = str(parsed) if not isinstance(parsed, (list, dict)) else value
            except ValueError:
                value = value.strip("'\"")
            normalized = reverse.get(key, key)
            result[normalized] = value
            result[key] = value
    result['type'] = {'论文精读': 'literature-note', '资料阅读': 'material-note'}.get(result.get('type'), result.get('type', ''))
    result.setdefault('note_path', path.name)
    return result

def identity_comment(metadata: dict) -> str:
    value = json.dumps(metadata, ensure_ascii=False, separators=(',', ':'), default=str).replace('--', '\\u002d\\u002d')
    return '<!-- researchvault-metadata ' + value + ' -->'

def render_properties(values: dict) -> str:
    """One-line JSON scalars/lists are valid YAML and preserve non-ASCII values."""
    return '---\n' + '\n'.join(f'{label}: {json.dumps(values.get(key, [] if key in {"tags", "journal_tags"} else ""), ensure_ascii=False, default=str)}' for key, label in FIELDS.items()) + '\n---\n'

def chinese_title(title: str) -> str:
    if not re.search(r'[\u3400-\u9fff]', title or ''):
        raise ValueError('请提供核对后的中文标题（--title-zh）；保留原题用于身份核对，不自动猜译。')
    return title.strip()

def route_material(vault: Path, source: Path, title_zh: str) -> Path:
    vault = vault.resolve()
    raw = (vault / SOURCE_ROOT).resolve()
    source = source.resolve()
    if not source.is_relative_to(raw) or not source.is_file():
        raise ValueError('资料必须是当前Vault的03原始资料内可读取的文件。')
    safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', chinese_title(title_zh)).strip(' .')[:110]
    relative = source.relative_to(raw)
    target = (vault / NOTE_ROOT / relative.parent / (safe + '.md')).resolve()
    if not target.is_relative_to((vault / NOTE_ROOT).resolve()):
        raise ValueError('笔记路径不能跳出02阅读笔记。')
    return target
