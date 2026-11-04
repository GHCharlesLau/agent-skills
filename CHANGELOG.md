# Changelog

All notable changes to this skill collection are recorded here, following
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Changed

- Renamed `source-command-travel-guide` → `travel-guide` and rewrote it to be
  more vivid: a clear three-view route system (route-chain + SVG + Leaflet),
  rich interactivity (day stepper, linked views, filters, interactive budget,
  pre-trip checklist) and better attraction image display (gallery + lightbox +
  hover zoom + multi-source fallback).
- `paper-search`: updated to the latest version — added `references/`
  (`pdf-sources.md`, `zotero-filing.md`) and expanded `SKILL.md` and
  `journals.csv`.

### Added

- Initial public release of the `agent-skills` collection:
  - Original skills: `agent-reach`, `source-command-travel-guide`,
    `paper-search`, `sync-docs`.
  - Third-party skills bundled with attribution: `open-kimi-ppt`,
    `scansci-pdf`, `scansci-sort`, `zotero-use`.
- Repository scaffolding: README, LICENSE, THIRD_PARTY notices,
  install scripts for Windows (`scripts/install.ps1`) and macOS/Linux
  (`scripts/install.sh`), and a SKILL.md validation workflow.
