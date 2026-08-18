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