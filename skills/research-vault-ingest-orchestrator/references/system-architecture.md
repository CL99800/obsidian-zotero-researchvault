# ResearchVault production architecture

```text
Zotero parent item (zotero_key)
  + PDF attachment (pdf_key)
        |
        v
03原始资料/论文/<collection>/<zotero_key>.md
  - original-language MinerU archive
  - image assets and reciprocal note link
        |
        v
02阅读笔记/论文/<collection>/<paper>.md
  - Chinese structured single-paper Analytical Note
  - Zotero identity and fulltext_path
        |
        v
01知识图谱/
  - Chinese human-facing derived synthesis
01知识图谱/.meta/
  - claims, gaps, indexes and machine traceability
```

`01知识图谱` is a navigation and synthesis layer, not primary scientific evidence. Evidence must remain traceable as Knowledge → Analytical Note → Fulltext → optional original PDF.

| Layer | Responsibility | Stable identity |
| --- | --- | --- |
| Zotero | Parent metadata and attached source PDF | `zotero_key`, `pdf_key` |
| `03原始资料` | Verbatim source archive and images | `zotero_key`, `pdf_key` |
| `02阅读笔记` | Structured single-paper interpretation | `zotero_key` |
| `01知识图谱` | Cross-paper Chinese synthesis and navigation | source Note links |
| `01知识图谱/.meta` | Claims, gaps and machine-only traceability | claim/gap IDs plus Note-derived identity |
