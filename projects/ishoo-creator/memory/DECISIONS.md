# Arkitekturbeslut — Ishoo Creator

*Varje viktigt beslut loggas här så agenter aldrig ifrågasätter det igen.*

| Datum | Beslut | Alternativ som övervägdes | Motivering |
|-------|--------|--------------------------|------------|
| 2026-06-08 | En fil per lager (app.py + index.html) | Separata moduler, React frontend | Enklare att underhålla, inga build-steg, enklare för Snickaren att modifiera |
| 2026-06-08 | Vanilla JS istället för React | React, Vue, Svelte | Inga beroenden, inga build-steg, Snickaren kan modifiera direkt |
| 2026-06-08 | FastAPI + WebSocket | Flask, Django, Express | Async-stöd, WebSocket inbyggt, snabb |
| 2026-06-08 | Anthropic Claude direkt (ingen CrewAI) | CrewAI, OpenHands, LangChain | Full kontroll, inga beroenden, bättre felsökning |
| 2026-06-08 | Python subprocess för git | GitPython, PyGit2 | Inga extra beroenden, enkel att felsöka |
| 2026-06-08 | settings.json utanför git | .env, hårdkodade värden | Enkelt UI-redigerbart, flexibelt per maskin |
