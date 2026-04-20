# Git Branch Strategy for mini-RAG

## Overview

This project uses a **Spec Kit feature-branch workflow** with numbered sequential branches.

## Branch Structure

```
main (protected, always deployable)
  ├── 001-langchain-prompt-template ✓ (merged)
  ├── 002-next-feature (in progress)
  └── 003-future-feature (planned)
```

## Branch Naming Convention

### **Format**: `<number>-<feature-slug>`

**Examples:**
- ✅ `001-langchain-prompt-template`
- ✅ `002-vector-search-optimization`
- ✅ `003-user-authentication`
- ❌ `feature/something` (deprecated pattern)
- ❌ `my-branch` (no number)

### **Numbering:**
- Start at `001` and increment sequentially
- Use 3-digit zero-padded numbers: `001`, `002`, ... `099`, `100`
- Each number corresponds to a spec in `specs/<number>-<feature>/`

## Workflow

### 1. Starting a New Feature

```bash
# Update main
git checkout main
git pull origin main

# Create new feature branch
git checkout -b 002-feature-name

# Create spec directory
mkdir -p specs/002-feature-name
```

### 2. Development Cycle

```bash
# Create specification
# ... work on specs/002-feature-name/spec.md
git add specs/002-feature-name/spec.md
git commit -m "spec: define requirements for 002-feature-name"

# Create plan
# ... work on specs/002-feature-name/plan.md
git add specs/002-feature-name/plan.md
git commit -m "plan: create implementation plan for 002-feature-name"

# Generate tasks
# ... work on specs/002-feature-name/tasks.md
git add specs/002-feature-name/tasks.md
git commit -m "tasks: generate task list for 002-feature-name"

# Implement
# ... make code changes
git add src/
git commit -m "feat: implement core functionality"

# Push regularly
git push -u origin 002-feature-name
```

### 3. Before Merging

```bash
# Ensure main is up to date
git checkout main
git pull origin main

# Update your branch
git checkout 002-feature-name
git rebase main  # or: git merge main

# Test everything works
# ... run tests, verify functionality

# Push (use --force-with-lease if rebased)
git push origin 002-feature-name --force-with-lease
```

### 4. Merging to Main

```bash
# Switch to main
git checkout main
git pull origin main

# Merge feature (creates merge commit)
git merge 002-feature-name --no-ff

# Push to remote
git push origin main
```

### 5. Post-Merge Cleanup

```bash
# Delete local branch
git branch -d 002-feature-name

# Delete remote branch
git push origin --delete 002-feature-name

# Clean up tracking references
git fetch --prune origin
```

## Branch Types

| Type | Pattern | Purpose | Example |
|------|---------|---------|---------|
| **Main** | `main` | Production-ready code | `main` |
| **Feature** | `<nnn>-<feature>` | New feature development | `001-langchain-templates` |
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
- Create a new branch for each feature/spec
- Commit frequently with meaningful messages
- Push to remote regularly
- Delete branches after merging
- Use pull requests for team reviews (optional)
- Tag releases: `git tag v1.0.0`

### ❌ DON'T:
- Commit directly to `main` (unless hotfix)
- Keep stale branches after merge
- Use generic commit messages ("fix", "update")
- Commit sensitive data (.env, keys)
- Force push to `main` or shared branches
- Rebase public/shared branches

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
git diff main..002-feature-name

# See what's not in main
git log main..002-feature-name --oneline
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

Each numbered branch corresponds to a spec directory:

```
Branch: 001-langchain-prompt-template
   ↓
Spec: specs/001-langchain-prompt-template/
      ├── spec.md
      ├── plan.md
      ├── tasks.md
      └── ...
```

This creates a clear mapping between specifications and implementation branches.

## Questions?

- Review commit history: `git log --oneline --graph`
- Check branch status: `git status`
- See branch list: `git branch -vv`
- Get help: `git help <command>`

---

**Last Updated**: 2026-04-21
**Project**: mini-RAG
**Workflow**: Spec Kit Feature Branches
