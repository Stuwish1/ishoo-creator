# Dataschema — Ishoo Creator

*Ishoo Creator använder JSON-filer lokalt, ingen databas.*

## settings.json (root)
```json
{
  "api_key": "sk-ant-...",
  "github_token": "ghp_...",
  "git_name": "Ishoo Creator",
  "git_email": "creator@ishoo.se",
  "dev_branch": "dev",
  "prod_branch": "main",
  "max_iterations": 3,
  "model_projektledare": "claude-sonnet-4-6",
  "model_snickare": "claude-sonnet-4-6",
  "model_sonnet": "claude-sonnet-4-6",
  "model_haiku": "claude-haiku-4-5-20251001",
  "agents": [{ "id": "...", "name": "...", "emoji": "...", "model": "sonnet|haiku", "enabled": true, "prompt": "..." }]
}
```

## projects.json (root)
```json
{
  "active": "projekt-id",
  "projects": [{ "id": "slug", "name": "...", "description": "...", "github": "user/repo", "created": "ISO-datum" }]
}
```

## projects/{pid}/features.json
```json
[{ "id": 1, "name": "...", "phase": "MVP|v1|v2", "status": "Planerad|Granskas|Byggs|I dev|Klar", "spec": {...}, "created": "ISO-datum" }]
```

## projects/{pid}/queue.json
```json
[{ "id": 1, "name": "...", "phase": "MVP", "description": "...", "from_suggestion": false, "added": "ISO-datum" }]
```

## projects/{pid}/pending_changes.json
```json
{ "feature": "Feature-namn", "files": [{ "path": "src/...", "action": "create|modify|delete", "content": "..." }] }
```

## projects/{pid}/memory/*.md
Sex prioriterade minnesfiler: CLAUDE.md, SCHEMA.md, PATTERNS.md, ARCHITECTURE.md, DECISIONS.md, FEATURES.md
