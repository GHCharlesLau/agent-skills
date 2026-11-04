#!/usr/bin/env bash
# Installs skills from this repo into agent skill directories.
# Usage:
#   ./scripts/install.sh                # install into ~/.agents/skills
#   ./scripts/install.sh --claude       # also ~/.claude/skills
#   ./scripts/install.sh --cursor       # also ~/.cursor/skills
#   ./scripts/install.sh --cc-switch    # also ~/.cc-switch/skills
#   ./scripts/install.sh --force        # overwrite existing copies

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SKILLS_SRC="$REPO_ROOT/skills"

if [[ ! -d "$SKILLS_SRC" ]]; then
  echo "skills/ directory not found next to this script ($SKILLS_SRC)" >&2
  exit 1
fi

CLAUDE=0
CURSOR=0
CC_SWITCH=0
FORCE=0

for arg in "$@"; do
  case "$arg" in
    --claude)    CLAUDE=1 ;;
    --cursor)    CURSOR=1 ;;
    --cc-switch) CC_SWITCH=1 ;;
    --force)     FORCE=1 ;;
    *) echo "Unknown option: $arg" >&2; exit 1 ;;
  esac
done

HOME_DIR="${HOME:-}"
if [[ -z "$HOME_DIR" ]]; then
  echo "Cannot determine home directory (\$HOME is empty)" >&2
  exit 1
fi

targets=( "$HOME/.agents/skills" )
if [[ "$CLAUDE" -eq 1 ]]; then targets+=( "$HOME/.claude/skills" ); fi
if [[ "$CURSOR" -eq 1 ]]; then targets+=( "$HOME/.cursor/skills" ); fi
if [[ "$CC_SWITCH" -eq 1 ]]; then targets+=( "$HOME/.cc-switch/skills" ); fi

installed=0
for target in "${targets[@]}"; do
  mkdir -p "$target"
  for skill_dir in "$SKILLS_SRC"/*/; do
    name="$(basename "$skill_dir")"
    dest="$target/$name"
    if [[ -e "$dest" ]]; then
      if [[ "$FORCE" -eq 0 ]]; then
        echo "Skipping $name -> $dest (exists). Use --force to overwrite." >&2
        continue
      fi
      rm -rf "$dest"
    fi
    cp -R "$skill_dir" "$dest"
    echo "Installed $name -> $dest"
    installed=$((installed + 1))
  done
done

echo ""
echo "Done. Installed $installed skill copies."
echo "Note: for zotero-use, run skills/zotero-use/scripts/install_cli.py to provision the CLI binary."
