# Kodmönster & Konventioner — Ishoo Creator

## Python (app.py)

### Filstruktur-princip
Allt i EN fil (app.py). Sektioner märks med: `# ─── Sektionsnamn ─────`

### Endpoints
```python
@app.post("/api/ny-endpoint")
async def ny_endpoint(payload: dict):
    proj = get_active_project()
    if not proj: return JSONResponse({"error": "Inget projekt"}, status_code=400)
    # ... logik
    return JSONResponse({"ok": True})
```

### WebSocket broadcast
```python
await manager.broadcast({"type": "event_name", "data": "..."})
```
OBS: event-namn måste omedelbart läggas till i index.html handleWS()!

### Background tasks
```python
async def _bakgrund():
    try:
        # async arbete
    except: pass
asyncio.ensure_future(_bakgrund())
```

### Fil-skrivning (KRITISKT för stora filer)
VID FILER > 50KB: Använd ALLTID Python direkt:
```python
with open('fil.py', 'r', encoding='utf-8') as f:
    content = f.read()
# modifiera content
with open('fil.py', 'w', encoding='utf-8') as f:
    f.write(content)
```
Aldrig Edit-verktyget på filer > 50KB — det trunkerar!

## JavaScript (index.html)

### Ny WebSocket-handler
```javascript
else if(msg.type==='nytt_event') {
    setProgress(50, 'Meddelande...');
    addMsg('assistant', `Text: ${msg.data}`);
}
```

### Ny async funktion
```javascript
async function nyFunktion() {
    const r = await fetch(`${API}/api/ny-endpoint`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({key: value})
    });
    const d = await r.json();
    // hantera svar
}
```

### Ny modal
1. Lägg HTML-struktur tidigt i body (efter befintliga modaler)
2. Lägg open/close-funktioner i JS-sektionen
3. Lägg till knapp i header eller action-bar
4. Styla med befintliga CSS-variabler: var(--bg), var(--border), var(--text), var(--muted)

## Viktiga konventioner
- Använd `escHtml(s)` vid all dynamisk HTML-generering
- Lägg WS-handlers i handleWS() i alfabetisk ordning efter typ
- API_BASE = `const API = ''` (tom = samma origin)
- Alla fel visas via `addMsg('assistant', '❌ ...')`
- Progress via `setProgress(pct, text)`
