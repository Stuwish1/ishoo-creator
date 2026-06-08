# Arkitektur — Ishoo Creator v6

## app.py — FastAPI Backend

### Konfiguration & State (rad 1-110)
- `DEFAULT_AGENTS` — lista med 10 agent-definitioner
- `DEFAULT_SETTINGS` — API-nycklar, git-info, modeller, max_iterations
- `load_settings()` / `save_settings()` — läser/sparar settings.json
- `_dev_server_proc` / `_dev_server_pid_lock` — dev server state

### Projekthantering (rad 110-180)
- `load_projects()` / `save_projects()` — projects.json
- `project_dir(pid)` — skapar mapp: projects/{pid}/
- `load_memory(pid)` — läser 6 minnesfiler, max 16000 tecken
- `load_features(pid)` / `save_features(pid)` — features.json
- `load_queue(pid)` / `save_queue(pid)` — queue.json

### Git-hantering (rad 180-280)
- `clone_or_pull(github_repo, pid, branch)` — klonar till projects/{pid}/repo/
- `apply_and_push(pid, feature_name, env)` — skriver filer + git commit + push
- `git(rd, *args)` — wrapper för subprocess git-kommandon

### AI-agenter (rad 280-520)
- `SNICKARE_PROMPT` — system-prompt för kodgenerering
- `build_code(spec, pid)` — anropar Claude, returnerar file_changes
- `PROJEKTLEDARE_PROMPT` — system-prompt med FEATURE_KLAR / SYSTEM_KLAR blocks
- `run_agent(agent_def, spec, memory, feedback)` — kör enskild agent
- `SPEC_REVIEWER_PROMPT` — kontrollerar spec-tydlighet
- `BUILD_FIX_PROMPT` — fixar byggfel

### API Endpoints (rad 520-1300)
- `POST /api/chat` — Projektledaren
- `POST /api/review` — kör alla 10 agenter parallellt
- `POST /api/build` — Snickaren genererar kod
- `POST /api/push` — skriver filer + git push
- `POST /api/spec-review` — Spec-granskare
- `POST /api/build-verify` — npm build loop med auto-fix
- `POST /api/fix-error` — Felklistraren
- `GET/POST /api/dev-server/start|stop|status` — lokal dev server
- `GET /api/git/log` / `POST /api/git/revert` — versionshistorik
- `POST /api/projects/{id}/onboard` — onboarding-wizard

### WebSocket (rad 553-570)
- `manager.broadcast(data)` — sänder till alla anslutna klienter
- Event-typer: pipeline_start, agent_status, pipeline_done, build_start, build_done, push_done, build_verify_*, revert_done, architecture_updated

## index.html — Frontend

### State-variabler (rad 620-640)
```javascript
let appState = 'idle'; // idle | pending_review | reviewed | built
let currentFeature, currentSpecObj, currentDiffs;
let chatHistory, onboardingProjectId, onboardingHistory;
let previewUrls, previewEnv, devServerRunning;
```

### Kritiska funktioner
- `handleWS(msg)` — WebSocket-händelsehanterare (rad ~660)
- `sendMessage()` — skickar chat, hanterar feature_detected + onboarding
- `startReview()` — spec-review → agent pipeline
- `startBuild()` — Snickaren bygger kod
- `startBuildVerify()` — npm build verifiering
- `confirmPush()` — godkänn och pusha
- `showDiffModal(feature, diffs, summary)` — visar koddiff

### Modaler
- `diffModal` — koddiff + Verifiera/Pusha knappar
- `previewModal` — Vercel dev/prod + lokal dev server
- `errorModal` — Felklistraren
- `historyModal` — Versionshistorik + revert
- `settingsModal` — API-nycklar, agenter, projekt-inställningar
