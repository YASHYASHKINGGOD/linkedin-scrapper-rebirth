# Git Versioning — Single‑File Command Guide

This is a **copy‑paste handbook** to manage versions with Git using **Tags + Branches + Worktrees**.

---

## 0) One‑time Setup
```bash
# Install Git
git --version

# (Optional) Global config
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
```

---

## 1) Monorepo Scaffold (Optional but handy)
```bash
mkdir -p ~/apps && cd ~/apps
git init
mkdir -p apps bin .worktrees
```

---

## 2) Helper Scripts (Save/Fork/Run)
Create helpers to save snapshots, fork new branches from tags, and run any version side‑by‑side.

### bin/save_version.sh
```bash
#!/usr/bin/env bash
set -euo pipefail
APP="${1:-}"; VER="${2:-}"; MSG="${3:-"save: $APP $VER"}"
if [[ -z "$APP" || -z "$VER" ]]; then echo "Usage: $0 <app-name> <version> [message]"; exit 1; fi

git rev-parse --git-dir >/dev/null 2>&1 || { echo "Not a git repo"; exit 1; }
git add -A
git commit -m "$MSG" || true   # allow no-op commit
TAG="${APP}-${VER}"
git tag -a "$TAG" -m "$MSG" || { echo "tag exists: $TAG"; }
echo "saved & tagged: $TAG"
```

### bin/fork_version.sh
```bash
#!/usr/bin/env bash
set -euo pipefail
APP="${1:-}"; FROM="${2:-}"; TO="${3:-}"
if [[ -z "$APP" || -z "$FROM" || -z "$TO" ]]; then echo "Usage: $0 <app-name> <from-version> <to-version>"; exit 1; fi
FROM_TAG="${APP}-${FROM}"; NEW_BRANCH="${APP}-${TO}-dev"
git worktree add ".worktrees/${NEW_BRANCH}" "$FROM_TAG"
cd ".worktrees/${NEW_BRANCH}"
git checkout -b "$NEW_BRANCH"
echo "forked $FROM_TAG → branch $NEW_BRANCH at .worktrees/${NEW_BRANCH}"
```

### bin/run_version.sh
```bash
#!/usr/bin/env bash
set -euo pipefail
APP="${1:-}"; VER="${2:-}"
if [[ -z "$APP" || -z "$VER" ]]; then echo "Usage: $0 <app-name> <version>"; exit 1; fi
TAG="${APP}-${VER}"; WT_DIR=".worktrees/${APP}-${VER}"
git worktree add "$WT_DIR" "$TAG" || true
cd "$WT_DIR"
echo "now in $WT_DIR at tag $TAG"
```

Make scripts executable:
```bash
chmod +x bin/*.sh
```

---

## 3) Daily Flow (Cheat‑Sheet)
```bash
# create a dev branch from main
git checkout -b notes-v1.3-dev

# commit as you build
git add -A && git commit -m "feat: canvas pan/zoom"

# freeze and tag a working snapshot
bin/save_version.sh notes v1.3 "save: notes v1.3"

# run a saved version side-by-side via worktree
bin/run_version.sh notes v1.3

# fork a new dev branch from an old tag
bin/fork_version.sh notes v1.2 v1.4
```

---

## 4) Branch/Tag Naming
- **Branches**: `<app>-<semver>-dev` (e.g., `notes-v1.4-dev`).
- **Tags**: `<app>-<semver>` (e.g., `notes-v1.3`). Tags are **immutable snapshots**.

---

## 5) Commit Message Best Practices
- Use conventional prefixes:  
  - `feat:` new feature  
  - `fix:` bug fix  
  - `chore:` infra/config  
  - `docs:` documentation  
  - `refactor:` code restructuring  
  - `test:` adding tests  

- Keep commits atomic: one logical change per commit.  
- Write clear, imperative messages (e.g., `feat: add login API`).

---

## 6) Best Practices
- **Always work on a branch**, never directly on main.  
- **Tag only stable, tested versions**. Tags are permanent.  
- **Use worktrees** to run multiple versions in parallel.  
- **Automate** with helper scripts to reduce human error.  
- **Review** code before tagging; treat tags as releases.  

---

## 7) Recovery
```bash
# list tags & branches
git tag --list
git branch --all

# delete a tag (if really needed)
git tag -d notes-v1.2
git push --delete origin notes-v1.2

# delete a worktree
git worktree remove .worktrees/notes-v1.2-dev
```
