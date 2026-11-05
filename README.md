# agent-skills

A personal collection of AI-agent skills, managed as a single installable
repository. The repository is the **source of truth**; each agent's skill
directory holds an installed copy (see [Install](#install)).

Skills follow the standard skill spec: each skill is a folder containing a
`SKILL.md` with YAML frontmatter (`name`, `description`) plus optional
`references/`, `scripts/`, etc. This format is portable across **Claude Code,
Codex, Cursor, OpenCode, and cc-switch**.

## Skills

| Skill | Description | Origin |
|---|---|---|
| `agent-reach` | Multi-platform research / search skill (15 platforms: X, xiaohongshu, bilibili, Reddit, V2EX, GitHub, YouTube, RSS, …) with backend routing | Original |
| `travel-guide` | 自驾游 / 徒步攻略生成器 — immersive interactive road-trip guide: three route views (chain / SVG / Leaflet with multi-tile fallback), hiking trail details with elevation profiles, real on-location photos with attribution, interactive budget & checklist, and an **offline single-file shareable HTML** (images inlined as base64) | Original |
| `paper-search` | Literature search across OpenAlex / arXiv / PubMed / Crossref, dedup & relevance filtering, exports BibTeX, imports into a Zotero subcollection | Original |
| `sync-docs` | Synchronize content across slides, speaker script, and manuscript; audits stale references and compiles to PDF | Original |
| `open-kimi-ppt` | Create/edit/export presentations using the PPTD format and a local PPTX writer | Third-party (MIT) |
| `scansci-pdf` | Academic PDF retrieval: search, DOI validation, citation export, open-access/institutional routes | Third-party (Apache-2.0, modified) |
| `scansci-sort` | Sort/cleanup workflows for downloaded papers | Third-party (Apache-2.0, modified) |
| `zotero-use` | Zotero library search & live DOCX citation fields (Pyzotero CLI `zot`, ZOTseek MCP) | Third-party (MIT, adapted) |

See [THIRD_PARTY.md](THIRD_PARTY.md) for full attribution and licensing details
for the bundled third-party skills. Each of those skills keeps its original
`LICENSE` file in its own directory.

## Repository layout

```
agent-skills/
├── README.md
├── LICENSE                     # MIT (original skills only)
├── THIRD_PARTY.md              # attribution for bundled third-party skills
├── CHANGELOG.md
├── scripts/
│   ├── install.ps1             # Windows (PowerShell)
│   └── install.sh              # macOS / Linux
└── skills/
    ├── agent-reach/            # SKILL.md + references/
    ├── travel-guide/           # SKILL.md + references/ + scripts/ + examples/
    ├── paper-search/           # SKILL.md + scripts/
    ├── sync-docs/
    ├── open-kimi-ppt/          # SKILL.md + reference/ + scripts/ + tests/
    ├── scansci-pdf/            # SKILL.md + references/ (modified)
    ├── scansci-sort/           # SKILL.md + references/ (modified)
    └── zotero-use/             # SKILL.md + references/ + scripts/ + tests/
```

## Install

### Windows (PowerShell)

```powershell
git clone https://github.com/<owner>/agent-skills.git
cd agent-skills
.\scripts\install.ps1            # installs into ~/.agents/skills
.\scripts\install.ps1 -Claude    # also installs into ~/.claude/skills
.\scripts\install.ps1 -Cursor    # also installs into ~/.cursor/skills
```

### macOS / Linux

```sh
git clone https://github.com/<owner>/agent-skills.git
cd agent-skills
./scripts/install.sh             # installs into ~/.agents/skills
./scripts/install.sh --claude    # also installs into ~/.claude/skills
./scripts/install.sh --cursor    # also installs into ~/.cursor/skills
```

### Post-install notes

- `zotero-use` depends on the `zotero-go-cli` binary, which is **not**
  committed to this repo. After installing the skill, run:

  ```sh
  python skills/zotero-use/scripts/install_cli.py
  ```

  (or `scripts\install_cli.py` on Windows). This downloads and verifies the
  platform-specific release.
- `paper-search` and `zotero-use` read credentials from environment variables
  (`ZOTERO_API_KEY`, `S2_API_KEY`, etc.) — never commit secrets.

## Updating / versioning

- This repo uses [semantic versioning](https://semver.org/) tags
  (`v1.2.0`, …). Tag a release after a meaningful change:

  ```sh
  git tag v1.2.0 && git push origin v1.2.0
  ```

- Record user-visible changes in `CHANGELOG.md` under **Unreleased**.
- A GitHub Action validates that every `skills/*/SKILL.md` has valid YAML
  frontmatter with `name` and `description` on push and PR.
- GitHub's secret scanning is enabled on public repos — still, double-check
  diffs before pushing (especially `scripts/` and `references/`).

## License

Original skills in this repo are licensed under the MIT License
(see [LICENSE](LICENSE)). Bundled third-party skills remain under their own
licenses (see `skills/<name>/LICENSE` and [THIRD_PARTY.md](THIRD_PARTY.md)).
