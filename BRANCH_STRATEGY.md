# Git Branch Strategy for mini-RAG

## Overview

This project uses a **Spec Kit feature-branch workflow** with numbered sequential branches following development chronology.

## Current Branch Structure

```
main (protected, always deployable)
  ├── 001-base-app ✓ (merged)
  ├── 002-process-file ✓ (merged)
  ├── 003-connect-mongo ✓ (merged)
  ├── 004-mongo-indexing ✓ (merged)
  ├── 005-llm-provider ✓ (merged)
  ├── 006-vectordb-provider ✓ (merged)
  ├── 007-nlp-routing ✓ (merged)
  ├── 008-langchain-prompt-template ✓ (merged)
  └── 009-next-feature (planned)
```

All branches 001-008 contain features that have been merged into `main`. They are kept for historical reference and can be cleaned up if desired.

## Branch Naming Convention

### **Format**: `<number>-<feature-slug>`

**Examples:**
- ✅ `001-base-app`
- ✅ `008-langchain-prompt-template`
- ✅ `009-vector-search-optimization`
- ❌ `feature/something` (deprecated pattern)
- ❌ `my-branch` (no number)
- ❌ `001-langchain-prompt-template` (wrong number for chronology)

### **Numbering:**
- Start at `001` and increment sequentially
- Use 3-digit zero-padded numbers: `001`, `002`, ... `099`, `100`
- Numbers follow **development chronology**, not merge order
- Each number can optionally correspond to a spec in `specs/<number>-<feature>/`
- Current highest number: `008` → Next feature: `009`

## Workflow

### 1. Starting a New Feature

```bash
# Update main
git checkout main
git pull origin main

# Create new feature branch (use next available number)
git checkout -b 009-feature-name

# Create spec directory (optional, for Spec Kit workflow)
mkdir -p specs/009-feature-name
```

### 2. Development Cycle

```bash
# Create specification (if using Spec Kit)
# ... work on specs/009-feature-name/spec.md
git add specs/009-feature-name/spec.md
git commit -m "spec: define requirements for 009-feature-name"

# Create plan
# ... work on specs/009-feature-name/plan.md
git add specs/009-feature-name/plan.md
git commit -m "plan: create implementation plan for 009-feature-name"

# Generate tasks
# ... work on specs/009-feature-name/tasks.md
git add specs/009-feature-name/tasks.md
git commit -m "tasks: generate task list for 009-feature-name"

# Implement
# ... make code changes
git add src/
git commit -m "feat: implement core functionality"

# Push regularly
git push -u origin 009-feature-name
```

### 3. Before Merging

```bash
# Ensure main is up to date
git checkout main
git pull origin main

# Update your branch
git checkout 009-feature-name
git rebase main  # or: git merge main

# Test everything works
# ... run tests, verify functionality

# Push (use --force-with-lease if rebased)
git push origin 009-feature-name --force-with-lease
```

### 4. Merging to Main

```bash
# Switch to main
git checkout main
git pull origin main

# Merge feature (creates merge commit)
git merge 009-feature-name --no-ff

# Push to remote
git push origin main
```

### 5. Post-Merge Cleanup (Optional)

```bash
# Option A: Keep branch for reference (current practice)
# Do nothing - branches 001-008 are kept for history

# Option B: Delete merged branch (clean approach)
git branch -d 009-feature-name
git push origin --delete 009-feature-name

# Clean up tracking references
git fetch --prune origin
```

## Branch Types

| Type | Pattern | Purpose | Example |
|------|---------|---------|---------|
| **Main** | `main` | Production-ready code | `main` |
| **Feature** | `<nnn>-<feature>` | New feature development | `008-langchain-prompt-template` |
| **Hotfix** | `hotfix-<issue>` | Emergency production fixes | `hotfix-login-bug` |
| **Archive** | `archive/<branch>` | Archived old branches | `archive/old-experiment` |

## Commit Message Convention

Follow **Conventional Commits**:

```
<type>: <description>

[optional body]

[optional footer]
```

### Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code formatting (no logic change)
- `refactor`: Code restructuring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks
- `spec`: Spec Kit specification
- `plan`: Spec Kit planning
- `tasks`: Spec Kit task generation

### Examples:
```bash
git commit -m "feat: add user authentication middleware"
git commit -m "fix: resolve memory leak in vector search"
git commit -m "docs: update API documentation for new endpoints"
git commit -m "spec: define requirements for user authentication"
```

## Best Practices

### ✅ DO:
- Keep `main` always deployable
- Create a new branch for each feature using next sequential number
- Commit frequently with meaningful messages
- Push to remote regularly
- Decide on branch retention policy: keep for history or delete after merge
- Use pull requests for team reviews (optional)
- Tag releases: `git tag v1.0.0`

### ❌ DON'T:
- Commit directly to `main` (unless hotfix)
- Use generic commit messages ("fix", "update")
- Commit sensitive data (.env, keys)
- Force push to `main` or shared branches
- Rebase public/shared branches
- Skip numbers in branch sequence (use next available number)

## Branch Renaming

If you need to rename a branch to follow the convention:

### Rename Local Branch
```bash
# Rename current branch
git branch -m new-name

# Rename any branch
git branch -m old-name new-name
```

### Rename Local + Remote Branch
```bash
# 1. Rename local
git branch -m old-name new-name

# 2. Delete old remote
git push origin --delete old-name

# 3. Push new branch
git push origin -u new-name
```

### Batch Rename (Use Script)
```bash
# Use the provided script for multiple branches
./rename-branches-numbered.sh
```

## Useful Commands

### View Branch Status
```bash
# List all branches
git branch -a

# Show branches with last commit
git branch -vv

# Show merged branches
git branch --merged main

# Show unmerged branches
git branch --no-merged main
```

### Cleanup
```bash
# Delete local branch
git branch -d <branch-name>

# Force delete local branch
git branch -D <branch-name>

# Delete remote branch
git push origin --delete <branch-name>

# Prune stale remote references
git fetch --prune origin
git remote prune origin
```

### View History
```bash
# Graph view
git log --oneline --graph --all

# Branch comparison
git diff main..009-feature-name

# See what's not in main
git log main..009-feature-name --oneline
```

## Emergency Procedures

### Accidentally Deleted Branch
```bash
# Find the commit hash
git reflog

# Recreate branch
git checkout -b <branch-name> <commit-hash>
```

### Undo Last Commit
```bash
# Keep changes staged
git reset --soft HEAD~1

# Discard changes (DANGEROUS)
git reset --hard HEAD~1
```

### Recover from Bad Merge
```bash
# Abort merge in progress
git merge --abort

# Undo merge (if not pushed)
git reset --hard HEAD~1
```

## Integration with Spec Kit

Some numbered branches correspond to spec directories (when using Spec Kit workflow):

```
Branch: 008-langchain-prompt-template
   ↓
Spec: specs/001-langchain-prompt-template/
      ├── spec.md
      ├── plan.md
      ├── tasks.md
      └── ...
```

**Note:** Branch numbers follow development chronology (001-008), while spec numbers may differ. The `008-langchain-prompt-template` branch corresponds to `specs/001-langchain-prompt-template/` because it was the first feature to use Spec Kit, but the 8th feature developed overall.

## Project History

**Development Timeline:**
1. `001-base-app` - Base application setup
2. `002-process-file` - File processing functionality
3. `003-connect-mongo` - MongoDB connection
4. `004-mongo-indexing` - Database indexing
5. `005-llm-provider` - LLM provider interface
6. `006-vectordb-provider` - Vector database provider
7. `007-nlp-routing` - NLP routing
8. `008-langchain-prompt-template` - LangChain templates (First Spec Kit feature)

All features 001-008 are merged into `main`. Next feature: `009`.

## Questions?

- Review commit history: `git log --oneline --graph`
- Check branch status: `git status`
- See branch list: `git branch -vv`
- Get help: `git help <command>`

## Available Scripts

This repository includes helper scripts for branch management:

- **`cleanup-branches.sh`** - Interactive cleanup of merged branches
- **`rename-branches-numbered.sh`** - Batch rename branches to numbered convention
- **`.cursor/GIT_QUICK_REFERENCE.md`** - Quick command reference

---

**Last Updated**: 2026-04-21  
**Project**: mini-RAG  
**Repository**: https://github.com/AHM215/RAG-APP.git  
**Workflow**: Spec Kit Feature Branches with Chronological Numbering  
**Current Branch**: 001-008 (merged), Next: 009
