# flow.kaleb.one

Morning dashboard & day planner for the kaleb.one ecosystem.

Aggregates signals from multiple vault domains (health, household, finance, projects) into a single Liquid Glass dashboard.

## Architecture

- **Source**: `triursa/second-brain-vault` domains (health, household, finance, projects, ai-tooling)
- **Build**: Python SSG (`scripts/build.py`) reads vault markdown, generates static HTML
- **Deploy**: Cloudflare Pages → `flow.kaleb.one` (Zero Trust Access)

## Local Build

```bash
VAULT_DIR=/path/to/vault/domains OUTPUT_DIR=/tmp/flow-site python3 scripts/build.py
```

## CI/CD

Vault push to any of the above domains triggers an automatic rebuild via `repository_dispatch`.