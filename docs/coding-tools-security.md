# Coding Tools — Token & Security Requirements

## GitHub Token Scope

The `CodingTools` module requires a **fine-grained Personal Access Token (PAT)** scoped to the target repository.

### Required Permissions

| Permission | Level | Used By |
|-----------|-------|---------|
| Contents | Read & Write | `get_file`, `create_or_update_file`, `push_files`, `create_branch` |
| Pull Requests | Read & Write | `create_pull_request` |
| Issues | Read & Write | `comment_on_issue`, `update_issue_labels` (via GitHubTools) |
| Metadata | Read | Implicit — always included |

### Do NOT use

- Classic PATs with `repo` scope (too broad)
- Tokens with `admin:org`, `delete_repo`, or `workflow` scope
- Tokens shared across multiple services

## Token Rotation

- Tokens are stored in Kubernetes Secrets (`crew-secrets`)
- Rotate every 90 days or on team member offboarding
- Never log token values — reference by key name only

## Rate Limiting

The `CodingTools` module includes automatic retry with exponential backoff:

- **429 Too Many Requests**: Respects `Retry-After` header
- **5xx Server Errors**: Retries with 1s → 2s → 4s backoff
- **Network Timeouts**: Same retry pattern
- **Max retries**: 3 attempts per request

GitHub API limits:
- Authenticated: 5,000 requests/hour
- With 3 agents running 10-min cycles: ~18 API calls/cycle × 3 agents × 6 cycles/hour = ~324 calls/hour (well within limits)

## Kubernetes Secret Structure

```yaml
# llm-api-keys — LLM provider credentials
apiVersion: v1
kind: Secret
metadata:
  name: llm-api-keys
  namespace: my-it-crew
data:
  OPENROUTER_API_KEY: <base64>
  SAMBANOVA_API_KEY: <base64>
  GROQ_API_KEY: <base64>

# mattermost-bot-tokens — per-agent chat identity
apiVersion: v1
kind: Secret
metadata:
  name: mattermost-bot-tokens
  namespace: my-it-crew
data:
  MATTERMOST_TOKEN_NOVA: <base64>
  MATTERMOST_TOKEN_KAI: <base64>
  MATTERMOST_TOKEN_ZARA: <base64>

# crew-secrets — core infrastructure
apiVersion: v1
kind: Secret
metadata:
  name: crew-secrets
  namespace: my-it-crew
data:
  github-token: <base64>
  litellm-api-key: <base64>
```

## Branch Protection

Agents create PRs — they do NOT merge directly to `main`. Ensure:
- Branch protection rule on `main` requires at least 1 review
- Force-push is disabled
- Status checks must pass before merge
