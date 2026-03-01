#!/bin/bash
# Git Helper Scripts for Story2 Project
# Usage: source scripts/git_helpers.sh
# Or run directly: ./scripts/git_helpers.sh <command>

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Get current branch name
get_current_branch() {
    git branch --show-current
}

# Get main branch name (main or master)
get_main_branch() {
    if git show-ref --verify --quiet refs/heads/main; then
        echo "main"
    elif git show-ref --verify --quiet refs/heads/master; then
        echo "master"
    else
        echo "main"
    fi
}

# Create a new feature branch from main
git_feature() {
    local feature_name="$1"
    if [[ -z "$feature_name" ]]; then
        echo -e "${RED}Error: Feature name required${NC}"
        echo "Usage: git_feature <feature-name>"
        echo "Example: git_feature add-user-auth"
        return 1
    fi

    local main_branch=$(get_main_branch)
    local branch_name="feature/${feature_name}"

    echo -e "${BLUE}Creating feature branch: ${branch_name}${NC}"
    git checkout "$main_branch"
    git pull origin "$main_branch"
    git checkout -b "$branch_name"
    echo -e "${GREEN}✓ Created and switched to ${branch_name}${NC}"
}

# Create a bug fix branch
git_fix() {
    local bug_name="$1"
    if [[ -z "$bug_name" ]]; then
        echo -e "${RED}Error: Bug name required${NC}"
        echo "Usage: git_fix <bug-name>"
        echo "Example: git_fix login-timeout"
        return 1
    fi

    local main_branch=$(get_main_branch)
    local branch_name="fix/${bug_name}"

    echo -e "${BLUE}Creating fix branch: ${branch_name}${NC}"
    git checkout "$main_branch"
    git pull origin "$main_branch"
    git checkout -b "$branch_name"
    echo -e "${GREEN}✓ Created and switched to ${branch_name}${NC}"
}

# Create a hotfix branch
git_hotfix() {
    local hotfix_name="$1"
    if [[ -z "$hotfix_name" ]]; then
        echo -e "${RED}Error: Hotfix name required${NC}"
        echo "Usage: git_hotfix <hotfix-name>"
        echo "Example: git_hotfix critical-auth-bug"
        return 1
    fi

    local main_branch=$(get_main_branch)
    local branch_name="hotfix/${hotfix_name}"

    echo -e "${BLUE}Creating hotfix branch: ${branch_name}${NC}"
    git checkout "$main_branch"
    git pull origin "$main_branch"
    git checkout -b "$branch_name"
    echo -e "${GREEN}✓ Created and switched to ${branch_name}${NC}"
}

# Quick commit with conventional commit format
git_qc() {
    local type="$1"
    local message="$2"

    if [[ -z "$type" || -z "$message" ]]; then
        echo -e "${RED}Error: Type and message required${NC}"
        echo "Usage: git_qc <type> <message>"
        echo "Types: feat, fix, docs, style, refactor, test, build, ci, chore, perf"
        echo "Example: git_qc feat 'add user authentication'"
        return 1
    fi

    git commit -m "${type}: ${message}"
}

# Show a nice git status
git_status() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${PURPLE}Branch: $(get_current_branch)${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""

    # Show branch info
    echo -e "${CYAN}Recent commits:${NC}"
    git log --oneline -5 --decorate --color=always
    echo ""

    # Show status
    echo -e "${CYAN}Working tree status:${NC}"
    git status --short
    echo ""

    # Show stash count
    local stash_count=$(git stash list | wc -l)
    if [[ $stash_count -gt 0 ]]; then
        echo -e "${YELLOW}Stashed changes: $stash_count${NC}"
    fi
}

# Show branch tree
git_tree() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${PURPLE}Branch Tree${NC}"
    echo -e "${BLUE}========================================${NC}"
    git log --all --oneline --graph --decorate -15
}

# Merge current branch to main with cleanup
git_merge_main() {
    local current_branch=$(get_current_branch)
    local main_branch=$(get_main_branch)

    if [[ "$current_branch" == "$main_branch" ]]; then
        echo -e "${RED}Error: Already on ${main_branch}${NC}"
        return 1
    fi

    echo -e "${BLUE}Merging ${current_branch} into ${main_branch}...${NC}"

    # Switch to main and pull latest
    git checkout "$main_branch"
    git pull origin "$main_branch"

    # Merge the feature branch
    git merge --no-ff "$current_branch" -m "Merge ${current_branch}"

    if [[ $? -eq 0 ]]; then
        echo -e "${GREEN}✓ Successfully merged ${current_branch} into ${main_branch}${NC}"
        echo ""
        read -p "Delete branch ${current_branch}? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            git branch -d "$current_branch"
            echo -e "${GREEN}✓ Deleted local branch ${current_branch}${NC}"
            read -p "Delete remote branch (if exists)? (y/n) " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                git push origin --delete "$current_branch" 2>/dev/null || echo -e "${YELLOW}No remote branch to delete${NC}"
            fi
        fi
    else
        echo -e "${RED}✗ Merge failed. Resolve conflicts manually.${NC}"
    fi
}

# Quick sync with remote
git_sync() {
    local current_branch=$(get_current_branch)
    echo -e "${BLUE}Syncing ${current_branch} with remote...${NC}"
    git fetch origin
    git pull origin "$current_branch"
    echo -e "${GREEN}✓ Synced${NC}"
}

# Interactive rebase on main
git_rebase_main() {
    local main_branch=$(get_main_branch)
    local current_branch=$(get_current_branch)

    if [[ "$current_branch" == "$main_branch" ]]; then
        echo -e "${RED}Error: Cannot rebase on ${main_branch}${NC}"
        return 1
    fi

    echo -e "${BLUE}Rebasing ${current_branch} on ${main_branch}...${NC}"
    git fetch origin
    git rebase "origin/${main_branch}"
}

# Undo last commit (keep changes)
git_undo() {
    echo -e "${YELLOW}Undoing last commit (keeping changes staged)...${NC}"
    git reset --soft HEAD~1
    echo -e "${GREEN}✓ Last commit undone. Changes are staged.${NC}"
}

# Show diff stats
git_stats() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${PURPLE}Repository Statistics${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""

    # Contributors
    echo -e "${CYAN}Top Contributors (by commits):${NC}"
    git shortlog -sn | head -10
    echo ""

    # File stats
    echo -e "${CYAN}File Statistics:${NC}"
    echo "  Total files: $(git ls-files | wc -l | tr -d ' ')"
    echo "  Python files: $(git ls-files '*.py' | wc -l | tr -d ' ')"
    echo "  JavaScript/TypeScript: $(git ls-files '*.js' '*.ts' '*.jsx' '*.tsx' | wc -l | tr -d ' ')"
    echo "  Total lines: $(git ls-files | xargs wc -l 2>/dev/null | tail -1 | awk '{print $1}')"
    echo ""

    # Recent activity
    echo -e "${CYAN}Recent Activity (last 7 days):${NC}"
    git log --since="1 week ago" --oneline | wc -l | xargs echo "  Commits:"
}

# Clean merged branches
git_clean_branches() {
    local main_branch=$(get_main_branch)

    echo -e "${BLUE}Cleaning up merged branches...${NC}"

    # Switch to main first
    git checkout "$main_branch"
    git pull origin "$main_branch"

    # Get merged branches (excluding main/master and current)
    local merged=$(git branch --merged | grep -v "^\*\|${main_branch}\|master" | sed 's/^[[:space:]]*//')

    if [[ -z "$merged" ]]; then
        echo -e "${GREEN}No merged branches to clean${NC}"
        return 0
    fi

    echo -e "${YELLOW}Merged branches to delete:${NC}"
    echo "$merged" | sed 's/^/  /'
    echo ""
    read -p "Delete these branches? (y/n) " -n 1 -r
    echo

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "$merged" | xargs git branch -d
        echo -e "${GREEN}✓ Cleaned up merged branches${NC}"
    fi
}

# Show help
git_help() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${PURPLE}Git Helper Commands${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    echo -e "${CYAN}Branch Management:${NC}"
    echo "  git_feature <name>     Create feature branch from main"
    echo "  git_fix <name>        Create fix branch from main"
    echo "  git_hotfix <name>     Create hotfix branch from main"
    echo "  git_clean_branches    Delete merged local branches"
    echo ""
    echo -e "${CYAN}Committing:${NC}"
    echo "  git_qc <type> <msg>   Quick commit with conventional format"
    echo "  git_undo              Undo last commit (keep changes staged)"
    echo ""
    echo -e "${CYAN}Merging & Syncing:${NC}"
    echo "  git_merge_main        Merge current branch to main with cleanup"
    echo "  git_sync              Quick pull from remote"
    echo "  git_rebase_main       Rebase current branch on main"
    echo ""
    echo -e "${CYAN}Information:${NC}"
    echo "  git_status            Enhanced git status"
    echo "  git_tree              Show branch tree"
    echo "  git_stats             Repository statistics"
    echo ""
    echo -e "${CYAN}Usage:${NC}"
    echo "  source scripts/git_helpers.sh  # Load all functions"
    echo "  ./scripts/git_helpers.sh help  # Show this help"
    echo ""
    echo -e "${CYAN}Valid commit types:${NC}"
    echo "  feat, fix, docs, style, refactor, test, build, ci, chore, perf, hotfix"
    echo ""
}

# Main script entry point
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    # Script is being run directly
    case "${1:-help}" in
        feature)
            git_feature "$2"
            ;;
        fix)
            git_fix "$2"
            ;;
        hotfix)
            git_hotfix "$2"
            ;;
        qc)
            git_qc "$2" "$3"
            ;;
        status)
            git_status
            ;;
        tree)
            git_tree
            ;;
        stats)
            git_stats
            ;;
        merge-main)
            git_merge_main
            ;;
        sync)
            git_sync
            ;;
        rebase)
            git_rebase_main
            ;;
        undo)
            git_undo
            ;;
        clean)
            git_clean_branches
            ;;
        help|--help|-h)
            git_help
            ;;
        *)
            echo -e "${RED}Unknown command: $1${NC}"
            git_help
            exit 1
            ;;
    esac
fi