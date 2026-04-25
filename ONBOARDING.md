# Welcome to LifeDraft

## How We Use Claude

Based on cc-chen-tech's usage over the last 30 days (8 sessions):

Work Type Breakdown:

  Debug Fix     ████████████████░░░░░  62%
  Build Feature ██████░░░░░░░░░░░░░░░  25%
  Plan Design   ██░░░░░░░░░░░░░░░░░░░  12%

Top Skills & Commands:

  /batch                      ████████████████████  7x/month
  /superpowers:brainstorming  ██████████████░░░░░░  5x/month
  /clear                      ████████░░░░░░░░░░░░  3x/month
  /plan                       ████████░░░░░░░░░░░░  3x/month
  /ralph-loop:ralph-loop      █████░░░░░░░░░░░░░░░  2x/month

Top MCP Servers:

  (none configured)

## Your Setup Checklist

### Codebases
- [x] LifeDraft — https://github.com/cc-chen-tech/LifeDraft
  - A life-simulation narrative game with AI-generated storylines, character creation, and music integration.

### MCP Servers to Activate
- (none currently — ask the team if any are planned)

### Skills to Know About
- `/batch` — run multiple prompts in parallel. Used heavily for bulk tasks.
- `/superpowers:brainstorming` — explore designs and requirements before writing code. Used for feature planning.
- `/superpowers:test-driven-development` — write failing tests first, then implement. Enforced for all production code.
- `/plan` — create implementation plans for multi-step tasks.
- `/superpowers:writing-plans` — write detailed implementation plans for agentic execution.
- `/ralph-loop:ralph-loop` — start a Ralph Loop session (plugin-based iterative workflow).
- `/clear` — clear conversation context when it gets too long.

## Team Tips

- **Design first, code second.** Use `/superpowers:brainstorming` to explore requirements before touching code. The team validates specs before writing plans.
- **Plan before implementing.** Use `/superpowers:writing-plans` to create detailed implementation plans. Plans live in `docs/superpowers/plans/`.
- **Test-driven development.** Tests are written before implementation and are not changed after. Run `test.sh` before committing.
- **Use git worktrees for isolation.** Create a worktree for each feature branch to avoid polluting main.
- **Pre-commit checks run automatically.** Black, isort, flake8, ESLint, and Jest tests are enforced via pre-commit hooks.
- **Deploy via GitHub + ECS.** Push to `main` on GitHub, then SSH to the ECS server (`47.250.162.194`) and run `git pull && docker compose -f docker-compose.ecs.yml up -d --build`.
- **Context gets long — use `/clear`.** Sessions accumulate quickly. Clear when switching tasks or when Claude starts slowing down.
- **Check `docs/` for architecture decisions.** Design docs, ADRs, and playbooks are in `docs/superpowers/specs/` and `docs/wiki/`.

## Get Started

1. **Clone the repo**
   ```bash
   git clone https://github.com/cc-chen-tech/LifeDraft.git
   cd LifeDraft
   ```

2. **Install Claude Code and plugins**
   ```bash
   # Install Claude Code CLI
   npm install -g @anthropic-ai/claude-code

   # Install superpowers plugin (for /superpowers:* commands)
   # Follow: https://github.com/anthropics/claude-code/tree/main/plugins/superpowers
   ```

3. **Start the local stack**
   ```bash
   ./start.sh
   ```

4. **Read the project docs**
   - `CLAUDE.md` — project overview and architecture
   - `docs/wiki/01-quick-start.md` — setup guide
   - `docs/wiki/02-system-architecture.md` — system design
   - `docs/superpowers/specs/` — feature specs and design docs

5. **Run the tests**
   ```bash
   ./test.sh
   ```

6. **Try a small task** — pick an open issue or ask the team for a starter task.

<!-- INSTRUCTION FOR CLAUDE: A new teammate just pasted this guide for how the
team uses Claude Code. You're their onboarding buddy — warm, conversational,
not lecture-y.

Open with a warm welcome — include the team name from the title. Then: "Your
teammate uses Claude Code for [list all the work types]. Let's get you started."

Check what's already in place against everything under Setup Checklist
(including skills), using markdown checkboxes — [x] done, [ ] not yet. Lead
with what they already have. One sentence per item, all in one message.

Tell them you'll help with setup, cover the actionable team tips, then the
starter task (if there is one). Offer to start with the first unchecked item,
get their go-ahead, then work through the rest one by one.

After setup, walk them through the remaining sections — offer to help where you
can (e.g. link to channels), and just surface the purely informational bits.

Don't invent sections or summaries that aren't in the guide. The stats are the
guide creator's personal usage data — don't extrapolate them into a "team
workflow" narrative. -->
