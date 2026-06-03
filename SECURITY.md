# Security Policy

## Reporting a vulnerability

If you discover a security issue, please **do not** open a public GitHub issue with exploit details. Open a private security advisory on the repository or contact the maintainers directly.

## Secrets and local configuration

Never commit:

- `.env` or any file with real API keys, JWT secrets, or database passwords
- `scripts/llama-paths.local.bat` (machine-specific paths)
- Docker volumes, model weights (`.gguf`), or user data exports

Use `.env.example` as a template and generate unique values for every deployment.

## Before your first push

1. Confirm `.env` is ignored: `git check-ignore -v .env`
2. Search the staging area: `git grep -i "api_key\|secret\|password" --cached` (should only hit placeholders and examples)
3. If a secret was ever committed, rotate it and rewrite history (`git filter-repo` or BFG) before publishing

## Operational notes

- `LITELLM_MASTER_KEY` protects the LiteLLM proxy; LibreChat uses the same value for the custom endpoint.
- `X-User-Id` is enforced fail-closed (`jean` | `tati` by default); do not weaken allowlists in production.
- AnythingLLM API keys are created in the AnythingLLM UI; store them only in `.env`.
