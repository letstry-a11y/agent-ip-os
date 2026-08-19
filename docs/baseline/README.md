# Baseline manifest

These files are byte-for-byte repository copies of the approved parent-workspace baselines. They are the durable source for product intent and constraints; future revisions must be added as new versioned files and must not overwrite these copies.

| File | Document version | Document date | SHA-256 |
|---|---|---|---|
| [AI超级IP双人公司商业计划书_v1.md](AI超级IP双人公司商业计划书_v1.md) | Discussion V1.1 | 2026-08-19 | `9B4CD455C682FEA18913D66777E5A2DA7311F4A902B422A11921BDC0E025D585` |
| [AI超级IP全Agent公司技术方案_v1.md](AI超级IP全Agent公司技术方案_v1.md) | V1.1 | 2026-08-19 | `24E7A48B3E5305F2B2497BE9819B4051CD5F647188D7643471A62DAB5B7F66D5` |
| [AI超级IP系统_Codex开发执行计划_v1.md](AI超级IP系统_Codex开发执行计划_v1.md) | V1.0 | 2026-08-19 | `34848C390329E9DBA66C090EDFCD1A854BF4A76433A31A3FFB9D05465CF82630` |

Copy date: 2026-08-19. Source: workspace root files with the same names.

To verify from the repository root in PowerShell:

```powershell
Get-FileHash -Algorithm SHA256 .\docs\baseline\*.md
```

Derived specifications must link to these repository copies, not to the parent directory or chat history.
