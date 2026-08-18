# My IT Crew

An autonomous AI-powered IT company where specialized agents collaborate, make decisions, and deliver results.

## Architecture

See [plan.md](plan.md) for full architecture documentation.

## Quick Start

```bash
# Install dependencies
pip install -e .

# Set environment variables
export LITELLM_API_BASE=http://litellm.ollama.svc:4000/v1
export LITELLM_API_KEY=your-key
export GITHUB_TOKEN=your-github-token
export GITHUB_REPO=subzone/my-it-crew

# Run the orchestrator
python -m src.orchestrator.main
```

## Agents

| Agent | Role | Status |
|-------|------|--------|
| CEO | Strategic direction, opportunity detection | 📱 Phase 1 |
| CTO | Technical vision, architecture decisions | 📱 Phase 1 |
| Engineer | Implementation, PRs, code reviews | 📱 Phase 1 |

## Communication

Agents communicate via GitHub Issues and Discussions:
- **Issues** — Tasks, bugs, epics, opportunities
- **Discussions** — Strategy, RFCs, standups, cross-team coordination
- **PRs** — Code reviews, implementation delivery