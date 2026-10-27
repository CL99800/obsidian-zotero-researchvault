"""Build journal badges from Zotero's existing fields without external lookups."""
from __future__ import annotations

import re


def journal_metadata(data: dict) -> dict:
    """Journal-related tags take precedence over Extra for the same category.

    Values are snapshots from the library, not a verification of current rankings.
    Unknown Extra fields (including TLDR) and ordinary topic tags are excluded.
    """
    found: dict[str, str] = {}
    sources: list[str] = []
    journal = str(data.get('publicationTitle') or data.get('publication_title') or '').strip()
    if journal:
        found['journal'] = journal
        sources.append('publicationTitle')

    patterns = [
        ('jcr', r'^(?:JCR(?:分区)?\s*[:：-]?\s*)(Q[1-4])\b', 'JCR {}'),
        ('cas', r'^(?:中科院分区(?:升级版)?|中科院|CAS(?:分区)?)\s*[:：-]?\s*(.+)$', '中科院 {}'),
        ('if5', r'^(?:5\s*年影响因子|5\s*年\s*IF|5[- ]?year\s*(?:IF|impact factor))\s*[:：=]?\s*(\d+(?:\.\d+)?)\s*$', '5年IF {}'),
        ('if', r'^(?:影响因子|IF|impact factor)\s*[:：=]?\s*(\d+(?:\.\d+)?)\s*$', 'IF {}'),
        ('quality', r'^南农高质量\s*[:：-]?\s*(.+)$', '南农高质量 {}'),
    ]

    def accept(value: str, source: str) -> None:
        value = value.strip().lstrip('#').strip()
        for category, pattern, fmt in patterns:
            match = re.match(pattern, value, re.IGNORECASE)
            if match:
                result = match.group(1).strip()
                # Never interpret a missing or "unavailable" value as a real grade.
                if result.casefold() in {'', '-', '--', 'n/a', 'na', 'none', '无', '未收录', '未知'}:
                    return
                if category not in found:
                    found[category] = fmt.format(result.upper() if category == 'jcr' else result)
                    if source not in sources:
                        sources.append(source)
                return

    for tag in data.get('tags') or []:
        value = tag.get('tag', '') if isinstance(tag, dict) else str(tag)
        accept(value, 'tags')
    for line in str(data.get('extra') or '').splitlines():
        accept(line, 'extra')
    order = ['journal', 'jcr', 'cas', 'if', 'if5', 'quality']
    return {
        'publication_title': journal,
        'journal_tags': list(dict.fromkeys(found[k] for k in order if k in found)),
        'journal_tags_source': sources,
    }
