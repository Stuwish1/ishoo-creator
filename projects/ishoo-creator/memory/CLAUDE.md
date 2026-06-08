# Ishoo Creator v6 — Spec-driven Edition

## Vad är detta
Ishoo Creator är ett lokalt AI-drivet byggverktyg som hjälper till att bygga webbapplikationer via en multi-agent pipeline. Det är byggt i Python (FastAPI) + vanilla JavaScript.

## GitHub
Stuwish1/ishoo-creator

## Tech Stack
- **Backend:** Python 3.11+ / FastAPI / Uvicorn / WebSocket
- **AI:** Anthropic Claude API (claude-sonnet-4-6 / claude-haiku-4-5) + Ollama (lokal RTX 3080)
- **Frontend:** Vanilla JavaScript (ES6+) / HTML5 / CSS variables
- **Git:** subprocess + GitHub REST API direkt i UI

## Arkitektur — två filer
Hela systemet bor i TWO filer:
- `app.py` — FastAPI backend (~1680 rader)
- `index.html` — komplett UI (~1650 rader)

## 9 Agenter (DEFAULT_AGENTS)
| Agent | Modell | Roll |
|-------|--------|------|
| Säkerhetsansvarig | sonnet | SQL injection, XSS, RLS, auth |
| DBA | ollama:qwen2.5-coder:7b | Migrationer, index, N+1 |
| Konfliktgranskare | ollama:qwen2.5-coder:7b | Duplikat, namnkonflikter |
| UX + Buggletare | haiku | Edge cases, loading states |
| Arkitektur | sonnet | Separation of concerns, hooks |
| Prestandagranskare | ollama:qwen2.5-coder:7b | Re-renders, bundles, memoization |
| Testgranskare | ollama:qwen2.5-coder:7b | Saknade tester, felflöden |
| Mobilanvändare | ollama:llama3.2:3b | Touch, liten skärm, långsamt nät |
| Besiktningsman | sonnet | Aggregerar, godkänner/avvisar |

Ollama fallback: om Ollama inte svarar → automatisk fallback till haiku.

## Pipeline-flöde
1. Spec-granskning (/api/spec-review) — stoppar om spec är otydlig
2. Agenter kör parallellt (ThreadPoolExecutor)
3. Besiktningsman aggregerar
4. Snickaren bygger kod om godkänd
5. Diff visas — användaren granskar
6. Build-verify (/api/build-verify) — npm build + auto-fix
7. Push till GitHub via /api/push

## Branch-strategi
- `main` — stabil version
- `dev` — aktiv utveckling (Snickaren pushar hit)

## Kritiska regler
- settings.json får ALDRIG committas
- Ny endpoint → uppdatera BÅDE app.py OCH index.html
- WebSocket-event-namn måste matcha exakt
- Filer > 67KB: använd Python direct write, ALDRIG Edit-verktyg
- Alla endpoints MÅSTE definieras FÖRE if __name__=="__main__": blocket
