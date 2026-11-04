# Installs skills from this repo into agent skill directories.
# Usage:
#   .\scripts\install.ps1               # install into ~/.agents/skills
#   .\scripts\install.ps1 -Claude       # also ~/.claude/skills
#   .\scripts\install.ps1 -Cursor       # also ~/.cursor/skills
#   .\scripts\install.ps1 -CCSwitch     # also ~/.cc-switch/skills
#   .\scripts\install.ps1 -Force        # overwrite existing copies

param(
    [switch]$Claude,
    [switch]$Cursor,
    [switch]$CCSwitch,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$SkillsSrc = Join-Path $RepoRoot "skills"

if (-not (Test-Path $SkillsSrc)) {
    Write-Error "skills/ directory not found next to this script ($SkillsSrc)"
    exit 1
}

$UserProfileDir = $env:USERPROFILE
if (-not $UserProfileDir) {
    $UserProfileDir = Join-Path $HOME ""  # fallback for non-Windows PowerShell
}

# Default target: Codex / OpenCode harness skills directory
$targets = [System.Collections.Generic.List[string]]::new()
$targets.Add((Join-Path $UserProfileDir ".agents\skills"))
if ($Claude)    { $targets.Add((Join-Path $UserProfileDir ".claude\skills")) }
if ($Cursor)    { $targets.Add((Join-Path $UserProfileDir ".cursor\skills")) }
if ($CCSwitch)  { $targets.Add((Join-Path $UserProfileDir ".cc-switch\skills")) }

$installed = 0
foreach ($target in $targets) {
    New-Item -ItemType Directory -Force -Path $target | Out-Null
    foreach ($skillDir in Get-ChildItem -LiteralPath $SkillsSrc -Directory) {
        $dest = Join-Path $target $skillDir.Name
        if (Test-Path $dest) {
            if (-not $Force) {
                Write-Warning "Skipping $($skillDir.Name) -> $dest (exists). Use -Force to overwrite."
                continue
            }
            Remove-Item -LiteralPath $dest -Recurse -Force
        }
        Copy-Item -LiteralPath $skillDir.FullName -Destination $dest -Recurse -Force
        Write-Host "Installed $($skillDir.Name) -> $dest"
        $installed++
    }
}

Write-Host ""
Write-Host "Done. Installed $installed skill copies."
Write-Host "Note: for zotero-use, run skills/zotero-use/scripts/install_cli.py to provision the CLI binary."
