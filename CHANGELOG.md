# Changelog

All notable changes to this skill collection are recorded here, following
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Changed

- `travel-guide`: major upgrade based on a real end-to-end run (清远梅子坪古道 +
  英西峰林). The skill is now a full toolkit rather than a single prompt:
  - **references/** — `images.md` (multi-source image strategy, Bilibili cover
    workflow, local storage + attribution), `maps.md` (5 tile providers, 7s
    watchdog, init robustness, GCJ-02 vs WGS84), `svg-map.md` (label leader
    lines, `paint-order: stroke`, overlap-detection snippet), `hiking.md`
    (segmented trail book, elevation profile, difficulty scale, retreat plan),
    `shareable.md` (offline single-file export), `html-spec.md` (structure /
    interactions / anti-template visual rules), `qa.md` (delivery gate with
    copy-paste browser checks).
  - **scripts/** — `probe_sources.py` (network/image/tile availability probe),
    `osrm_verify.py` (per-leg OSRM verification + buffer), `download_bili_covers.py`
    (search & download real on-location photos with credits), `build_shareable.py`
    (base64-inline all images → one offline HTML).
  - **examples/qingyuan-meiziping-yingxi/** — complete real deliverable
    (Markdown + interactive HTML + route.svg + image manifest/credits).
- `travel-guide`: 逐日行程卡片默认展开；SVG 示意图标签用引线外移并加白描边衬底，
  交付前用脚本验证「文字-文字 / 文字-节点 0 重叠」。
- Renamed `source-command-travel-guide` → `travel-guide` and rewrote it to be
  more vivid: a clear three-view route system (route-chain + SVG + Leaflet),
  rich interactivity (day stepper, linked views, filters, interactive budget,
  pre-trip checklist) and better attraction image display (gallery + lightbox +
  hover zoom + multi-source fallback).
- `paper-search`: updated to the latest version — added `references/`
  (`pdf-sources.md`, `zotero-filing.md`) and expanded `SKILL.md` and
  `journals.csv`.

### Added

- `travel-guide`: 单文件离线分享版（`build_shareable.py`）——把所有图片压缩后以
  base64 内嵌，解决"只发 HTML 到其他设备图片全裂"的问题；地图瓦片保留远程并新增
  离线提示，引导查看「行程示意图」。
- `travel-guide`: 徒步场景支持（分段路书、海拔剖面、撤退方案、两步路轨迹指引）。

### Fixed

- `travel-guide`: 地图白屏问题——`localStorage` 异常会中断后续脚本，现所有读写
  try/catch，地图初始化整体 try/catch，并加 5 源回退 + 看门狗 + 可见错误提示。

## [0.1.0] — initial release

### Added

- Initial public release of the `agent-skills` collection:
  - Original skills: `agent-reach`, `source-command-travel-guide`,
    `paper-search`, `sync-docs`.
  - Third-party skills bundled with attribution: `open-kimi-ppt`,
    `scansci-pdf`, `scansci-sort`, `zotero-use`.
- Repository scaffolding: README, LICENSE, THIRD_PARTY notices,
  install scripts for Windows (`scripts/install.ps1`) and macOS/Linux
  (`scripts/install.sh`), and a SKILL.md validation workflow.
