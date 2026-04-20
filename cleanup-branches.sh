#!/bin/bash

# Branch Cleanup Script for mini-RAG
# Generated: 2026-04-21

set -e

echo "=========================================="
echo "Git Branch Cleanup for mini-RAG"
echo "=========================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Ensure we're on main
echo "Switching to main branch..."
git checkout main
git pull origin main
echo ""

echo "=========================================="
echo "STEP 1: Merged Feature Branches"
echo "=========================================="
echo ""
echo "These branches are fully merged into main:"
echo ""

MERGED_BRANCHES=(
    "001-langchain-prompt-template"
    "feature/nlp-routing"
    "feature/vectordb-provider-interface"
    "feature/llm-provider-interface"
)

for branch in "${MERGED_BRANCHES[@]}"; do
    echo -e "${BLUE}  - $branch${NC}"
done
echo ""

read -p "Delete these merged branches? (y/n): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    for branch in "${MERGED_BRANCHES[@]}"; do
        # Delete local branch
        if git show-ref --verify --quiet refs/heads/$branch; then
            git branch -d $branch 2>/dev/null && echo -e "${GREEN}✓${NC} Deleted local: $branch" || echo -e "${YELLOW}⚠${NC} Could not delete: $branch"
        fi
        
        # Delete remote branch if exists
        if git show-ref --verify --quiet refs/remotes/origin/$branch; then
            git push origin --delete $branch 2>/dev/null && echo -e "${GREEN}✓${NC} Deleted remote: $branch" || echo -e "${YELLOW}⚠${NC} Remote already deleted: $branch"
        fi
    done
    echo -e "${GREEN}✓ Merged branches cleaned up${NC}"
else
    echo -e "${YELLOW}⚠ Skipped merging feature branches${NC}"
fi
echo ""

echo "=========================================="
echo "STEP 2: Old Development Branches"
echo "=========================================="
echo ""
echo "These branches contain old work already in main:"
echo ""

OLD_BRANCHES=(
    "base-app"
    "connect-mongo"
    "mongo-indexing"
    "process-file"
)

for branch in "${OLD_BRANCHES[@]}"; do
    last_commit=$(git log -1 --format="%cd - %s" --date=short $branch 2>/dev/null || echo "N/A")
    echo -e "${BLUE}  - $branch${NC}"
    echo "    Last commit: $last_commit"
done
echo ""
echo -e "${YELLOW}WARNING: These branches will be deleted locally and remotely.${NC}"
echo "Their work is already in main. If unsure, choose 'n' and review manually."
echo ""

read -p "Delete these old branches? (y/n): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    for branch in "${OLD_BRANCHES[@]}"; do
        # Delete local branch (force delete since git doesn't recognize as merged)
        if git show-ref --verify --quiet refs/heads/$branch; then
            git branch -D $branch 2>/dev/null && echo -e "${GREEN}✓${NC} Deleted local: $branch" || echo -e "${YELLOW}⚠${NC} Could not delete: $branch"
        fi
        
        # Delete remote branch if exists
        if git show-ref --verify --quiet refs/remotes/origin/$branch; then
            git push origin --delete $branch 2>/dev/null && echo -e "${GREEN}✓${NC} Deleted remote: $branch" || echo -e "${YELLOW}⚠${NC} Remote already deleted: $branch"
        fi
    done
    echo -e "${GREEN}✓ Old branches cleaned up${NC}"
else
    echo -e "${YELLOW}⚠ Skipped old branches${NC}"
fi
echo ""

echo "=========================================="
echo "STEP 3: Cleanup Remote Tracking"
echo "=========================================="
echo ""
echo "Removing stale remote-tracking branches..."
git fetch --prune origin
git remote prune origin
echo -e "${GREEN}✓ Remote tracking cleaned${NC}"
echo ""

echo "=========================================="
echo "Current Branch Status"
echo "=========================================="
echo ""
git branch -vv
echo ""

echo "=========================================="
echo "✅ Cleanup Complete!"
echo "=========================================="
echo ""
echo "Recommendations:"
echo "  1. Use numbered branches for Spec Kit features: 001-feature-name"
echo "  2. Use descriptive names: 002-user-authentication"
echo "  3. Delete branches after merging to main"
echo "  4. Keep main clean and always deployable"
echo ""
