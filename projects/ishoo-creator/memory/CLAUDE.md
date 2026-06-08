# Ishoo Creator v6 — Spec-driven Edition

## Vad är detta
Ishoo Creator är ett lokalt AI-drivet byggverktyg som hjälper till att bygga webbapplikationer via en multi-agent pipeline. Det är byggt i Python (FastAPI) + vanilla JavaScript.

## GitHub
Stuwish1/ishoo-creator

## Tech Stack
- **Backend:** Python 3.11+ / FastAPI / Uvicorn / WebSocket
- **Frontend:** Vanilla JavaScript (ES6+) / HTML5 / CSS (CSS variables)
- **AI:** Anthropic Claude API (claude-sonnet-4-6 / claude-haiku-4-5)
- **Git:** subprocess + GitHub REST API

## Arkitektur — två filer
Hela systemet bor i **TWO filer**:
- `app.py` — FastAPI backend (~1500 rader)
- `index.html` — komplett UI i en fil (~1490 rader)

## Branch-strategi
- `main` — stabil version
- `dev` — aktiv utveckling (Snickaren pushar hit)
- Aldrig pusha direkt till main utan genomgång

## Personas / Användare
- **Stiven** — grundare, semi-teknisk, bygger appar med AI-hjälp
- Vill ha full kontroll men minimal friktion
- Arbetar på Windows 11

## Kritiska Affärsregler
- settings.json får ALDRIG committas (innehåller API-nycklar)
- Varje ändring i app.py MÅSTE ha sin motsvarighet i index.html om det gäller ny endpoint eller WS-event
- WebSocket-event-namn måste matcha exakt mellan backend och frontend
- Filer > 67KB: använd ALLTID Python direct write, aldrig Edit-verktyg direkt
