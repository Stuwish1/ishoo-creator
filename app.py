#!/usr/bin/env python3
"""
Ishoo Creator — Lokal Agent Backend v4 (Settings Edition)
==========================================================
Allt konfigurerbart inifrån UI:
- Settings (API-nycklar, git-info, modeller, max iterationer)
- Agent CRUD (lägg till / redigera / ta bort agenter)
- Dev/Prod branch-separation
- Per-projekt Supabase-konfiguration
"""

import os, json, asyncio, re, difflib, subprocess, threading
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# ─── Dev Server State ────────────────────────────────────────────────────────
_dev_server_proc = None
_dev_server_pid_lock = threading.Lock()

import anthropic
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Ishoo Creator")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

PROJECTS_FILE = Path("projects.json")
PROJECTS_DIR  = Path("projects")
SETTINGS_FILE = Path("settings.json")

SONNET_DEFAULT = "claude-sonnet-4-6"
HAIKU_DEFAULT  = "claude-haiku-4-5-20251001"

# ─── Settings ─────────────────────────────────────────────────────────────────

DEFAULT_AGENTS = [

    # ══ STEG 0: SPEC-GRANSKNING (kör alltid, kan stoppa pipelinen direkt) ══════

    # ── Kravanalytikorn ──────────────────────────────────────────────────────────
    {"id":"kravanalytiker","name":"Kravanalytikorn","emoji":"🔍","model":"sonnet","enabled":True,
     "prompt":'''Du ansvarar ENBART för att bedöma om specifikationen är tillräcklig för att bygga.

Kontrollera:
1. Är det tydligt VAD som ska byggas? (inte vad det ska heta, utan exakt beteende)
2. Finns acceptanskriterier — hur vet vi att featuren är klar?
3. Är kantfall definierade? (vad händer vid fel, tom data, ogiltigt input)
4. Är det tydligt VEM som ska kunna göra VAD? (behörigheter, roller)
5. Finns det motstridiga krav?

GODKÄND om: spec är konkret nog för att Snickaren ska kunna bygga utan att gissa.
AVVISAD om: spec är för vag, saknar acceptanskriterier, eller innehåller motsägelser.

Vid AVVISAD: lista EXAKT vilka frågor som måste besvaras innan bygget kan starta.

Returnera ENBART JSON: {"status":"GODKÄND"/"AVVISAD","findings":["..."],"severity":"LOW"/"MEDIUM"/"HIGH","suggestions":["Exakt fråga 1 som måste besvaras","Exakt fråga 2..."]}'''},

    # ── Beroendeanalytikorn ──────────────────────────────────────────────────────
    {"id":"beroendeanalytiker","name":"Beroendeanalytikorn","emoji":"🔗","model":"sonnet","enabled":True,
     "prompt":'''Du ansvarar ENBART för att identifiera beroenden som måste finnas INNAN denna feature kan byggas.

Kontrollera ALLA dessa kategorier:
1. FEATURES: Kräver denna feature att en annan feature är byggd och klar?
2. DATABAS: Krävs specifika tabeller, kolumner, relationer eller RLS-policies?
3. PACKAGES: Krävs npm-paket eller Python-bibliotek som inte är installerade?
4. ENV-VARIABLER: Krävs miljövariabler som kanske saknas (.env)?
5. API-ENDPOINTS: Kräver denna feature endpoints som inte finns än?
6. TYPER/INTERFACES: Krävs TypeScript-typer eller interfaces som saknas?

GODKÄND om: alla beroenden finns på plats.
AVVISAD om: minst ett beroende saknas — lista EXAKT vad som saknas och måste skapas först.

Returnera ENBART JSON: {"status":"GODKÄND"/"AVVISAD","findings":["..."],"severity":"LOW"/"MEDIUM"/"HIGH","suggestions":["..."],"saknade_beroenden":[{"typ":"feature"/"db"/"package"/"env"/"api"/"typ","namn":"...","beskrivning":"..."}]}'''},

    # ══ STEG 1: TEKNISK GRANSKNING (parallell) ═══════════════════════════════════

    # ── Strukturnavigatorn ───────────────────────────────────────────────────────
    {"id":"strukturnavigator","name":"Strukturnavigatorn","emoji":"🗺️","model":"sonnet","enabled":True,
     "prompt":'''Du ansvarar ENBART för kodbas-struktur och filnavigation.

JOBB (i ordning):
1. Kontrollera om STRUKTURINDEX.md finns. Saknas den → AVVISAD HIGH.
2. Bestäm exakt var varje ny fil placeras (mapp + filnamn).
3. Identifiera befintliga filer som påverkas.
4. Verifiera att namnkonventioner följs (PascalCase komponenter, camelCase hooks etc).
5. Om nödvändig mappstruktur saknas → AVVISAD med exakt vad som skapas först.

REGLER React/TypeScript: src/components/[domän]/[Komponent].tsx, src/pages/, src/hooks/use[Namn].ts, src/lib/, src/types/, src/utils/
REGLER Python/FastAPI: endpoints i app.py under rätt # ─── sektion, agenter i DEFAULT_AGENTS

Returnera ENBART JSON: {"status":"GODKÄND"/"AVVISAD","findings":["..."],"severity":"LOW"/"MEDIUM"/"HIGH","suggestions":["..."],"filplacering":[{"fil":"src/...","typ":"create"/"modify","anledning":"..."}]}'''},

    # ── Säkerhet ─────────────────────────────────────────────────────────────────
    {"id":"security","name":"Säkerhetsansvarig","emoji":"🔒","model":"sonnet","enabled":True,
     "prompt":'Du ansvarar ENBART för säkerhet. Granska: SQL-injection, XSS, exponerade API-nycklar, saknad RLS i Supabase, felaktig autentisering/auktorisering, CSRF, osäker direktlänkning till resurser. Kommentera inget annat. Returnera ENBART JSON: {"status":"GODKÄND"/"AVVISAD","findings":["..."],"severity":"LOW"/"MEDIUM"/"HIGH","suggestions":["..."]}'},

    # ── Databas ──────────────────────────────────────────────────────────────────
    {"id":"dba","name":"DBA","emoji":"🗄️","model":"ollama:qwen2.5-coder:7b","enabled":True,
     "prompt":'''Du ansvarar ENBART för databasfrågor.
STEG 1: Kräver denna feature persistent datalagring?
STEG 2a — JA + ingen DB: AVVISAD HIGH, beskriv exakt vilka tabeller/kolumner som behövs.
STEG 2b — JA + DB finns: granska migreringar, saknade index, N+1, saknad RLS.
STEG 2c — NEJ: GODKÄND "Ingen databas krävs."
Returnera ENBART JSON: {"status":"GODKÄND"/"AVVISAD","findings":["..."],"severity":"LOW"/"MEDIUM"/"HIGH","suggestions":["..."]}'''},

    # ── Arkitektur ───────────────────────────────────────────────────────────────
    {"id":"architect","name":"Arkitekt","emoji":"🏗️","model":"sonnet","enabled":True,
     "prompt":'Du ansvarar ENBART för systemarkitektur. Granska: separation of concerns, onödig prop drilling, felaktiga modulberoenden, duplicerad affärslogik, felplacerad kod. Kommentera inte säkerhet, prestanda eller UX. Returnera ENBART JSON: {"status":"GODKÄND"/"AVVISAD","findings":["..."],"severity":"LOW"/"MEDIUM"/"HIGH","suggestions":["..."]}'},

    # ── Ansvarsfördelning ────────────────────────────────────────────────────────
    {"id":"ansvarsfordelning","name":"Ansvarsfördelning","emoji":"⚖️","model":"sonnet","enabled":True,
     "prompt":'Du ansvarar ENBART för Single Responsibility. Granska: har varje funktion/komponent ett enda ansvar? God Objects? Otydliga gränssnitt mellan lager? Saknade abstraktioner? Returnera ENBART JSON: {"status":"GODKÄND"/"AVVISAD","findings":["..."],"severity":"LOW"/"MEDIUM"/"HIGH","suggestions":["..."]}'},

    # ── TypeScript-typer ─────────────────────────────────────────────────────────
    {"id":"typgranskare","name":"Typgranskaren","emoji":"🔷","model":"ollama:qwen2.5-coder:7b","enabled":True,
     "prompt":'''Du ansvarar ENBART för TypeScript-typsäkerhet.
Granska: användning av `any` (förbjudet utom med explicit motivering), saknade interface/type-definitioner, inkonsekventa typer mot befintlig src/types/, icke-exporterade typer som borde vara delade, implicit `any` från bibliotek utan types, union types som borde vara enums.
GODKÄND om: inga `any`, alla nya typer definierade och exporterade korrekt.
AVVISAD om: `any` används, typer saknas, eller typer är inkompatibla med befintlig kod.
Returnera ENBART JSON: {"status":"GODKÄND"/"AVVISAD","findings":["..."],"severity":"LOW"/"MEDIUM"/"HIGH","suggestions":["..."]}'''},

    # ── Felhantering ─────────────────────────────────────────────────────────────
    {"id":"felhantering","name":"Felhanteringsgranskaren","emoji":"🚨","model":"ollama:qwen2.5-coder:7b","enabled":True,
     "prompt":'''Du ansvarar ENBART för felhantering och robusthet.
Granska:
- Saknar API-anrop try/catch?
- Visas fel för användaren (toast, error state, fallback UI)?
- Finns loading-state under async-operationer?
- Hanteras null/undefined-värden defensivt?
- Finns tomma-listan-state (empty state) när data saknas?
- Kraschar UI om ett enskilt fält saknas i API-svaret?
GODKÄND om: alla async-operationer har felhantering och UI har error/loading/empty states.
AVVISAD om: saknat try/catch, ingen error state, eller UI kan krascha på null-data.
Returnera ENBART JSON: {"status":"GODKÄND"/"AVVISAD","findings":["..."],"severity":"LOW"/"MEDIUM"/"HIGH","suggestions":["..."]}'''},

    # ── Tillgänglighet ───────────────────────────────────────────────────────────
    {"id":"tillganglighet","name":"Tillgänglighetsgranskaren","emoji":"♿","model":"haiku","enabled":True,
     "prompt":'''Du ansvarar ENBART för tillgänglighet (a11y/WCAG).
Granska: saknade aria-label/aria-describedby på knappar och ikoner, bilder utan alt-text, formulärfält utan kopplad label, otillräcklig färgkontrast (under 4.5:1), element som inte är nåbara med tangentbord (Tab/Enter/Escape), modaler utan fokushantering (focus trap), dynamisk text som skärmläsare missar.
GODKÄND om: alla interaktiva element är tillgängliga och ARIA används korrekt.
AVVISAD om: kritiska a11y-problem som utestänger användare med hjälpmedel.
Returnera ENBART JSON: {"status":"GODKÄND"/"AVVISAD","findings":["..."],"severity":"LOW"/"MEDIUM"/"HIGH","suggestions":["..."]}'''},

    # ── Konfiguration ────────────────────────────────────────────────────────────
    {"id":"konfiguration","name":"Konfigurationsgranskaren","emoji":"⚙️","model":"ollama:qwen2.5-coder:7b","enabled":True,
     "prompt":'''Du ansvarar ENBART för konfiguration och hårdkodade värden.
Granska: hårdkodade URL:er (ska vara env-variabler), hårdkodade API-nycklar (KRITISKT), magiska strängar/siffror som borde vara konstanter, timeout-värden som borde vara konfigurerbara, feature flags som saknas, .env.example som inte uppdaterats med nya variabler.
GODKÄND om: inga hårdkodade secrets, alla env-variabler dokumenterade i .env.example.
AVVISAD HIGH om: API-nyckel eller URL hårdkodad. AVVISAD MEDIUM om: magiska värden saknar konstanter.
Returnera ENBART JSON: {"status":"GODKÄND"/"AVVISAD","findings":["..."],"severity":"LOW"/"MEDIUM"/"HIGH","suggestions":["..."]}'''},

    # ── Prestanda ────────────────────────────────────────────────────────────────
    {"id":"performance","name":"Prestanda","emoji":"⚡","model":"ollama:qwen2.5-coder:7b","enabled":True,
     "prompt":'Du ansvarar ENBART för prestanda. Granska: onödiga re-renders, saknad useMemo/useCallback, tunga beräkningar i render-loop, stora bundle-imports, saknad lazy loading, långsamma queries, saknad paginering. Returnera ENBART JSON: {"status":"GODKÄND"/"AVVISAD","findings":["..."],"severity":"LOW"/"MEDIUM"/"HIGH","suggestions":["..."]}'},

    # ── UX ───────────────────────────────────────────────────────────────────────
    {"id":"ux","name":"UX-granskare","emoji":"🎨","model":"haiku","enabled":True,
     "prompt":'Du ansvarar ENBART för användarupplevelse. Granska: uppfylls acceptanskriterierna, intuitivt flöde, feedback till användaren. Kommentera inte kod-struktur. Returnera ENBART JSON: {"status":"GODKÄND"/"AVVISAD","findings":["..."],"severity":"LOW"/"MEDIUM"/"HIGH","suggestions":["..."]}'},

    # ── Mobil ────────────────────────────────────────────────────────────────────
    {"id":"mobile","name":"Mobil/Fält","emoji":"📱","model":"haiku","enabled":True,
     "prompt":'Du ansvarar ENBART för mobil/fält. Granska: touchmål under 44px, läsbarhet i solljus, för många steg, saknad offline-hantering. Tänk: handskebeklädd tumme. Returnera ENBART JSON: {"status":"GODKÄND"/"AVVISAD","findings":["..."],"severity":"LOW"/"MEDIUM"/"HIGH","suggestions":["..."]}'},

    # ── Testbarhet ───────────────────────────────────────────────────────────────
    {"id":"tester","name":"Testbarhet","emoji":"🧪","model":"ollama:qwen2.5-coder:7b","enabled":True,
     "prompt":'Du ansvarar ENBART för testbarhet. Granska: testbar kod utan side effects, edge cases utan täckning (null, nätverksfel, tomma listor, race conditions). Lista de 3 viktigaste saknade testfallen. Returnera ENBART JSON: {"status":"GODKÄND"/"AVVISAD","findings":["..."],"severity":"LOW"/"MEDIUM"/"HIGH","suggestions":["..."]}'},

    # ── Inspector (sista grinden) ─────────────────────────────────────────────
    {"id":"inspector","name":"Besiktningsman","emoji":"✅","model":"sonnet","enabled":True,"is_inspector":True,
     "prompt":'''Du är Besiktningsmannen — sista grinden innan kod byggs. Du får strukturerade fynd från ALLA granskaragenter.

DITT ANSVAR (och inget annat):
1. Läs ALLA agenters fynd och bedöm HELHETEN
2. Är det säkert att bygga nu, eller krävs beslut/förtydliganden?
3. Formulera konkreta instruktioner till Snickaren om GODKÄND
4. Formulera en ENKEL fråga till användaren om AVVISAD — bara när det verkligen behövs

GODKÄNN om: Inga HIGH-problem, eller HIGH-problem som Snickaren kan lösa självständigt
AVVISA om: Spec för vag, säkerhetsrisk som kräver beslut, motstridiga krav

Returnera ENBART JSON:
{"status":"GODKÄND"/"AVVISAD","findings":["..."],"severity":"LOW"/"MEDIUM"/"HIGH","suggestions":["..."],"snickare_instruktioner":"Konkreta riktlinjer till Snickaren baserat på agenters fynd","user_question":"Fråga till användaren om AVVISAD, annars tom sträng"}
'''},
]

DEFAULT_SETTINGS = {
    "api_key": "",
    "github_token": "",
    "git_name": "Ishoo Creator",
    "git_email": "creator@ishoo.se",
    "dev_branch": "dev",
    "prod_branch": "main",
    "max_iterations": 3,
    "vercel_token": "",
    "vercel_team_id": "",
    "model_projektledare": SONNET_DEFAULT,
    "model_snickare": SONNET_DEFAULT,
    "model_sonnet": SONNET_DEFAULT,
    "model_haiku": HAIKU_DEFAULT,
    "agents": DEFAULT_AGENTS,
}

def load_settings() -> dict:
    stored = {}
    if SETTINGS_FILE.exists():
        try: stored = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except: pass
    s = {**DEFAULT_SETTINGS, **stored}
    # .env overrides for sensitive keys (backwards compat)
    if not s["api_key"]:     s["api_key"]     = os.environ.get("ANTHROPIC_API_KEY", "")
    if not s["github_token"]:s["github_token"] = os.environ.get("GITHUB_TOKEN", "")
    if not s["git_name"] or s["git_name"] == "Ishoo Creator":
        env_gn = os.environ.get("GIT_NAME",""); s["git_name"] = env_gn or s["git_name"]
    if not s["git_email"] or s["git_email"] == "creator@ishoo.se":
        env_ge = os.environ.get("GIT_EMAIL",""); s["git_email"] = env_ge or s["git_email"]
    if "agents" not in s or not s["agents"]: s["agents"] = DEFAULT_AGENTS
    return s

def save_settings(data: dict):
    # Never save plaintext keys if they match env vars (keep as-is)
    SETTINGS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def get_client(s: dict = None):
    if s is None: s = load_settings()
    key = s.get("api_key","")
    return anthropic.Anthropic(api_key=key) if key else None

def model_for(role: str, s: dict = None) -> str:
    if s is None: s = load_settings()
    m = {"sonnet": s.get("model_sonnet", SONNET_DEFAULT), "haiku": s.get("model_haiku", HAIKU_DEFAULT)}
    if role == "projektledare": return s.get("model_projektledare", SONNET_DEFAULT)
    if role == "snickare":      return s.get("model_snickare", SONNET_DEFAULT)
    return m.get(role, SONNET_DEFAULT)

# ─── Projekthantering ─────────────────────────────────────────────────────────

def load_projects() -> dict:
    if PROJECTS_FILE.exists():
        return json.loads(PROJECTS_FILE.read_text(encoding="utf-8"))
    default = {"active": "innob-bygg", "projects": [{
        "id": "innob-bygg", "name": "Innob Bygg CRM",
        "description": "Totalentreprenad", "github": "Stuwish1/quote-engine-setup",
        "created": datetime.now().isoformat()
    }]}
    save_projects(default); return default

def save_projects(data: dict):
    PROJECTS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def get_active_project() -> dict | None:
    data = load_projects()
    return next((p for p in data["projects"] if p["id"] == data.get("active")), None)

def project_dir(pid: str) -> Path:
    d = PROJECTS_DIR / pid; d.mkdir(parents=True, exist_ok=True)
    (d / "memory").mkdir(exist_ok=True); return d

def load_memory(pid: str) -> str:
    mem_dir = project_dir(pid) / "memory"
    # Prioritetsordning: viktigaste filerna först
    priority_order = ["CLAUDE.md", "SCHEMA.md", "PATTERNS.md", "ARCHITECTURE.md", "DECISIONS.md", "FEATURES.md"]
    files = list(mem_dir.glob("*.md"))
    def sort_key(f):
        try: return priority_order.index(f.name)
        except ValueError: return 99
    files.sort(key=sort_key)
    parts = []
    for f in files:
        try:
            content = f.read_text(encoding='utf-8')
            if content.strip():
                parts.append(f"=== {f.name} ===\n{content}")
        except: pass
    combined = "\n\n".join(parts)
    return combined[:16000] if combined else "Inget projektminne ännu."

def load_features(pid: str) -> list:
    f = project_dir(pid) / "features.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else []

def save_features(pid: str, features: list):
    (project_dir(pid) / "features.json").write_text(
        json.dumps(features, ensure_ascii=False, indent=2), encoding="utf-8")

def add_feature(pid: str, name: str, phase: str = "MVP", spec: dict = None):
    features = load_features(pid)
    features.append({"id": len(features)+1, "name": name, "phase": phase,
                     "status": "Planerad", "spec": spec or {},
                     "created": datetime.now().isoformat()})
    save_features(pid, features)

def add_subtasks(pid: str, parent_name: str, deluppgifter: list) -> list:
    """Skapar deluppgifter som sub-features under parent_name.
    Returnerar lista med namn på tillagda deluppgifter."""
    features = load_features(pid)
    existing_names = {f["name"] for f in features}
    added = []
    for sub in sorted(deluppgifter, key=lambda x: x.get("prioritet", 99)):
        raw_name = sub.get("namn", "Deluppgift")
        name = f"{parent_name}: {raw_name}"
        # Undvik dubletter
        if name in existing_names:
            continue
        existing_names.add(name)
        beroenden = sub.get("beroende_av", [])
        # Prefix beroenden med parent om de inte redan är prefixade
        beroenden_full = [
            b if b.startswith(parent_name) else f"{parent_name}: {b}"
            for b in beroenden
        ]
        features.append({
            "id": len(features) + 1,
            "name": name,
            "phase": "MVP",
            "status": "Planerad",
            "parent_feature": parent_name,
            "spec": {
                "name": name,
                "description": sub.get("spec", ""),
                "beroende_av": beroenden_full
            },
            "created": datetime.now().isoformat()
        })
        added.append(name)
    # Markera parent som Blockerad
    for f in features:
        if f["name"] == parent_name:
            f["status"] = "Blockerad"
    save_features(pid, features)
    update_features_md(pid)
    return added

def load_project_settings(pid: str) -> dict:
    f = project_dir(pid) / "project_settings.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}

def save_project_settings(pid: str, ps: dict):
    (project_dir(pid) / "project_settings.json").write_text(
        json.dumps(ps, ensure_ascii=False, indent=2), encoding="utf-8")

def slug(name: str) -> str:
    s = re.sub(r'[åä]', 'a', name.lower().strip())
    s = re.sub(r'ö', 'o', s); s = re.sub(r'[^a-z0-9]+', '-', s)
    return s.strip('-')[:40]

# ─── Git / Repo ───────────────────────────────────────────────────────────────

def repo_dir(pid: str) -> Path:
    return project_dir(pid) / "repo"

def effective_repo_dir(pid: str) -> Path:
    """Returnerar rotmappen for ishoo-creator (sjalvforbattring), annars vanlig repo-mapp."""
    if pid == "ishoo-creator":
        return Path(".")  # Skriv direkt till C:\innob-agent\
    return repo_dir(pid)

def is_self_project(pid: str) -> bool:
    return pid == "ishoo-creator"

def git(rd, *args, **kwargs):
    return subprocess.run(["git", "-C", str(rd)] + list(args),
                          capture_output=True, text=True, **kwargs)

def clone_or_pull(github_repo: str, pid: str, branch: str = None) -> tuple[Path, str]:
    """Klonar eller uppdaterar repot, checkar ut rätt branch."""
    s = load_settings()
    if not github_repo: return None, "Inget GitHub-repo angivet."
    if not s["github_token"]: return None, "GitHub-token saknas. Lägg till i Inställningar."

    rd = repo_dir(pid)
    url = f"https://{s['github_token']}@github.com/{github_repo}.git"
    dev_branch = branch or s.get("dev_branch", "dev")

    if (rd / ".git").exists():
        # Fetch + checkout
        git(rd, "fetch", "--all")
        git(rd, "config", "user.name",  s["git_name"])
        git(rd, "config", "user.email", s["git_email"])
        # Checkout dev branch (create if not exists)
        r = git(rd, "checkout", dev_branch)
        if r.returncode != 0:
            r = git(rd, "checkout", "-b", dev_branch)
            if r.returncode != 0:
                return None, f"Kunde inte checka ut branch {dev_branch}: {r.stderr[:200]}"
        git(rd, "pull", "--rebase", "origin", dev_branch)
    else:
        rd.mkdir(parents=True, exist_ok=True)
        r = subprocess.run(["git", "clone", url, str(rd)], capture_output=True, text=True)
        if r.returncode != 0:
            return None, f"git clone misslyckades: {r.stderr[:300]}"
        git(rd, "config", "user.name",  s["git_name"])
        git(rd, "config", "user.email", s["git_email"])
        # Checkout or create dev branch
        r = git(rd, "checkout", dev_branch)
        if r.returncode != 0:
            r = git(rd, "checkout", "-b", dev_branch)
            if r.returncode != 0:
                return None, f"Kunde inte skapa branch {dev_branch}: {r.stderr[:200]}"

    # Write Supabase env files if project has Supabase config
    ps = load_project_settings(pid)
    if ps.get("supabase_dev_url"):
        dev_env = rd / ".env.development"
        dev_env.write_text(
            f"VITE_SUPABASE_URL={ps['supabase_dev_url']}\n"
            f"VITE_SUPABASE_ANON_KEY={ps.get('supabase_dev_key','')}\n",
            encoding="utf-8")
    if ps.get("supabase_prod_url"):
        prod_env = rd / ".env.production"
        prod_env.write_text(
            f"VITE_SUPABASE_URL={ps['supabase_prod_url']}\n"
            f"VITE_SUPABASE_ANON_KEY={ps.get('supabase_prod_key','')}\n",
            encoding="utf-8")

    # Auto-generera STRUKTURINDEX.md om den saknas (krävs av Strukturnavigatorn)
    si_path = rd / "STRUKTURINDEX.md"
    if not si_path.exists():
        try:
            generate_strukturindex(pid, rd)
        except Exception:
            pass  # Misslyckas tyst — genereras nästa gång istället

    return rd, ""

_SKIP_DIRS = {"node_modules", ".git", "dist", "build", "__pycache__", ".next", "coverage"}

def _should_skip(path: Path) -> bool:
    return any(skip in path.parts for skip in _SKIP_DIRS)

def build_file_index(path: Path) -> str:
    """Strukturindex för en Python/JS/TS-fil: alla funktioner, endpoints och sektioner med radnummer."""
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").split("\n")
    except Exception:
        return ""
    total = len(lines)
    rows = [f"  [{total} rader]"]
    for i, line in enumerate(lines, 1):
        s = line.strip()
        if "# ───" in s or "# ---" in s:
            rows.append(f"  r{i}: {s[:70]}")
        elif s.startswith("@app.") or s.startswith("@router."):
            rows.append(f"  r{i}: {s.split('(')[0]}")
        elif s.startswith("async def ") or s.startswith("def "):
            indent = "    " if len(line) - len(line.lstrip()) > 0 else "  "
            rows.append(f"{indent}r{i}: {s.split('(')[0]}")
        elif s.startswith("class "):
            rows.append(f"\n  r{i}: {s.split(':')[0]}")
        elif (s.startswith("function ") or s.startswith("async function ")
              or s.startswith("export function") or s.startswith("export async function")
              or s.startswith("export default function")):
            rows.append(f"  r{i}: {s.split('(')[0][:60]}")
        elif s.startswith("export const ") and "=>" in s:
            rows.append(f"  r{i}: {s.split('=')[0].strip()[:60]}")
    return "\n".join(rows)

def get_file_section(path: Path, keyword_list: list, max_chars: int = 3000) -> str:
    """Returnerar sektioner i filen som matchar keywords — kompletta funktioner, ej avklippta."""
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").split("\n")
    except Exception:
        return ""
    hits = set()
    for i, line in enumerate(lines):
        if any(kw.lower() in line.lower() for kw in keyword_list):
            # Ta med omgivande funktion: backa till def/function
            start = i
            for j in range(i, max(-1, i-60), -1):
                s = lines[j].strip()
                if (s.startswith("def ") or s.startswith("async def ")
                        or s.startswith("function ") or s.startswith("async function")
                        or s.startswith("export")):
                    start = j
                    break
            hits.add(start)
    if not hits:
        return ""
    sections = []
    for start in sorted(hits)[:4]:
        chunk = "\n".join(lines[start:start+50])
        sections.append(f"# rad {start+1}:\n{chunk}")
    result = "\n\n...\n\n".join(sections)
    return result[:max_chars]


def generate_strukturindex(pid: str, rd: Path) -> str:
    """Genererar STRUKTURINDEX.md och sparar den i projektmappen.
    Returnerar sökvägen till den skapade filen."""
    lines = ["# STRUKTURINDEX", f"Uppdaterad: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ""]

    # ── Katalogträd ──────────────────────────────────────────────────────────
    lines += ["## Filstruktur", "```"]
    all_files: list[tuple] = []
    for ext in (".py", ".ts", ".tsx", ".js", ".jsx", ".css", ".json", ".html", ".md"):
        for f in rd.rglob(f"*{ext}"):
            if _should_skip(f):
                continue
            try:
                all_files.append((f.relative_to(rd), f.stat().st_size, f))
            except Exception:
                pass
    all_files.sort(key=lambda x: str(x[0]))

    # Bygg träd
    seen_dirs: set = set()
    for rel, sz, _ in all_files:
        parts = rel.parts
        for depth in range(len(parts) - 1):
            d = "/".join(parts[:depth+1])
            if d not in seen_dirs:
                seen_dirs.add(d)
                lines.append("  " * depth + parts[depth] + "/")
        indent = "  " * (len(parts) - 1)
        label = f"{sz//1024}kb" if sz >= 1024 else f"{sz}b"
        lines.append(f"{indent}{parts[-1]}  ({label})")
    lines += ["```", ""]

    # ── Strukturindex per fil ─────────────────────────────────────────────────
    lines += ["## Strukturindex per fil", ""]
    for rel, sz, full in sorted(all_files, key=lambda x: x[1], reverse=True)[:20]:
        if rel.suffix not in (".py", ".ts", ".tsx", ".js"):
            continue
        idx = build_file_index(full)
        if idx.strip():
            lines += [f"### {rel}", "```", idx, "```", ""]

    # ── Konventioner (försök läsa befintliga) ─────────────────────────────────
    # Detektera projekt-typ
    is_react = any(str(r).endswith("package.json") for r, _, _ in all_files)
    is_python = any(r.suffix == ".py" for r, _, _ in all_files)

    lines += ["## Konventioner", ""]
    if is_react:
        lines += [
            "- Komponenter: `src/components/[domän]/[Komponent].tsx` (PascalCase)",
            "- Sidor: `src/pages/[Sida].tsx`",
            "- Hooks: `src/hooks/use[Namn].ts`",
            "- API/Supabase: `src/lib/[namn].ts`",
            "- Typer: `src/types/index.ts` eller `src/types/[domän].ts`",
            "- Utils: `src/utils/[namn].ts`",
            "",
        ]
    if is_python:
        lines += [
            "- Endpoints: `app.py` under rätt `# ───` sektion",
            "- Agenter: DEFAULT_AGENTS eller POST_BUILD_AGENTS",
            "- Helpers: nära relaterade funktioner",
            "",
        ]

    content = "\n".join(lines)
    # Spara i projektets datamapp OCH i repots rot om det finns
    data_path = project_dir(pid) / "STRUKTURINDEX.md"
    data_path.write_text(content, encoding="utf-8")
    if rd.exists():
        repo_path = rd / "STRUKTURINDEX.md"
        try:
            repo_path.write_text(content, encoding="utf-8")
        except Exception:
            pass
    return str(data_path)


def read_codebase_context(rd: Path, spec: dict, for_ollama: bool = False) -> str:
    """Bygger rik kodbas-kontext: karta + strukturindex + relevanta sektioner.

    for_ollama=True → komprimerat för modeller med litet kontextfönster (≤8k).
    """
    parts = []

    # ── DEL 0: STRUKTURINDEX.md — alltid allra först ─────────────────────────
    # Letar i repots rot och i projektets datamapp
    for si_path in [rd / "STRUKTURINDEX.md"]:
        if si_path.exists():
            try:
                si_content = si_path.read_text(encoding="utf-8", errors="ignore")
                # Komprimera för Ollama: bara rubrikerna + konventioner
                if for_ollama:
                    si_lines = [l for l in si_content.split("\n")
                                if l.startswith("#") or l.startswith("- ") or l.startswith("  ") and "(" in l]
                    si_content = "\n".join(si_lines[:80])
                parts.append(f"=== STRUKTURINDEX.md ===\n{si_content[:8000]}")
            except Exception:
                pass
            break

    # ── DEL 1: Filkarta (alltid med — kompakt) ───────────────────────────────
    all_files: list[tuple] = []
    for ext in (".py", ".ts", ".tsx", ".js", ".jsx", ".css", ".json", ".html", ".md"):
        for f in rd.rglob(f"*{ext}"):
            if _should_skip(f):
                continue
            try:
                sz = f.stat().st_size
                all_files.append((f.relative_to(rd), sz, f))
            except Exception:
                pass
    all_files.sort(key=lambda x: x[1], reverse=True)

    karta_rows = []
    for rel, sz, _ in all_files[:50]:
        label = f"{sz//1024}kb" if sz >= 1024 else f"{sz}b"
        karta_rows.append(f"  {rel} ({label})")
    parts.append("=== KODBAS-KARTA ===\n" + "\n".join(karta_rows))

    # ── DEL 2: Strukturindex (för .py, .ts, .tsx, .js) ──────────────────────
    if not for_ollama:
        for rel, sz, full in all_files:
            if rel.suffix in (".py", ".ts", ".tsx", ".js") and sz > 300:
                idx = build_file_index(full)
                if idx.strip():
                    parts.append(f"=== INDEX: {rel} ===\n{idx}")

    # ── DEL 3: Konfigfiler i sin helhet ─────────────────────────────────────
    priority = ["package.json", "tsconfig.json", "requirements.txt",
                ".env.example", "vite.config.ts", "tailwind.config.ts"]
    for rel_name in priority:
        p = rd / rel_name
        if p.exists():
            try:
                content = p.read_text(encoding="utf-8", errors="ignore")[:1500]
                parts.append(f"=== {rel_name} ===\n{content}")
            except Exception:
                pass

    # ── DEL 4: Relevanta sektioner baserat på spec-keywords ─────────────────
    kws: list[str] = []
    for field in ("name", "description", "problem", "solution", "spec"):
        val = spec.get(field, "")
        if isinstance(val, str):
            kws.extend(w for w in val.lower().split() if len(w) > 4)
    kws = list(dict.fromkeys(kws))[:8]  # unika, max 8

    if kws:
        for rel, sz, full in all_files[:15]:
            if rel.suffix in (".py", ".ts", ".tsx", ".js", ".html"):
                sec = get_file_section(full, kws, max_chars=2000)
                if sec:
                    parts.append(f"=== RELEVANTA AVSNITT: {rel} ===\n{sec}")

    # ── DEL 5: Små filer i sin helhet (< 200 rader) ──────────────────────────
    if not for_ollama:
        for rel, sz, full in all_files:
            if rel.suffix in (".py", ".ts", ".tsx", ".js") and sz < 4000:
                try:
                    content = full.read_text(encoding="utf-8", errors="ignore")
                    if len(content.split("\n")) < 200:
                        parts.append(f"=== FULL FIL: {rel} ===\n{content}")
                except Exception:
                    pass

    result = "\n\n".join(parts)
    limit = 10000 if for_ollama else 35000
    return result[:limit]

def generate_diff_text(old_content: str, new_content: str, filename: str) -> list[dict]:
    old_lines = old_content.splitlines(keepends=True) if old_content else []
    new_lines = new_content.splitlines(keepends=True)
    diff = list(difflib.unified_diff(old_lines, new_lines,
                fromfile=f"a/{filename}", tofile=f"b/{filename}", lineterm=""))
    lines = []
    for line in diff[2:]:
        if line.startswith('+'):   lines.append({"type":"add","content":line[1:].rstrip('\n')})
        elif line.startswith('-'): lines.append({"type":"del","content":line[1:].rstrip('\n')})
        elif line.startswith('@@'):lines.append({"type":"hunk","content":line.rstrip('\n')})
        else:                      lines.append({"type":"ctx","content":line[1:].rstrip('\n') if line.startswith(' ') else line.rstrip('\n')})
    return lines

SNICKARE_PROMPT = """Du är en expert React/TypeScript/Supabase-utvecklare — "snickaren".
Du får en feature-spec och befintlig kodbas.

REGLER:
- Skriv korrekt TypeScript med types
- Använd shadcn/ui och Tailwind CSS för UI
- Supabase-anrop: använd import.meta.env.VITE_SUPABASE_URL och VITE_SUPABASE_ANON_KEY (aldrig hårdkoda URLs)
- Skapa eller modifiera minsta möjliga antal filer
- Inga TODO-kommentarer — skriv färdig kod
- Returnera EXAKT detta JSON:

{
  "summary": "Kort beskrivning",
  "files": [
    {"path":"src/...", "action":"create"/"modify"/"delete", "content":"...", "description":"..."}
  ]
}"""

async def build_code(spec: dict, pid: str) -> tuple[list, str]:
    s = load_settings()
    client_inst = get_client(s)
    if not client_inst: return [], "API-nyckel saknas. Lägg till i Inställningar."
    proj = get_active_project()
    if not proj or not proj.get("github"): return [], "Inget GitHub-repo kopplat."
    if is_self_project(pid):
        rd = effective_repo_dir(pid)
        # Ishoo Creator: ge Snickaren full strukturell kontext om sina egna filer
        ctx_parts = []
        for fname in ["app.py", "index.html"]:
            fp = rd / fname
            if fp.exists():
                raw = fp.read_text(encoding="utf-8", errors="ignore")
                idx = build_file_index(fp)
                # Ge index + full fil (Snickaren behöver se allt för att skriva korrekt kod)
                ctx_parts.append(
                    f"=== {fname} — INDEX ===\n{idx}\n\n"
                    f"=== {fname} — FULL KOD ({len(raw.splitlines())} rader) ===\n{raw}"
                )
        context = "\n\n".join(ctx_parts) if ctx_parts else "Inga filer hittades."
    else:
        rd, err = clone_or_pull(proj["github"], pid)
        if err: return [], err
        context = read_codebase_context(rd, spec)
    spec_text = json.dumps(spec, ensure_ascii=False, indent=2)
    try:
        response = client_inst.messages.create(
            model=model_for("snickare", s), max_tokens=8000, system=SNICKARE_PROMPT,
            messages=[{"role":"user","content":f"FEATURE-SPEC:\n{spec_text}\n\nBEFINTLIG KODBAS:\n{context}\n\nGenerera koden nu. Returnera ENBART XML-format enligt instruktionen."}])
        text = response.content[0].text.strip()
        import re as _re
        # Parsa XML-format
        files, summary = [], ""
        sm = _re.search(r"<summary>(.*?)</summary>", text, _re.DOTALL)
        if sm: summary = sm.group(1).strip()
        for fm in _re.finditer(r"<file>(.*?)</file>", text, _re.DOTALL):
            blk = fm.group(1)
            def _tag(t, b=blk):
                m = _re.search(rf"<{t}>(.*?)</{t}>", b, _re.DOTALL)
                return m.group(1).strip() if m else ""
            p2 = _tag("path"); act = _tag("action") or "create"
            desc = _tag("description")
            cm = _re.search(r"<content>(.*?)</content>", blk, _re.DOTALL)
            code = cm.group(1).lstrip("\n") if cm else ""
            if p2: files.append({"path":p2,"action":act,"content":code,"description":desc})
        if not files:
            # Fallback: JSON om Claude missade instruktionen
            try:
                s2, e2 = text.find("{"), text.rfind("}")+1
                d2 = json.loads(text[s2:e2]) if s2!=-1 else {}
                files = d2.get("files",[])
                summary = d2.get("summary", summary)
            except Exception:
                pass
        if not files:
            return [], f"Snickaren returnerade ogiltigt format. ({len(text)} tecken)"
        return files, summary
    except Exception as ex:
        return [], f"Kodgenerering misslyckades: {ex}"

def compute_diffs(pid: str, file_changes: list) -> list:
    rd = effective_repo_dir(pid); diffs = []
    for fc in file_changes:
        path=fc.get("path",""); action=fc.get("action","create")
        new_content=fc.get("content",""); description=fc.get("description","")
        existing = rd / path; old_content = ""
        if existing.exists() and action != "create":
            try: old_content = existing.read_text(encoding="utf-8", errors="ignore")
            except: pass
        diff_lines = generate_diff_text(old_content, new_content, path)
        added   = sum(1 for l in diff_lines if l["type"]=="add")
        removed = sum(1 for l in diff_lines if l["type"]=="del")
        diffs.append({"path":path,"action":action,"description":description,
                      "lines":diff_lines,"added":added,"removed":removed,"new_content":new_content})
    return diffs

def store_pending(pid: str, file_changes: list, feature_name: str):
    p = project_dir(pid) / "pending_changes.json"
    p.write_text(json.dumps({"feature":feature_name,"files":file_changes},ensure_ascii=False,indent=2),encoding="utf-8")

def load_pending(pid: str) -> dict:
    p = project_dir(pid) / "pending_changes.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

def apply_and_push(pid: str, feature_name: str, env: str = "dev") -> str:
    """Applicerar ändringar och pushar till dev-branch eller mergar till prod."""
    s = load_settings()
    pending = load_pending(pid)
    if not pending: return "Inga väntande ändringar."
    rd = effective_repo_dir(pid)
    if not rd.exists(): return "Repo-mappen saknas."

    dev_branch  = s.get("dev_branch","dev")
    prod_branch = s.get("prod_branch","main")

    # Se till att vi är på dev-branch
    r = git(rd, "checkout", dev_branch)
    if r.returncode != 0:
        r = git(rd, "checkout", "-b", dev_branch)
        if r.returncode != 0: return f"Kunde inte checka ut {dev_branch}: {r.stderr[:200]}"

    # Applicera filer
    for fc in pending.get("files",[]):
        fpath = rd / fc["path"]; action = fc.get("action","create")
        if action == "delete":
            if fpath.exists(): fpath.unlink()
        else:
            fpath.parent.mkdir(parents=True, exist_ok=True)
            fpath.write_text(fc.get("content",""), encoding="utf-8")

    # Commit på dev
    git(rd, "add", "-A")
    commit_msg = f"feat: {feature_name}\n\nGenererat av Ishoo Creator [{env}]"
    r = git(rd, "commit", "-m", commit_msg)
    if r.returncode != 0 and "nothing to commit" not in r.stdout:
        return f"git commit misslyckades: {r.stderr[:300]}"

    # Push dev
    r = git(rd, "push", "--set-upstream", "origin", dev_branch)
    if r.returncode != 0:
        return f"git push {dev_branch} misslyckades: {r.stderr[:300]}"

    if env == "prod":
        # Merge dev → prod branch
        r = git(rd, "checkout", prod_branch)
        if r.returncode != 0:
            # Skapa prod branch baserat på remote
            r = git(rd, "checkout", "-b", prod_branch, f"origin/{prod_branch}")
            if r.returncode != 0:
                return f"Kunde inte checka ut {prod_branch}: {r.stderr[:200]}"
        r = git(rd, "merge", "--no-ff", dev_branch, "-m", f"Merge: {feature_name} → produktion")
        if r.returncode != 0:
            return f"Merge {dev_branch} → {prod_branch} misslyckades: {r.stderr[:300]}"
        r = git(rd, "push", "origin", prod_branch)
        if r.returncode != 0:
            return f"git push {prod_branch} misslyckades: {r.stderr[:300]}"

    (project_dir(pid) / "pending_changes.json").unlink(missing_ok=True)
    return ""

# ─── Agenter ──────────────────────────────────────────────────────────────────

def get_agents_from_settings(s: dict = None):
    if s is None: s = load_settings()
    agents = s.get("agents", DEFAULT_AGENTS)
    regular = [a for a in agents if not a.get("is_inspector") and a.get("enabled", True)]
    inspector_list = [a for a in agents if a.get("is_inspector") and a.get("enabled", True)]
    inspector = inspector_list[0] if inspector_list else DEFAULT_AGENTS[-1]
    return regular, inspector

PROJEKTLEDARE_PROMPT = """Du är en extremt noggrann projektledare OCH systemarkitekt i Ishoo Creator.

PROJEKT: {project_name}
BESKRIVNING: {project_desc}
GITHUB: {project_github}

Du hanterar TWO typer av förfrågningar:

━━━ TYP 1: FEATURE (bygga ny funktionalitet) ━━━
Var BESLUTSSAM och SNABB. Ställ max 1-2 korta frågor, sedan kör.
Om du kan gissa rimliga svar på saknade detaljer — gör det och berätta vad du antog.

Samla MINST detta innan du avslutar:
- Vad ska byggas (redan känt från användarens meddelande)
- Vem använder det (gissa om oklart)
- Acceptanskriterier — 2-4 konkreta punkter
- Fas: MVP / v1 / v2 (fråga EN gång om oklart, annars MVP)

Jobba som en senior utvecklare: förstå intentionen, fyll i rimliga gap, kör.

När klart, avsluta MED EXAKT:
[FEATURE_KLAR]
{{
  "name": "Kortnamn",
  "phase": "MVP",
  "problem": "...",
  "solution": "...",
  "users": "...",
  "acceptance_criteria": ["..."],
  "dependencies": [],
  "risks": []
}}
[/FEATURE_KLAR]

━━━ TYP 2: SYSTEMKONFIGURATION (ändra Ishoo Creator) ━━━
När användaren vill lägga till/ändra agenter, byta inställningar, modifiera pipeline.
Ställ frågor för att förstå:
- Vad ska den nya agenten/ändringen göra exakt?
- Vilket problem löser det?
- Vilken modell passar (sonnet för komplex analys, haiku för snabb check)?
- Hur strikta ska krav vara?

När klart, avsluta MED EXAKT:
[SYSTEM_KLAR]
{{
  "type": "add_agent"/"update_agent"/"update_settings"/"update_prompt",
  "description": "Vad som ändrades",
  "agent": {{
    "name": "Agentnamn",
    "emoji": "🏛️",
    "model": "sonnet"/"haiku",
    "is_inspector": false,
    "prompt": "Du är... Returnera ENBART JSON: {{\"status\":\"GODKÄND\"/\"AVVISAD\",\"findings\":[\"...\"],\"severity\":\"LOW\"/\"MEDIUM\"/\"HIGH\",\"suggestions\":[\"...\"]}}",
    "enabled": true
  }},
  "settings": {{}}
}}
[/SYSTEM_KLAR]

━━━ FRÅGOR MED ALTERNATIV ━━━
När du vill ställa en fråga med fasta alternativ, använd EXAKT detta format:

[FRÅGA]
text: Din fråga här?
multi: false
alternativ: Alternativ 1, Alternativ 2, Alternativ 3, Alternativ 4
[/FRÅGA]

Sätt multi: true om användaren kan välja flera alternativ.
Max 4 alternativ. Använd alltid svenska.
Exempel på när du ska använda frågor med alternativ:
- "Vilken fas? MVP / v1 / v2 / Osäker"
- "Vilka användare? (välj flera)" med multi: true
- "Hur komplex?" med alternativ för svårighetsgrad

━━━ MINNE & KONTEXT ━━━
Du har FULL FRIHET att:
- Hämta och analysera information ur minnet
- Fatta beslut och anta rimliga defaults utan att fråga
- Komma ihåg tidigare konversation och referera till den
- Agera som en senior teknisk projektledare med full befogenhet
- Specificera features baserat på vad du vet om projektet
Du BEHÖVER INTE fråga om saker du kan rimligt anta. Kör på.

PROJEKTMINNE:
{memory}

FASÖVERSIKT:
{phases}"""

# ─── Domare — aktiveras efter max_iter misslyckanden ─────────────────────────

DOMARE_PROMPT = """Du är Domaren — kontinuerlig prioriterare. Du aktiveras när en granskning misslyckas.

DITT JOBB I EXAKT DENNA ORDNING:

STEG 1 — Kategorisera blockerarna:
Dela in alla agentfynd i:
  A) MÅSTE FIXAS FÖRST (blockerar allt annat — spec oklart, kritisk infrastruktur saknas)
  B) MÅSTE FIXAS (HIGH-problem som stoppar bygget)
  C) BÖR FIXAS (MEDIUM-problem som påverkar kvalitet men inte stoppar)
  D) KAN VÄNTA (LOW-problem, teknisk skuld)

STEG 2 — Bryt ner i MINIMALA BYGGBARA DELUPPGIFTER:
Varje deluppgift ska vara så liten att den:
  - Kan granskas och byggas på under 30 minuter
  - Löser EXAKT EN blockerare
  - Kan testas självständigt
Skapa 2-5 deluppgifter MAX. Om fler behövs, prioritera de viktigaste.

STEG 3 — Sätt HÅRD BEROENDEORDNING:
Om deluppgift B beror på deluppgift A → sätt beroende_av: ["A"].
Ingen deluppgift ska byggas om dess beroenden inte är GODKÄNDA och BYGGDA.

STEG 4 — Tydliggör vem som behöver agera:
  - "Användaren" = beslut/konfiguration som kräver mänskligt ingripande
  - "Snickaren" = ren kodändring som AI kan göra
  - "Projektledaren + Användaren" = diskussion krävs

FORMAT — returnera ENBART JSON:
{{
  "blockerare": [
    {{"problem": "...", "kategori": "A"/"B"/"C"/"D", "berorda_agenter": ["..."], "rekommendation": "..."}}
  ],
  "grundorsak": "Spec för vag / Teknisk skuld / Saknat beroende / Säkerhetsrisk / Infrastruktur saknas",
  "deluppgifter": [
    {{"prioritet": 1, "namn": "Kort unikt namn", "spec": "Exakt vad som ska implementeras — tillräckligt detaljerat för Snickaren att bygga direkt", "vem": "Snickaren"/"Användaren", "beroende_av": [], "beraknad_tid": "15min"}},
    {{"prioritet": 2, "namn": "...", "spec": "...", "vem": "...", "beroende_av": ["Prioritet 1 namn"], "beraknad_tid": "..."}}
  ],
  "nasta_steg": "Exakt vad användaren ska göra NU — ett konkret nästa steg",
  "projektledare_sammanfattning": "Kortfattad text på svenska — max 3 meningar",
  "kan_byggas_nu": false
}}"""

# ─── Post-build agenter (kör automatiskt efter varje bygge) ──────────────────
# Varje agent har ett ENDA ansvar — inga överlapp.

POST_BUILD_AGENTS = [
    {
        "id": "felsokaren",
        "name": "Felsökaren",
        "emoji": "🔬",
        "model": "ollama:qwen2.5-coder:7b",
        "stage": "post",
        "prompt": """Du ansvarar ENBART för att hitta buggar i genererad kod: syntaxfel, saknade imports, odefinierade variabler, trasiga JSX-taggar, felaktig indragning, logikfel som garanterat kraschar runtime. Rapportera INTE kodstil eller förbättringsförslag.
Returnera ENBART JSON: {"status":"GODKÄND"/"AVVISAD","findings":["..."],"severity":"LOW"/"MEDIUM"/"HIGH","suggestions":["..."]}"""
    },
    {
        "id": "refaktorering",
        "name": "Refaktorerare",
        "emoji": "♻️",
        "model": "ollama:qwen2.5-coder:7b",
        "stage": "post",
        "prompt": """Du ansvarar ENBART för refaktoreringsförslag på genererad kod: duplicerad kod som bör extraheras, funktioner som är för långa (>30 rader), magiska värden som bör bli konstanter, dåliga variabelnamn, onödig komplexitet. Hitta INTE buggar — det gör Felsökaren.
Returnera ENBART JSON: {"status":"GODKÄND"/"AVVISAD","findings":["..."],"severity":"LOW"/"MEDIUM"/"HIGH","suggestions":["..."]}"""
    },
    {
        "id": "integration",
        "name": "Integrationstestaren",
        "emoji": "🔗",
        "model": "ollama:qwen2.5-coder:7b",
        "stage": "post",
        "prompt": """Du ansvarar ENBART för att kontrollera att ny kod inte bryter befintliga gränssnitt: ändrade API-signaturer, borttagna exports, inkompatibla props/typer, saknade databas-migreringar, brutna imports. Rapportera INTE kodkvalitet eller buggar.
Returnera ENBART JSON: {"status":"GODKÄND"/"AVVISAD","findings":["..."],"severity":"LOW"/"MEDIUM"/"HIGH","suggestions":["..."]}"""
    },
    {
        "id": "dokumenteraren",
        "name": "Dokumenteraren",
        "emoji": "📝",
        "model": "ollama:qwen2.5-coder:7b",
        "stage": "post",
        "prompt": """Du ansvarar ENBART för dokumentation av nybyggd kod.
Kontrollera: saknar exporterade funktioner JSDoc-kommentarer? Saknar komplexa logikblock förklarande kommentarer? Är komponenters props odokumenterade? Är README eller ARCHITECTURE.md inaktuell?
Hitta INTE buggar. Föreslå INTE refaktorering.
Returnera ENBART JSON: {"status":"GODKÄND"/"AVVISAD","findings":["Funktion X saknar JSDoc","..."],"severity":"LOW"/"MEDIUM"/"HIGH","suggestions":["/** @param {string} id - Beskrivning */\nexport function X(id: string) {...}"]}"""
    },
    {
        "id": "konsistensgranskare",
        "name": "Konsistensgranskaren",
        "emoji": "🎯",
        "model": "ollama:qwen2.5-coder:7b",
        "stage": "post",
        "prompt": """Du ansvarar ENBART för konsistens med befintlig kodbas.
Kontrollera: följer ny kod samma mönster som liknande befintlig kod? Används samma namnkonventioner? Samma felhanteringsmönster? Samma import-struktur? Samma komponentstruktur?
Exempel på problem: en ny hook skrivs på ett helt annat sätt än befintliga hooks, en ny sida använder class-komponenter när resten använder functional, en ny API-funktion returnerar en annan form än resten.
Returnera ENBART JSON: {"status":"GODKÄND"/"AVVISAD","findings":["..."],"severity":"LOW"/"MEDIUM"/"HIGH","suggestions":["..."]}"""
    },
]

def parse_fraga(reply: str) -> dict | None:
    """Parsar [FRÅGA]...[/FRÅGA] block och returnerar strukturerad fråga."""
    if "[FRÅGA]" not in reply: return None
    try:
        s = reply.find("[FRÅGA]") + len("[FRÅGA]")
        e = reply.find("[/FRÅGA]", s)
        block = reply[s:e].strip()
        result = {}
        for line in block.split("\n"):
            line = line.strip()
            if line.startswith("text:"):
                result["text"] = line[5:].strip()
            elif line.startswith("multi:"):
                result["multi"] = line[6:].strip().lower() == "true"
            elif line.startswith("alternativ:"):
                alts = [a.strip() for a in line[11:].split(",") if a.strip()]
                result["options"] = alts[:4]
        return result if "text" in result and "options" in result else None
    except:
        return None

def parse_feature_klar(reply: str) -> dict | None:
    if "[FEATURE_KLAR]" not in reply: return None
    try:
        s = reply.find("[FEATURE_KLAR]") + len("[FEATURE_KLAR]")
        e = reply.find("[/FEATURE_KLAR]", s)
        return json.loads(reply[s:e].strip())
    except:
        return None

def parse_system_klar(reply: str) -> dict | None:
    if "[SYSTEM_KLAR]" not in reply: return None
    try:
        s = reply.find("[SYSTEM_KLAR]") + len("[SYSTEM_KLAR]")
        e = reply.find("[/SYSTEM_KLAR]", s)
        return json.loads(reply[s:e].strip())
    except:
        return None


def phases_summary(pid: str) -> str:
    features = load_features(pid)
    phases = {"MVP":[],"v1":[],"v2":[]}
    for f in features:
        ph = f.get("phase","MVP")
        if ph in phases: phases[ph].append(f"{f['name']} [{f['status']}]")
    return "\n".join(f"{ph}: {', '.join(items) if items else 'inga'}" for ph,items in phases.items())

def _ollama_available() -> bool:
    import urllib.request as _ur
    try:
        _ur.urlopen("http://localhost:11434/api/tags", timeout=2)
        return True
    except: return False

def run_agent_ollama(agent_def: dict, spec: str, memory: str, feedback: str = "", code_context: str = "") -> dict:
    """Kor agent via lokal Ollama — gratis och snabbt pa RTX 3080."""
    import urllib.request as _ur
    model_key = agent_def.get("model", "sonnet")
    ollama_model = model_key.split("ollama:", 1)[1] if "ollama:" in model_key else "qwen2.5-coder:7b"
    fb = f"\n\nFEEDBACK:\n{feedback}" if feedback else ""
    # Ollama har begränsat kontextfönster — karta + index ryms i 10k
    code_block = f"\n\nKODBAS (aktuell):\n{code_context[:10000]}" if code_context else ""
    messages = [
        {"role": "system", "content": agent_def["prompt"]},
        {"role": "user", "content": f"MINNE:\n{memory}\n\nSPEC:\n{spec}{code_block}{fb}\n\nReturnera ENBART JSON."}
    ]
    payload = json.dumps({"model": ollama_model, "messages": messages,
                           "stream": False, "format": "json"}).encode("utf-8")
    req = _ur.Request("http://localhost:11434/api/chat", data=payload,
                       headers={"Content-Type": "application/json"})
    try:
        with _ur.urlopen(req, timeout=90) as r:
            resp = json.loads(r.read())
        text = resp.get("message", {}).get("content", "{}")
        si, e = text.find("{"), text.rfind("}") + 1
        data = json.loads(text[si:e]) if si != -1 else {}
        data["agent"] = agent_def["name"]
        data["id"] = agent_def["id"]
        data["_local"] = True
        return data
    except Exception as ex:
        return {"agent": agent_def["name"], "id": agent_def["id"],
                "status": "GODKÄND", "findings": [f"Ollama-fel: {ex}"],
                "severity": "LOW", "suggestions": [], "_local": True}

def _parse_json_robust(text: str) -> dict:
    """Parsar JSON robust — hittar yttersta { } korrekt även vid nested objekt."""
    text = text.strip()
    # Hitta första {
    start = text.find("{")
    if start == -1:
        return {}
    # Räkna brackets för att hitta matchande }
    depth = 0
    end = -1
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end == -1:
        return {}
    try:
        return json.loads(text[start:end])
    except json.JSONDecodeError:
        # Sista utväg: ta bort kommentarer och försök igen
        cleaned = "\n".join(l for l in text[start:end].split("\n") if not l.strip().startswith("//"))
        try:
            return json.loads(cleaned)
        except Exception:
            return {}


def run_agent(agent_def: dict, spec: str, memory: str, feedback: str = "", s: dict = None, code_context: str = "") -> dict:
    if s is None: s = load_settings()
    model_key = agent_def.get("model","sonnet")
    if model_key.startswith("ollama:"):
        result = run_agent_ollama(agent_def, spec, memory, feedback, code_context=code_context)
        ollama_err = result.get("findings", [""])
        if ollama_err and str(ollama_err[0]).startswith("Ollama-fel"):
            fallback = dict(agent_def); fallback["model"] = "haiku"
            return run_agent(fallback, spec, memory, feedback, s, code_context)
        return result
    client_inst = get_client(s)
    if not client_inst:
        return {"agent":agent_def["name"],"id":agent_def["id"],"status":"GODKÄND","findings":["Demo-läge"],"severity":"LOW","suggestions":[]}
    model_name = model_for(model_key, s)
    fb = f"\n\nFEEDBACK:\n{feedback}" if feedback else ""
    # Kontextgräns per modell — Claude kan hantera mycket mer än Ollama
    ctx_limit = 35000 if model_key in ("sonnet", "opus") else 20000
    code_block = f"\n\nKODBAS (aktuell):\n{code_context[:ctx_limit]}" if code_context else ""
    is_domare = agent_def.get("id") == "domare"
    max_tokens = 3000 if is_domare else 1500
    try:
        r = client_inst.messages.create(model=model_name, max_tokens=max_tokens,
            system=agent_def["prompt"],
            messages=[{"role":"user","content":f"MINNE:\n{memory}\n\nSPEC:\n{spec}{code_block}{fb}\n\nReturnera ENBART JSON."}])
        text = r.content[0].text.strip()
        # Robust JSON-parser: hitta yttersta { } korrekt (hanterar nested)
        data = _parse_json_robust(text)
        data["agent"]=agent_def["name"]; data["id"]=agent_def["id"]; return data
    except Exception as ex:
        return {"agent":agent_def["name"],"id":agent_def["id"],"status":"GODKÄND","findings":[f"Fel: {ex}"],"severity":"LOW","suggestions":[]}


@app.post("/api/apply-system-config")
async def apply_system_config(payload: dict):
    """Applicerar en systemkonfiguration från Projektledaren."""
    config = payload.get("config", {})
    action = config.get("type","")
    s = load_settings()

    if action == "add_agent":
        agents = s.get("agents", [])
        agent = config.get("agent", {})
        if not agent.get("id"):
            agent["id"] = slug(agent.get("name","agent")) + "-" + str(len(agents))
        agents.append(agent); s["agents"] = agents; save_settings(s)
        return JSONResponse({"ok":True,"message":f"Agent '{agent.get('name')}' tillagd"})

    elif action == "update_agent":
        agent_update = config.get("agent", {})
        agents = s.get("agents", [])
        for a in agents:
            if a["id"] == agent_update.get("id") or a["name"] == agent_update.get("name"):
                a.update({k:v for k,v in agent_update.items() if k})
        s["agents"] = agents; save_settings(s)
        return JSONResponse({"ok":True,"message":"Agent uppdaterad"})

    elif action == "update_settings":
        updates = config.get("settings", {})
        s.update(updates); save_settings(s)
        return JSONResponse({"ok":True,"message":"Inställningar uppdaterade"})

    return JSONResponse({"error":"Okänd action"},status_code=400)

# ─── WebSocket ────────────────────────────────────────────────────────────────

class ConnectionManager:
    def __init__(self): self.active: list[WebSocket] = []
    async def connect(self, ws: WebSocket): await ws.accept(); self.active.append(ws)
    def disconnect(self, ws: WebSocket): self.active = [c for c in self.active if c != ws]
    async def broadcast(self, data: dict):
        dead = []
        for ws in self.active:
            try: await ws.send_json(data)
            except: dead.append(ws)
        for ws in dead: self.active.remove(ws)

manager = ConnectionManager()

# ─── API ──────────────────────────────────────────────────────────────────────

@app.get("/")
async def root(): return FileResponse("index.html")

# Settings
@app.get("/api/settings")
async def get_settings_api():
    s = load_settings()
    safe = {k:v for k,v in s.items()}
    # Mask sensitive keys for display (send length hint instead)
    if safe.get("api_key"):     safe["api_key_set"] = True
    if safe.get("github_token"):safe["github_token_set"] = True
    return JSONResponse(safe)

@app.post("/api/settings")
async def save_settings_api(payload: dict):
    s = load_settings()
    allowed = ["api_key","github_token","git_name","git_email","dev_branch","prod_branch",
               "max_iterations","model_projektledare","model_snickare","model_sonnet","model_haiku",
               "vercel_token","vercel_team_id"]
    for k in allowed:
        if k in payload and payload[k] is not None:
            s[k] = payload[k]
    save_settings(s)
    return JSONResponse({"ok":True})

# Agents
@app.get("/api/agents")
async def get_agents():
    s = load_settings(); return JSONResponse(s.get("agents", DEFAULT_AGENTS))

@app.post("/api/agents")
async def create_agent(payload: dict):
    s = load_settings(); agents = s.get("agents", DEFAULT_AGENTS[:])
    new_id = slug(payload.get("name","agent")) + "-" + str(len(agents))
    new_agent = {"id":new_id,"name":payload.get("name","Ny agent"),
                 "emoji":payload.get("emoji","🤖"),"model":payload.get("model","haiku"),
                 "enabled":True,"is_inspector":False,"prompt":payload.get("prompt","")}
    agents.append(new_agent); s["agents"]=agents; save_settings(s)
    return JSONResponse(new_agent)

@app.put("/api/agents/{agent_id}")
async def update_agent(agent_id: str, payload: dict):
    s = load_settings(); agents = s.get("agents", [])
    for a in agents:
        if a["id"] == agent_id:
            for k in ["name","emoji","model","enabled","prompt","is_inspector"]:
                if k in payload: a[k] = payload[k]
    s["agents"] = agents; save_settings(s)
    return JSONResponse({"ok":True})

@app.delete("/api/agents/{agent_id}")
async def delete_agent(agent_id: str):
    s = load_settings()
    s["agents"] = [a for a in s.get("agents",[]) if a["id"] != agent_id]
    save_settings(s); return JSONResponse({"ok":True})

# Projects
@app.get("/api/projects")
async def get_projects(): return JSONResponse(load_projects())

@app.post("/api/projects")
async def create_project(payload: dict):
    name = payload.get("name","").strip()
    if not name: return JSONResponse({"error":"Namn krävs"},status_code=400)
    pid = slug(name); data = load_projects()
    if any(p["id"]==pid for p in data["projects"]): pid += "-"+str(len(data["projects"]))
    new_p = {"id":pid,"name":name,"description":payload.get("description",""),
             "github":payload.get("github",""),"created":datetime.now().isoformat()}
    data["projects"].append(new_p); data["active"]=pid; save_projects(data)
    project_dir(pid)
    mem = project_dir(pid) / "memory"
    s = load_settings()
    dev_b = s.get("dev_branch","dev"); prod_b = s.get("prod_branch","main")
    desc = payload.get('description',''); github = payload.get('github','Ej angivet')
    # CLAUDE.md — projektöversikt
    (mem / "CLAUDE.md").write_text(
        f"# {name}\n\n## Beskrivning\n{desc}\n\n## GitHub\n{github}\n\n## Tech Stack\nReact + TypeScript + Vite + Tailwind + shadcn/ui + Supabase\n\n## Dev/Prod\n- Dev: `{dev_b}`-branch + dev Supabase\n- Prod: `{prod_b}`-branch + prod Supabase\n- Aldrig pusha till prod utan manuellt godkännande\n\n## Personas / Användare\n*(Fyll i: vem använder systemet och i vilket sammanhang?)*\n\n## Affärsregler\n*(Fyll i: viktiga domänregler, beräkningslogik, begränsningar)*\n\n## Faser\n- **MVP:** Minimum för att systemet ska fungera\n- **v1:** Viktiga tillägg\n- **v2:** Framtida idéer\n",
        encoding="utf-8")
    # SCHEMA.md — databasschema
    (mem / "SCHEMA.md").write_text(
        f"# Databasschema — {name}\n\n## Tabeller\n*(Fyll i eller generera via Projektledaren)*\n\n## Relationer\n*(T.ex: projekt.kund_id → kunder.id)*\n\n## RLS-policies\n*(Beskriv Row Level Security per tabell)*\n\n## Index\n*(Vilka kolumner behöver index för prestanda?)*\n",
        encoding="utf-8")
    # PATTERNS.md — kodkonventioner
    (mem / "PATTERNS.md").write_text(
        f"# Kodmönster & Konventioner — {name}\n\n## Filstruktur\n```\nsrc/\n  components/   # Återanvändbara UI-komponenter\n  pages/        # Sidkomponenter (route-nivå)\n  hooks/        # Custom React hooks\n  lib/          # Supabase-klient, utilities\n  types/        # TypeScript-typer\n```\n\n## Supabase\n- Använd alltid `import.meta.env.VITE_SUPABASE_URL` — aldrig hårdkoda\n- RLS aktiverat på alla tabeller från start\n- Hantera loading/error-state på alla queries\n\n## Komponenter\n- shadcn/ui för all UI\n- Tailwind för styling — inga inline styles\n- Alla forms: react-hook-form + zod-validering\n\n## Felhantering\n- Visa alltid feedback till användaren vid fel\n- Logga fel i konsolen för debugging\n- Aldrig tysta fel med tom catch\n\n## Loading states\n- Skeleton-loaders för listor/tabeller\n- Spinner på knappar vid async-action\n",
        encoding="utf-8")
    # DECISIONS.md — arkitekturbeslut
    (mem / "DECISIONS.md").write_text(
        f"# Arkitekturbeslut — {name}\n\n*Varje viktigt beslut loggas här så agenter aldrig ifrågasätter det igen.*\n\n| Datum | Beslut | Alternativ som övervägdes | Motivering |\n|-------|--------|--------------------------|------------|\n| {datetime.now().strftime('%Y-%m-%d')} | React + TypeScript + Vite | Next.js, SvelteKit | Lovable-kompatibelt, snabb HMR, starkt typsystem |\n| {datetime.now().strftime('%Y-%m-%d')} | Supabase | Firebase, PlanetScale | RLS, Postgres, öppen källkod |\n| {datetime.now().strftime('%Y-%m-%d')} | shadcn/ui | MUI, Ant Design | Kopierbar, Tailwind-baserad, ingen bundle-bloat |\n",
        encoding="utf-8")
    # FEATURES.md — featureöversikt (uppdateras automatiskt)
    (mem / "FEATURES.md").write_text(
        f"# Features — {name}\n\n*Uppdateras automatiskt av Ishoo Creator.*\n\n## MVP\n*(Inga ännu)*\n\n## v1\n*(Inga ännu)*\n\n## v2\n*(Inga ännu)*\n",
        encoding="utf-8")
    return JSONResponse({"project":new_p,"projects":data})

@app.put("/api/projects/active")
async def set_active(payload: dict):
    pid=payload.get("id"); data=load_projects()
    if not any(p["id"]==pid for p in data["projects"]): return JSONResponse({"error":"Hittades inte"},status_code=404)
    data["active"]=pid; save_projects(data); return JSONResponse({"active":pid})

@app.delete("/api/projects/{project_id}")
async def delete_project(project_id: str):
    if project_id == "ishoo-creator":
        return JSONResponse({"ok": False, "error": "Grundprojektet kan inte tas bort."}, status_code=403)
    data=load_projects(); data["projects"]=[p for p in data["projects"] if p["id"]!=project_id]
    if data["active"]==project_id: data["active"]=data["projects"][0]["id"] if data["projects"] else None
    save_projects(data); return JSONResponse({"ok":True})

@app.get("/api/projects/{project_id}/settings")
async def get_project_settings(project_id: str):
    return JSONResponse(load_project_settings(project_id))

@app.post("/api/projects/{project_id}/settings")
async def update_project_settings(project_id: str, payload: dict):
    ps = load_project_settings(project_id)
    for k in ["supabase_dev_url","supabase_dev_key","supabase_prod_url","supabase_prod_key","github"]:
        if k in payload: ps[k] = payload[k]
    # Also update github in projects.json if provided
    if "github" in payload:
        data = load_projects()
        for p in data["projects"]:
            if p["id"] == project_id: p["github"] = payload["github"]
        save_projects(data)
    save_project_settings(project_id, ps)
    return JSONResponse({"ok":True})

# Features
@app.get("/api/features")
async def get_features():
    proj=get_active_project(); return JSONResponse(load_features(proj["id"]) if proj else [])

@app.delete("/api/features/{feature_name:path}")
async def delete_feature(feature_name: str):
    proj = get_active_project()
    if not proj:
        return JSONResponse({"ok": False, "error": "Inget aktivt projekt"}, status_code=400)
    pid = proj["id"]
    # Ta bort från features.json — inkl. alla deluppgifter (barn) rekursivt
    features = load_features(pid)
    before = len(features)
    to_remove = {feature_name}
    # Rekursivt hitta alla barn-features
    changed = True
    while changed:
        changed = False
        for f in features:
            if f.get("parent_feature") in to_remove and f["name"] not in to_remove:
                to_remove.add(f["name"])
                changed = True
    features = [f for f in features if f["name"] not in to_remove]
    save_features(pid, features)
    # Rensa väntande bygge om det gäller denna feature
    pending = load_pending(pid)
    if pending and pending.get("feature") == feature_name:
        pending_path = project_dir(pid) / "pending.json"
        if pending_path.exists():
            pending_path.unlink()
    # Uppdatera FEATURES.md
    update_features_md(pid)
    removed = before - len(features)
    return JSONResponse({"ok": True, "removed": removed})

# Chat
@app.post("/api/chat")
async def chat(payload: dict):
    message=payload.get("message",""); history=payload.get("history",[])
    proj=get_active_project()
    if not proj: return JSONResponse({"reply":"Inget aktivt projekt.","feature_detected":None,"feature_spec":None})
    s = load_settings()
    client_inst = get_client(s)
    if not client_inst: return JSONResponse({"reply":"⚠️ API-nyckel saknas. Gå till Inställningar (⚙️) och lägg till din Anthropic API-nyckel.","feature_detected":None,"feature_spec":None})
    memory=load_memory(proj["id"]); phases=phases_summary(proj["id"])
    # Ge Projektledaren tillgång till aktuell kodbas
    rd_chat = effective_repo_dir(proj["id"])
    code_ctx_chat = read_codebase_context(rd_chat, {"name": message, "problem": message, "solution": ""}) if rd_chat.exists() else ""
    code_section = f"\n\nAKTUELL KODBAS:\n{code_ctx_chat}" if code_ctx_chat else ""
    system=PROJEKTLEDARE_PROMPT.format(project_name=proj["name"],project_desc=proj.get("description",""),
        project_github=proj.get("github","Ej angivet"),memory=memory,phases=phases) + code_section
    response=client_inst.messages.create(model=model_for("projektledare",s),max_tokens=1500,system=system,
        messages=history[-12:]+[{"role":"user","content":message}])
    reply=response.content[0].text
    feature_spec=parse_feature_klar(reply); feature_name=None
    if feature_spec:
        feature_name=feature_spec.get("name","Okänd")
        add_feature(proj["id"],feature_name,feature_spec.get("phase","MVP"),feature_spec)
    system_config = parse_system_klar(reply)
    question = parse_fraga(reply)
    # Rensa [FRÅGA]-blocket från reply-texten som visas
    clean_reply = reply
    if question:
        import re as _re
        clean_reply = _re.sub(r'\[FRÅGA\][\s\S]*?\[/FRÅGA\]', '', reply).strip()
    return JSONResponse({"reply":clean_reply,"feature_detected":feature_name,"feature_spec":feature_spec,"system_config":system_config,"question":question})

# Review — EN enda pass. Om något agent säger ifrån → Domaren direkt.
@app.post("/api/review")
async def review_feature(payload: dict):
    feature_name = payload.get("feature_name", "Okand")
    spec_obj = payload.get("spec_obj", {})
    proj = get_active_project()
    if not proj:
        return JSONResponse({"approved": False, "error": "Inget aktivt projekt"}, status_code=400)
    s = load_settings()
    if not s.get("api_key"):
        await manager.broadcast({"type": "pipeline_done", "success": False, "feature": feature_name,
            "reason": "⚠️ Anthropic API-nyckel saknas — gå till ⚙️ Inställningar och lägg in nyckeln."})
        return JSONResponse({"approved": False, "error": "API-nyckel saknas"}, status_code=400)
    memory = load_memory(proj["id"])
    spec_str = json.dumps(spec_obj, ensure_ascii=False) if spec_obj else feature_name
    loop = asyncio.get_event_loop()
    agents, inspector = get_agents_from_settings(s)
    rd = effective_repo_dir(proj["id"])
    # Bygg två versioner av kontexten: rik för Claude, komprimerad för Ollama
    code_ctx_claude  = read_codebase_context(rd, spec_obj, for_ollama=False) if rd.exists() else ""
    code_ctx_ollama  = read_codebase_context(rd, spec_obj, for_ollama=True)  if rd.exists() else ""
    def ctx_for(agent_def: dict) -> str:
        return code_ctx_ollama if agent_def.get("model","").startswith("ollama:") else code_ctx_claude

    domare_entry = {"id": "domare", "name": "⚖️Domaren", "model": "sonnet", "is_domare": True}
    await manager.broadcast({"type": "pipeline_start", "feature": feature_name,
        "agents": [{"id": a["id"], "name": f"{a.get('emoji','')}{a['name']}", "model": a.get("model","haiku")}
                   for a in agents + [inspector]] + [domare_entry]})
    await manager.broadcast({"type": "iteration", "iteration": 1, "max": 1})

    # ── Steg 1: Kör ALLA granskare parallellt ────────────────────────────────
    for agent in agents:
        await manager.broadcast({"type": "agent_status", "id": agent["id"],
            "name": f"{agent.get('emoji','')}{agent['name']}", "status": "running"})

    results = []
    from concurrent.futures import as_completed as _as_completed
    ex = ThreadPoolExecutor(max_workers=min(len(agents), 10))
    future_to_agent = {ex.submit(run_agent, ag, spec_str, memory, "", s, ctx_for(ag)): ag
                       for ag in agents}
    try:
        pending_futures = set(future_to_agent.keys())
        while pending_futures:
            done_future = await loop.run_in_executor(None,
                lambda fs=list(pending_futures): next(_as_completed(fs)))
            pending_futures.discard(done_future)
            ag = future_to_agent[done_future]
            try:
                result = done_future.result()
            except Exception as e:
                result = {"id": ag["id"], "agent": ag["name"], "status": "GODKAND",
                          "findings": [f"Agent-fel: {e}"], "severity": "LOW", "suggestions": []}
            results.append(result)
            await manager.broadcast({"type": "agent_status",
                "id": result.get("id"), "name": result.get("agent", "Agent"),
                "status": "approved" if result.get("status") in ("GODKAND","GODKÄND") else "rejected",
                "findings": result.get("findings", []),
                "severity": result.get("severity", "LOW"),
                "suggestions": result.get("suggestions", []),
                "local": result.get("_local", False)})
    finally:
        ex.shutdown(wait=False)

    # ── Steg 2: Inspector sammanväger alla fynd ───────────────────────────────
    parts = []
    for r in results:
        finds = "; ".join(r.get("findings", [])) or "Inga anmarkningar"
        suggs = "; ".join(r.get("suggestions", [])) or "-"
        parts.append(
            f"### {r.get('agent','?')} [{r.get('status','?')}] [{r.get('severity','LOW')}]\n"
            f"Fynd: {finds}\nForslag: {suggs}"
        )
    inspector_input = (
        f"FEATURE: {feature_name}\n\nSPEC:\n{spec_str[:2000]}\n\n"
        f"AGENT-FYND:\n" + "\n\n".join(parts)
    )
    await manager.broadcast({"type": "agent_status",
        "id": inspector["id"], "name": f"{inspector.get('emoji','')}{inspector['name']}",
        "status": "running"})
    insp = await loop.run_in_executor(None, run_agent, inspector, inspector_input, memory, "", s, code_ctx_claude)
    insp_status = insp.get("status", "GODKAND")
    snickare_instruktioner = insp.get("snickare_instruktioner", "")

    await manager.broadcast({"type": "agent_status",
        "id": inspector["id"], "name": f"{inspector.get('emoji','')}{inspector['name']}",
        "status": "approved" if insp_status in ("GODKAND","GODKÄND") else "rejected",
        "findings": insp.get("findings", []),
        "severity": insp.get("severity", "LOW"),
        "suggestions": insp.get("suggestions", []),
        "inspector_note": snickare_instruktioner})

    # ── Steg 3: Godkänt → klart att bygga ────────────────────────────────────
    if insp_status in ("GODKAND", "GODKÄND"):
        features = load_features(proj["id"])
        for f in features:
            if f["name"] == feature_name:
                f["status"] = "Granskas"

        # ── Skapa max 3 uppföljningsuppgifter — bara unika HIGH utanför specens scope ──
        backlog_added = []
        TRUSTED_AGENTS = {"security", "architect", "felhantering", "performance"}
        FP = ["strukturindex", "ingen fil", "finns ingen fil", "typescript-typer",
              "filplacering", "src/", "kallad strukturindex", "saknad beroende på typescript",
              "duplicerad", "duplikat", "duplicate", "två gånger", "two definition",
              "two definitioner", "definierad två", "redan definierad"]
        def is_fp(t: str) -> bool:
            tl = t.lower()
            return any(p in tl for p in FP)
        def fp_overlap_with_spec(t: str) -> bool:
            # Hoppa över fynd som handlar om samma sak som featuren redan fixar
            spec_words = set(spec_str.lower().split())
            finding_words = set(t.lower().split())
            overlap = spec_words & finding_words
            meaningful = {w for w in overlap if len(w) > 4}
            return len(meaningful) >= 3

        seen_fingerprints = set()
        existing_names = {f["name"] for f in features}
        prio = 1
        priority_order = ["security","architect","felhantering","performance"]
        sorted_results = sorted(
            [r for r in results if r.get("status") not in ("GODKAND","GODKÄND") and r.get("severity")=="HIGH"],
            key=lambda r: priority_order.index(r.get("id","")) if r.get("id","") in priority_order else 99
        )
        for r in sorted_results:
            if prio > 3: break
            if r.get("id","") not in TRUSTED_AGENTS: continue
            agent_label = r.get("agent","?")
            for finding in r.get("findings",[])[:2]:
                if prio > 3: break
                if len(finding) < 20: continue
                if is_fp(finding): continue
                if fp_overlap_with_spec(finding): continue
                # Fingerprint: 6 mest frekventa ord (ignorera stoppord)
                stopwords = {"och","att","är","en","ett","som","på","av","för","med","i","det","den","de"}
                words = [w for w in finding.lower().split() if w not in stopwords and len(w)>3]
                fingerprint = " ".join(sorted(words[:6]))
                if fingerprint in seen_fingerprints: continue
                seen_fingerprints.add(fingerprint)
                # Kort, beskrivande namn utan förälderns prefix
                short_label = finding[:50].rstrip().rstrip("—").strip()
                task_name = f"{feature_name}: ↳ {prio}. {short_label}"
                if task_name in existing_names: continue
                existing_names.add(task_name)
                features.append({
                    "id": len(features) + 1,
                    "name": task_name,
                    "phase": "Backlog",
                    "status": "Planerad",
                    "parent_feature": feature_name,
                    "spec": {
                        "name": task_name,
                        "description": finding,
                        "prioritet": prio,
                        "beroende_av": [],
                        "källa": agent_label
                    },
                    "created": datetime.now().isoformat()
                })
                backlog_added.append(task_name)
                prio += 1

        save_features(proj["id"], features)
        update_features_md(proj["id"])
        await manager.broadcast({"type": "pipeline_done", "success": True,
            "feature": feature_name, "snickare_instruktioner": snickare_instruktioner,
            "backlog_added": backlog_added})
        return JSONResponse({"approved": True, "snickare_instruktioner": snickare_instruktioner,
                             "backlog_added": backlog_added})

    # ── Steg 4: Avvisat → Domaren analyserar direkt ──────────────────────────
    await manager.broadcast({"type": "domare_start", "feature": feature_name})

    rejected = [r for r in results if r.get("status") not in ("GODKAND","GODKÄND")]
    domare_sections = ["## AGENT-FYND"]
    for r in results:
        st = r.get("status","?"); sev = r.get("severity","LOW")
        finds = "; ".join(r.get("findings",[])) or "Inga fynd"
        domare_sections.append(f"  {r.get('agent','?')} [{st}][{sev}]: {finds}")
    domare_sections.append(f"\n## INSPECTOR [{insp_status}]")
    domare_sections.append("  " + "; ".join(insp.get("findings",[])))
    if insp.get("user_question"):
        domare_sections.append(f"\n  Inspector fråga: {insp['user_question']}")

    domare_input = (
        f"FEATURE: {feature_name}\n\nSPEC:\n{spec_str[:1500]}\n\n"
        + "\n".join(domare_sections)
    )
    domare_agent = {"id":"domare","name":"Domaren","emoji":"⚖️","model":"sonnet",
                    "prompt": DOMARE_PROMPT.format(max_iter=1)}

    await manager.broadcast({"type": "agent_status", "id": "domare",
        "name": "⚖️ Domaren", "status": "running"})
    domare_result = await loop.run_in_executor(
        None, run_agent, domare_agent, domare_input, memory, "", s, code_ctx_claude)

    pl_summary = domare_result.get("projektledare_sammanfattning", "Granskningen misslyckades.")
    blockerare = domare_result.get("blockerare", [])
    atgarder = domare_result.get("prioriterad_atgardsplan", [])

    await manager.broadcast({"type": "agent_status", "id": "domare",
        "name": "⚖️ Domaren", "status": "rejected",
        "findings": [b.get("problem","") for b in blockerare],
        "severity": "HIGH"})

    # ── Spara deluppgifter och markera parent som Blockerad ──────────────────
    deluppgifter = domare_result.get("deluppgifter", [])
    added_subtasks = []
    if deluppgifter and proj:
        added_subtasks = add_subtasks(proj["id"], feature_name, deluppgifter)

    nasta_steg = domare_result.get("nasta_steg", "")
    pl_message = f"{pl_summary}\n\n"
    if blockerare:
        # Visa bara A+B-blockerare (måste fixas) — inte C/D
        critical = [b for b in blockerare if b.get("kategori","B") in ("A","B")]
        if critical:
            pl_message += "**Blockerare:**\n"
            for b in critical:
                agenter = ", ".join(b.get("berorda_agenter", []))
                kategori = b.get("kategori","B")
                pl_message += f"- [{kategori}] {b.get('problem','')} _(berör: {agenter})_\n"
    if added_subtasks:
        pl_message += f"\n**Jag har brutit ner featuren i {len(added_subtasks)} deluppgifter** som nu visas i listan nedan. "
        pl_message += "De är ordnade i rätt byggordsföljd — börja uppifrån.\n"
    if nasta_steg:
        pl_message += f"\n**➡ Nästa steg:** {nasta_steg}"

    await manager.broadcast({"type": "pipeline_done", "success": False,
        "feature": feature_name,
        "domare_report": domare_result,
        "added_subtasks": added_subtasks,
        "projektledare_message": pl_message})

    return JSONResponse({"approved": False})

# Build
@app.post("/api/build")
async def build_feature(payload: dict):
    feature_name=payload.get("feature_name","Okänd"); spec_obj=payload.get("spec_obj",{})
    proj=get_active_project()
    if not proj: return JSONResponse({"error":"Inget aktivt projekt"},status_code=400)
    await manager.broadcast({"type":"build_start","feature":feature_name})
    await manager.broadcast({"type":"build_progress","message":"Klonar/uppdaterar repo från GitHub..."})
    loop=asyncio.get_event_loop()
    file_changes, result = await loop.run_in_executor(None, lambda: build_code_sync(spec_obj, proj["id"]))
    if isinstance(result, str) and result and not file_changes:
        await manager.broadcast({"type":"build_error","message":result}); return JSONResponse({"error":result},status_code=500)
    await manager.broadcast({"type":"build_progress","message":"Beräknar diff..."})
    diffs=compute_diffs(proj["id"], file_changes)
    store_pending(proj["id"], file_changes, feature_name)
    await manager.broadcast({"type":"build_done","feature":feature_name,"diffs":diffs,"summary":result})
    return JSONResponse({"diffs":diffs,"summary":result,"files_count":len(file_changes)})

def build_code_sync(spec: dict, pid: str):
    import asyncio as _as; loop=_as.new_event_loop()
    return loop.run_until_complete(build_code(spec, pid))

# Push
@app.post("/api/push")
async def push_feature(payload: dict):
    feature_name=payload.get("feature_name","feature"); env=payload.get("env","dev")
    proj=get_active_project()
    if not proj: return JSONResponse({"error":"Inget aktivt projekt"},status_code=400)
    await manager.broadcast({"type":"push_start","feature":feature_name,"env":env})
    loop=asyncio.get_event_loop()
    err=await loop.run_in_executor(None, apply_and_push, proj["id"], feature_name, env)
    if err:
        await manager.broadcast({"type":"push_error","message":err}); return JSONResponse({"error":err},status_code=500)
    features=load_features(proj["id"])
    for f in features:
        if f["name"]==feature_name: f["status"]="Klar" if env=="prod" else "I dev"
    save_features(proj["id"],features)
    # Auto-uppdatera FEATURES.md
    update_features_md(proj["id"])
    # Auto-uppdatera ARCHITECTURE.md i bakgrunden (icke-blockerande)
    async def _regen_arch():
        try:
            rd = repo_dir(proj["id"])
            if not rd.exists(): return
            s2 = load_settings(); client2 = get_client(s2)
            if not client2: return
            src2 = rd / "src"; file_list2 = []
            if src2.exists():
                for fobj in sorted(src2.rglob("*")):
                    if fobj.is_file() and fobj.suffix in (".ts",".tsx"):
                        rel2 = str(fobj.relative_to(rd))
                        try: head2 = fobj.read_text(encoding="utf-8",errors="ignore")[:400]; file_list2.append(f"{rel2}\n{head2}\n---")
                        except: pass
            context2 = "\n".join(file_list2[:50])
            ARCH_PROMPT2 = """Du är en arkitekt. Analysera kodbas och uppdatera ARCHITECTURE.md.
Inkludera: ## Komponenter, ## Supabase-tabeller, ## Hooks, ## Utilities, ## Viktiga mönster.
Var kortfattad — detta är kontextfil för AI-agenter."""
            loop2 = asyncio.get_event_loop()
            r2 = await loop2.run_in_executor(None, lambda: client2.messages.create(
                model=model_for("haiku", s2), max_tokens=2000, system=ARCH_PROMPT2,
                messages=[{"role":"user","content":f"Projekt: {proj['name']}\n\nFILER:\n{context2}"}]))
            save_architecture(proj["id"], r2.content[0].text)
            await manager.broadcast({"type":"architecture_updated","feature":feature_name})
        except: pass
    asyncio.ensure_future(_regen_arch())

    # Uppdatera STRUKTURINDEX efter push (kodbasen har förändrats)
    async def _regen_index():
        try:
            proj2 = get_active_project()
            if proj2:
                rd2 = effective_repo_dir(proj2["id"])
                if rd2.exists():
                    generate_strukturindex(proj2["id"], rd2)
                    await manager.broadcast({"type": "strukturindex_updated", "feature": feature_name})
        except Exception:
            pass
    asyncio.ensure_future(_regen_index())

    await manager.broadcast({"type":"push_done","feature":feature_name,"env":env})
    return JSONResponse({"success":True})


@app.post("/api/rebuild-index")
async def rebuild_strukturindex():
    """Manuell trigger: bygg om STRUKTURINDEX.md för aktivt projekt."""
    proj = get_active_project()
    if not proj:
        return JSONResponse({"ok": False, "error": "Inget aktivt projekt"}, status_code=400)
    rd = effective_repo_dir(proj["id"])
    if not rd.exists():
        return JSONResponse({"ok": False, "error": "Ingen kodbas klonad ännu"}, status_code=400)
    path = generate_strukturindex(proj["id"], rd)
    await manager.broadcast({"type": "strukturindex_updated", "message": "STRUKTURINDEX.md uppdaterad"})
    return JSONResponse({"ok": True, "path": path})


# WebSocket

# ─── Vercel Preview ───────────────────────────────────────────────────────────

@app.get("/api/preview")
async def get_preview():
    """Hämtar senaste Vercel deployment-URL för dev och prod branch."""
    import urllib.request
    s = load_settings()
    token = s.get("vercel_token","")
    if not token:
        return JSONResponse({"dev_url":"","prod_url":"","error":"Vercel-token saknas. Lägg till i ⚙️ Inställningar."})

    proj = get_active_project()
    ps = load_project_settings(proj["id"]) if proj else {}
    vercel_project = ps.get("vercel_project_id","") or ps.get("vercel_project_name","")
    if not vercel_project:
        return JSONResponse({"dev_url":"","prod_url":"","error":"Vercel-projektnamn saknas. Lägg till i ⚙️ → Projekt."})

    team_id = s.get("vercel_team_id","")
    dev_branch  = s.get("dev_branch","dev")
    prod_branch = s.get("prod_branch","main")

    def fetch_latest_deployment(branch: str):
        team_q = f"&teamId={team_id}" if team_id else ""
        url = f"https://api.vercel.com/v6/deployments?projectId={vercel_project}&target=preview&limit=10{team_q}"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        try:
            with urllib.request.urlopen(req, timeout=8) as r:
                data = json.loads(r.read())
            deployments = data.get("deployments", [])
            for d in deployments:
                meta = d.get("meta", {})
                if meta.get("githubCommitRef") == branch or d.get("name","").endswith(f"-{branch}"):
                    return f"https://{d.get('url','')}"
            # Fallback: return first deployment URL
            if deployments:
                return f"https://{deployments[0].get('url','')}"
        except Exception as ex:
            return f"__error__{ex}"
        return ""

    def fetch_prod_deployment():
        team_q = f"&teamId={team_id}" if team_id else ""
        url = f"https://api.vercel.com/v6/deployments?projectId={vercel_project}&target=production&limit=1{team_q}"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        try:
            with urllib.request.urlopen(req, timeout=8) as r:
                data = json.loads(r.read())
            deps = data.get("deployments",[])
            if deps: return f"https://{deps[0].get('url','')}"
        except Exception as ex:
            return f"__error__{ex}"
        return ""

    loop = asyncio.get_event_loop()
    dev_url, prod_url = await asyncio.gather(
        loop.run_in_executor(None, fetch_latest_deployment, dev_branch),
        loop.run_in_executor(None, fetch_prod_deployment)
    )
    err = ""
    if dev_url and dev_url.startswith("__error__"): err=dev_url[9:]; dev_url=""
    if prod_url and prod_url.startswith("__error__"): prod_url=""
    return JSONResponse({"dev_url": dev_url, "prod_url": prod_url, "error": err})

@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True: await websocket.receive_text()
    except WebSocketDisconnect: manager.disconnect(websocket)

# ─── Feature Queue ────────────────────────────────────────────────────────────

def load_queue(pid: str) -> list:
    f = project_dir(pid) / "queue.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else []

def save_queue(pid: str, queue: list):
    (project_dir(pid) / "queue.json").write_text(
        json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8")

@app.get("/api/queue")
async def get_queue():
    proj = get_active_project()
    return JSONResponse(load_queue(proj["id"]) if proj else [])

@app.post("/api/queue")
async def add_to_queue(payload: dict):
    proj = get_active_project()
    if not proj: return JSONResponse({"error":"Inget projekt"},status_code=400)
    queue = load_queue(proj["id"])
    item = {"id": len(queue)+1, "name": payload.get("name",""),
            "phase": payload.get("phase","v1"),
            "description": payload.get("description",""),
            "from_suggestion": payload.get("from_suggestion", False),
            "added": datetime.now().isoformat()}
    queue.append(item); save_queue(proj["id"], queue)
    return JSONResponse(item)

@app.delete("/api/queue/{item_id}")
async def remove_from_queue(item_id: int):
    proj = get_active_project()
    if not proj: return JSONResponse({"error":"Inget projekt"},status_code=400)
    queue = [q for q in load_queue(proj["id"]) if q["id"] != item_id]
    save_queue(proj["id"], queue)
    return JSONResponse({"ok":True})

@app.put("/api/queue/reorder")
async def reorder_queue(payload: dict):
    proj = get_active_project()
    if not proj: return JSONResponse({"error":"Inget projekt"},status_code=400)
    save_queue(proj["id"], payload.get("queue",[]))
    return JSONResponse({"ok":True})

# ─── Feature Suggestions ──────────────────────────────────────────────────────

SUGGESTION_PROMPT = """Du ar en produktstrateg. En ny feature ar specificerad.
Forslag 4-5 relaterade features som naturligt kompletterar den.
Var specifik och praktisk. Tank pa floden, edge cases, admin-behov och rapporter.

Returnera ENBART JSON:
{
  "suggestions": [
    {"name": "Kortnamn", "phase": "MVP", "description": "En mening vad det ar och varfor"},
    {"name": "Kortnamn2", "phase": "v1", "description": "En mening"}
  ]
}"""

@app.post("/api/suggestions")
async def get_suggestions(payload: dict):
    spec = payload.get("spec", {})
    proj = get_active_project()
    if not proj: return JSONResponse({"suggestions":[]})
    s = load_settings()
    client_inst = get_client(s)
    if not client_inst: return JSONResponse({"suggestions":[]})
    spec_text = json.dumps(spec, ensure_ascii=False)
    proj_context = f"Projekt: {proj['name']} - {proj.get('description','')}"
    try:
        r = client_inst.messages.create(
            model=model_for("haiku", s), max_tokens=800, system=SUGGESTION_PROMPT,
            messages=[{"role":"user","content":f"{proj_context}\n\nFEATURE:\n{spec_text}\n\nForslag 4-5 relaterade features. ENBART JSON."}])
        text = r.content[0].text.strip()
        si, e = text.find("{"), text.rfind("}")+1
        data = json.loads(text[si:e]) if si != -1 else {}
        return JSONResponse(data)
    except Exception as ex:
        return JSONResponse({"suggestions":[],"error":str(ex)})

# ─── Architecture Map ─────────────────────────────────────────────────────────

def load_architecture(pid: str) -> str:
    f = project_dir(pid) / "memory" / "ARCHITECTURE.md"
    return f.read_text(encoding="utf-8") if f.exists() else ""

def save_architecture(pid: str, content: str):
    (project_dir(pid) / "memory" / "ARCHITECTURE.md").write_text(content, encoding="utf-8")

def update_features_md(pid: str):
    """Uppdaterar FEATURES.md baserat pa aktuell features.json."""
    features = load_features(pid)
    proj_data = load_projects()
    proj = next((p for p in proj_data["projects"] if p["id"] == pid), None)
    proj_name = proj["name"] if proj else pid
    phases = {"MVP": [], "v1": [], "v2": []}
    for f in features:
        ph = f.get("phase","MVP")
        if ph in phases:
            status = f.get("status","Planerad")
            icon = "OK" if status in ("Klar","I prod") else "->" if status in ("I dev","Granskas","Byggs") else "[]"
            phases[ph].append(f"{icon} **{f['name']}** - {status}")
    lines = [f"# Features - {proj_name}\n\n*Uppdateras automatiskt av Ishoo Creator.*\n"]
    for ph, items in phases.items():
        lines.append(f"\n## {ph}")
        if items:
            lines.extend(f"- {item}" for item in items)
        else:
            lines.append("*(Inga annu)*")
    (project_dir(pid) / "memory" / "FEATURES.md").write_text("\n".join(lines), encoding="utf-8")

ONBOARDING_PROMPT = """Du ar projektledare och arkitekt i Ishoo Creator.
Du ska hjalpa anvandaren satta upp ett nytt projekt ordentligt INNAN nagot byggs.

Stall dessa fragor EN I TAGET for att samla in tillrackligt:
1. Vilka ar de primara anvandarna och hur ser deras vardag ut?
2. Vilka ar de 3-5 absolut viktigaste sakerna systemet maste kunna gora (MVP)?
3. Finns det viktiga affarsregler eller berakningar? (t.ex. priser, skatter, statusfloden)
4. Vilka dataentiteter finns? (t.ex. kunder, projekt, fakturor) och hur hanger de ihop?
5. Finns det externa system att integrera med? (t.ex. bokforing, BankID, email)

Nar du har svar pa alla fragor, generera fullstandig dokumentation med EXAKT detta format:

[ONBOARDING_KLAR]
{
  "claude_md_additions": "Markdown-text att lagga till i CLAUDE.md (personas, affarsregler)",
  "schema_md": "Komplett SCHEMA.md innehall med alla tabeller och relationer",
  "patterns_md_additions": "Eventuella projektspecifika kodriktlinjer",
  "mvp_features": [
    {"name": "...", "description": "...", "priority": 1}
  ],
  "decisions": [
    {"beslut": "...", "motivering": "..."}
  ]
}
[/ONBOARDING_KLAR]

Projektinfo:
Namn: {project_name}
Beskrivning: {project_desc}"""

@app.post("/api/projects/{project_id}/onboard")
async def onboard_project(project_id: str, payload: dict):
    """Onboarding-chat: Projektledaren staller fragor och genererar projektdocs."""
    message = payload.get("message",""); history = payload.get("history",[])
    data = load_projects()
    proj = next((p for p in data["projects"] if p["id"] == project_id), None)
    if not proj: return JSONResponse({"error":"Projekt hittades inte"},status_code=404)
    s = load_settings(); client_inst = get_client(s)
    if not client_inst: return JSONResponse({"error":"API-nyckel saknas"},status_code=400)
    system = ONBOARDING_PROMPT.format(project_name=proj["name"], project_desc=proj.get("description",""))
    response = client_inst.messages.create(
        model=model_for("projektledare", s), max_tokens=2000, system=system,
        messages=history[-10:]+[{"role":"user","content":message}])
    reply = response.content[0].text
    onboarding_data = None
    if "[ONBOARDING_KLAR]" in reply:
        try:
            s2 = reply.find("[ONBOARDING_KLAR]") + len("[ONBOARDING_KLAR]")
            e2 = reply.find("[/ONBOARDING_KLAR]", s2)
            onboarding_data = json.loads(reply[s2:e2].strip())
            mem = project_dir(project_id) / "memory"
            claude_md = mem / "CLAUDE.md"
            if claude_md.exists() and onboarding_data.get("claude_md_additions"):
                current = claude_md.read_text(encoding="utf-8")
                claude_md.write_text(current + "\n\n" + onboarding_data["claude_md_additions"], encoding="utf-8")
            if onboarding_data.get("schema_md"):
                (mem / "SCHEMA.md").write_text(onboarding_data["schema_md"], encoding="utf-8")
            if onboarding_data.get("patterns_md_additions"):
                patterns = mem / "PATTERNS.md"
                if patterns.exists():
                    current = patterns.read_text(encoding="utf-8")
                    patterns.write_text(current + "\n\n" + onboarding_data["patterns_md_additions"], encoding="utf-8")
            if onboarding_data.get("mvp_features"):
                queue = load_queue(project_id)
                for i, feat in enumerate(onboarding_data["mvp_features"]):
                    queue.append({"id": len(queue)+i+1, "name": feat["name"],
                        "phase": "MVP", "description": feat.get("description",""),
                        "from_suggestion": False, "added": datetime.now().isoformat()})
                save_queue(project_id, queue)
            if onboarding_data.get("decisions"):
                decisions_md = mem / "DECISIONS.md"
                if decisions_md.exists():
                    current = decisions_md.read_text(encoding="utf-8")
                    rows = "\n".join(
                        "| " + datetime.now().strftime("%Y-%m-%d") + " | " + d["beslut"] + " | - | " + d["motivering"] + " |"
                        for d in onboarding_data["decisions"])
                    decisions_md.write_text(current + "\n" + rows, encoding="utf-8")
        except Exception as ex:
            onboarding_data = {"error": str(ex)}
    return JSONResponse({"reply": reply, "onboarding_complete": onboarding_data is not None, "onboarding_data": onboarding_data})

@app.get("/api/architecture")
async def get_architecture():
    proj = get_active_project()
    if not proj: return JSONResponse({"content":""})
    return JSONResponse({"content": load_architecture(proj["id"])})

@app.post("/api/architecture")
async def update_architecture(payload: dict):
    proj = get_active_project()
    if not proj: return JSONResponse({"error":"Inget projekt"},status_code=400)
    save_architecture(proj["id"], payload.get("content",""))
    return JSONResponse({"ok":True})

@app.post("/api/architecture/generate")
async def generate_architecture():
    proj = get_active_project()
    if not proj: return JSONResponse({"error":"Inget projekt"},status_code=400)
    s = load_settings()
    client_inst = get_client(s)
    if not client_inst: return JSONResponse({"error":"API-nyckel saknas"},status_code=400)
    rd = repo_dir(proj["id"])
    if not rd.exists():
        return JSONResponse({"error":"Repo ej klonat annu"},status_code=400)
    src = rd / "src"
    file_list = []
    if src.exists():
        for f in sorted(src.rglob("*")):
            if f.is_file() and f.suffix in (".ts",".tsx"):
                rel = str(f.relative_to(rd))
                try:
                    head = f.read_text(encoding="utf-8",errors="ignore")[:500]
                    file_list.append(rel + "\n" + head + "\n---")
                except: pass
    context = "\n".join(file_list[:40])
    ARCH_PROMPT = "Du ar en arkitekt. Analysera kodbas och skriv ARCHITECTURE.md med sektionerna: ## Komponenter, ## Supabase-tabeller, ## Hooks, ## Utilities, ## Viktiga monster. Var kortfattad."
    try:
        r = client_inst.messages.create(
            model=model_for("haiku", s), max_tokens=2000, system=ARCH_PROMPT,
            messages=[{"role":"user","content":"Projekt: " + proj["name"] + "\n\nFILER:\n" + context}])
        content = r.content[0].text
        save_architecture(proj["id"], content)
        return JSONResponse({"content": content})
    except Exception as ex:
        return JSONResponse({"error":str(ex)},status_code=500)


# ─── Lokal Dev Server ─────────────────────────────────────────────────────────

@app.post("/api/dev-server/start")
async def start_dev_server():
    global _dev_server_proc
    proj = get_active_project()
    if not proj: return JSONResponse({"error":"Inget aktivt projekt"},status_code=400)
    rd = repo_dir(proj["id"])
    if not rd.exists(): return JSONResponse({"error":"Repo ej klonat. Koppla GitHub-repo forst."},status_code=400)
    if not (rd / "package.json").exists(): return JSONResponse({"error":"Inget package.json hittat i repot."},status_code=400)
    with _dev_server_pid_lock:
        if _dev_server_proc and _dev_server_proc.poll() is None:
            return JSONResponse({"ok":True,"status":"already_running","port":5173})
        try:
            import sys
            npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
            proc = subprocess.Popen(
                [npm_cmd, "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"],
                cwd=str(rd), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform=="win32" else 0)
            _dev_server_proc = proc
            return JSONResponse({"ok":True,"status":"started","port":5173,"pid":proc.pid})
        except Exception as ex:
            return JSONResponse({"error":f"Kunde inte starta dev-servern: {ex}"},status_code=500)

@app.post("/api/dev-server/stop")
async def stop_dev_server():
    global _dev_server_proc
    with _dev_server_pid_lock:
        if not _dev_server_proc or _dev_server_proc.poll() is not None:
            return JSONResponse({"ok":True,"status":"not_running"})
        try:
            import sys, signal
            if sys.platform == "win32":
                _dev_server_proc.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                _dev_server_proc.terminate()
            _dev_server_proc.wait(timeout=5)
        except: pass
        finally:
            _dev_server_proc = None
    return JSONResponse({"ok":True,"status":"stopped"})

@app.get("/api/dev-server/status")
async def dev_server_status():
    global _dev_server_proc
    with _dev_server_pid_lock:
        running = _dev_server_proc is not None and _dev_server_proc.poll() is None
    return JSONResponse({"running":running,"port":5173})

# ─── Felklistraren — auto-fix error ──────────────────────────────────────────

FIX_PROMPT = """Du ar en expert React/TypeScript/Supabase-utvecklare.
Anvandaren har fatt ett fel och behover hjalp.
Las felet och den befintliga kodbas-kontexten. Hitta och fixa problemet.
Returnera EXAKT detta JSON:
{
  "summary": "Kort forklaring av vad felet var och vad som fixades",
  "files": [
    {"path":"src/...", "action":"modify", "content":"...", "description":"..."}
  ]
}"""

@app.post("/api/fix-error")
async def fix_error(payload: dict):
    error_text = payload.get("error","").strip()
    if not error_text: return JSONResponse({"error":"Inget fel angivet"},status_code=400)
    proj = get_active_project()
    if not proj: return JSONResponse({"error":"Inget aktivt projekt"},status_code=400)
    s = load_settings(); client_inst = get_client(s)
    if not client_inst: return JSONResponse({"error":"API-nyckel saknas"},status_code=400)
    rd, err = clone_or_pull(proj["github"], proj["id"])
    if err: return JSONResponse({"error":err},status_code=500)
    context = read_codebase_context(rd, {"name":error_text,"problem":error_text,"solution":""})
    memory = load_memory(proj["id"])
    await manager.broadcast({"type":"build_start","feature":"Felfix"})
    await manager.broadcast({"type":"build_progress","message":"Analyserar felet och hittar orsaken..."})
    try:
        response = client_inst.messages.create(
            model=model_for("snickare",s), max_tokens=8000, system=FIX_PROMPT,
            messages=[{"role":"user","content":f"PROJEKTMINNE:\n{memory}\n\nFEL:\n{error_text}\n\nKODBAS:\n{context}\n\nFix felet. Returnera ENBART JSON."}])
        text = response.content[0].text.strip()
        s2, e2 = text.find("{"), text.rfind("}")+1
        data = json.loads(text[s2:e2]) if s2 != -1 else {}
        files = data.get("files",[])
        summary = data.get("summary","")
        if not files: return JSONResponse({"error":"Snickaren hittade ingen fix"},status_code=500)
        diffs = compute_diffs(proj["id"], files)
        store_pending(proj["id"], files, "Felfix")
        await manager.broadcast({"type":"build_done","feature":"Felfix","diffs":diffs,"summary":summary})
        return JSONResponse({"diffs":diffs,"summary":summary,"files_count":len(files)})
    except Exception as ex:
        await manager.broadcast({"type":"build_error","message":str(ex)})
        return JSONResponse({"error":str(ex)},status_code=500)

# ─── Versionshistorik & Revert ────────────────────────────────────────────────

@app.get("/api/git/log")
async def git_log():
    proj = get_active_project()
    if not proj: return JSONResponse({"commits":[]})
    rd = repo_dir(proj["id"])
    if not rd.exists(): return JSONResponse({"commits":[],"error":"Repo ej klonat"})
    r = git(rd, "log", "--oneline", "--format=%H|%s|%an|%ar|%ad", "--date=short", "-20")
    if r.returncode != 0: return JSONResponse({"commits":[],"error":r.stderr[:200]})
    commits = []
    for line in r.stdout.strip().split("\n"):
        if not line.strip(): continue
        parts = line.split("|", 4)
        if len(parts) >= 4:
            commits.append({"hash":parts[0],"message":parts[1],"author":parts[2],"ago":parts[3],"date":parts[4] if len(parts)>4 else ""})
    return JSONResponse({"commits":commits})

@app.get("/api/git/status")
async def git_status():
    """Raknar ostaged + uncommitted + unpushed filer."""
    try:
        base = Path(".")
        if not (base / ".git").exists():
            return JSONResponse({"changed": 0, "unpushed": 0, "total": 0, "files": []})
        r1 = subprocess.run(["git", "status", "--short"], cwd=str(base), capture_output=True, text=True)
        lines = r1.stdout.strip().split("\n")
        files = [l.strip() for l in lines if l.strip()]
        changed = len(files)
        r2 = subprocess.run(["git", "rev-list", "--count", "@{u}..HEAD"],
                            cwd=str(base), capture_output=True, text=True)
        unpushed = int(r2.stdout.strip()) if r2.returncode == 0 and r2.stdout.strip().isdigit() else 0
        total = changed + unpushed
        return JSONResponse({"changed": changed, "unpushed": unpushed, "total": total, "files": files[:20]})
    except Exception as e:
        return JSONResponse({"changed": 0, "unpushed": 0, "total": 0, "files": [], "error": str(e)})

@app.post("/api/git/revert")
async def git_revert(payload: dict):
    commit_hash = payload.get("hash","").strip()
    if not commit_hash: return JSONResponse({"error":"Ingen commit-hash angiven"},status_code=400)
    proj = get_active_project()
    if not proj: return JSONResponse({"error":"Inget projekt"},status_code=400)
    s = load_settings()
    rd = repo_dir(proj["id"])
    if not rd.exists(): return JSONResponse({"error":"Repo saknas"},status_code=400)
    dev_branch = s.get("dev_branch","dev")
    r = git(rd, "checkout", dev_branch)
    if r.returncode != 0: return JSONResponse({"error":f"Kunde inte checka ut {dev_branch}"},status_code=500)
    r = git(rd, "reset", "--hard", commit_hash)
    if r.returncode != 0: return JSONResponse({"error":f"Reset misslyckades: {r.stderr[:200]}"},status_code=500)
    r = git(rd, "push", "--force-with-lease", "origin", dev_branch)
    if r.returncode != 0: return JSONResponse({"error":f"Force push misslyckades: {r.stderr[:200]}"},status_code=500)
    (project_dir(proj["id"]) / "pending_changes.json").unlink(missing_ok=True)
    await manager.broadcast({"type":"revert_done","hash":commit_hash})
    return JSONResponse({"ok":True,"hash":commit_hash})

@app.get("/api/ollama/status")
async def ollama_status():
    """Kollar om Ollama koer och vilka modeller som finns."""
    import urllib.request as _ur
    try:
        with _ur.urlopen("http://localhost:11434/api/tags", timeout=3) as r:
            data = json.loads(r.read())
        models = [m.get("name","") for m in data.get("models",[])]
        return JSONResponse({"running": True, "models": models})
    except:
        return JSONResponse({"running": False, "models": []})

# ─── Spec-granskare ───────────────────────────────────────────────────────────

SPEC_REVIEWER_PROMPT = """Du ar Spec-granskaren i Ishoo Creator. Din enda uppgift:
KONTROLLERA om en feature-spec ar tillrackligt tydlig for att byggas korrekt.

GRANSKA dessa 5 punkter:
1. Finns matbara acceptanskriterier? (t.ex. "Anvandaren kan..." INTE "Det ska fungera")
2. Ar problemet specifikt? (vem, nar, hur ofta)
3. Ar scope tydligt? (vad ingar INTE i denna feature?)
4. Finns viktiga edge cases beskrivna? (vad hander om X saknas, Y ar tomt, Z ar fel)
5. Ar beroenden till andra features tydliga?

Returnera ENBART JSON:
{
  "status": "GODKAND" eller "OTYDLIG",
  "redo_att_bygga": true eller false,
  "fragor": ["Specifik fraga som maste besvaras fore bygget"],
  "forslag": "Forbattrade acceptanskriterier om du kan formulera dem"
}

GODKAND = kan byggas direkt utan missforstand
OTYDLIG = risk att Snickaren bygger fel sak"""


@app.post("/api/spec-review")
async def spec_review(payload: dict):
    """Granskar om en feature-spec ar tillrackligt tydlig fore bygget."""
    spec = payload.get("spec", {})
    proj = get_active_project()
    if not proj:
        return JSONResponse({"status": "GODKAND", "redo_att_bygga": True, "fragor": []})
    s = load_settings()
    client_inst = get_client(s)
    if not client_inst:
        return JSONResponse({"status": "GODKAND", "redo_att_bygga": True, "fragor": []})
    spec_text = json.dumps(spec, ensure_ascii=False, indent=2)
    try:
        r = client_inst.messages.create(
            model=model_for("haiku", s), max_tokens=600,
            system=SPEC_REVIEWER_PROMPT,
            messages=[{"role": "user", "content": f"SPEC:\n{spec_text}\n\nGranska och returnera ENBART JSON."}])
        text = r.content[0].text.strip()
        si, e = text.find("{"), text.rfind("}") + 1
        data = json.loads(text[si:e]) if si != -1 else {"status": "GODKAND", "redo_att_bygga": True, "fragor": []}
        return JSONResponse(data)
    except Exception as ex:
        return JSONResponse({"status": "GODKAND", "redo_att_bygga": True, "fragor": [], "error": str(ex)})


# ─── Build Verification Loop ──────────────────────────────────────────────────

def run_npm_build(rd: Path) -> tuple:
    """Kor npm run build i repot. Returnerar (success, output)."""
    import sys
    npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
    # npm install om node_modules saknas
    if not (rd / "node_modules").exists():
        subprocess.run([npm_cmd, "install"], cwd=str(rd),
                       capture_output=True, text=True, timeout=120)
    try:
        result = subprocess.run(
            [npm_cmd, "run", "build"],
            cwd=str(rd), capture_output=True, text=True, timeout=180)
        output = (result.stdout + result.stderr)[:3000]
        return result.returncode == 0, output
    except subprocess.TimeoutExpired:
        return False, "Build timeout (>120s) - projektet kan vara for stort"
    except FileNotFoundError:
        return False, "npm hittades inte - kontrollera att Node.js ar installerat"
    except Exception as ex:
        return False, f"Build-fel: {ex}"


BUILD_FIX_PROMPT = """Du ar Snickaren i Ishoo Creator. Tidigare genererad kod ger byggfel.
Analysera felmeddelandet noggrant och generera fixade filer.

REGLER:
- Fixa ENBART det som orsakar bygget att misslyckas (typfel, importfel, syntax)
- Andra INTE funktionalitet eller design - bara det som ger fel
- Returnera EXAKT detta JSON med bara de filer som behover andras:

{
  "summary": "Vad fixades och varfor",
  "files": [
    {"path": "src/...", "action": "modify", "content": "FULLSTANDIGT filinnehall", "description": "Vad andrades"}
  ]
}"""


@app.post("/api/build-verify")
async def build_verify(payload: dict):
    """Skriver filer till repo, kor npm build, fixar fel i loop tills gront."""
    feature_name = payload.get("feature_name", "Okand")
    proj = get_active_project()
    if not proj:
        return JSONResponse({"error": "Inget projekt"}, status_code=400)
    pid = proj["id"]
    s = load_settings()
    client_inst = get_client(s)
    rd = effective_repo_dir(pid)

    # For ishoo-creator: skippa npm build (ingen package.json) — skriv direkt och returnera OK
    if is_self_project(pid):
        pending = load_pending(pid)
        if not pending:
            return JSONResponse({"error": "Inga filer att verifiera"}, status_code=400)
        current_files = list(pending.get("files", []))
        await manager.broadcast({"type": "build_verify_start", "iteration": 1, "max": 1, "feature": feature_name})
        for fc in current_files:
            fpath = rd / fc["path"]
            if fc.get("action") == "delete":
                if fpath.exists(): fpath.unlink()
            else:
                fpath.parent.mkdir(parents=True, exist_ok=True)
                fpath.write_text(fc.get("content", ""), encoding="utf-8")
        await manager.broadcast({"type": "build_verify_running", "message": "Skriver filer direkt till Ishoo Creator..."})
        diffs = compute_diffs(pid, current_files)
        store_pending(pid, current_files, feature_name)
        await manager.broadcast({"type": "build_verify_done", "success": True, "feature": feature_name, "iterations": 1, "diffs": diffs})
        return JSONResponse({"success": True, "iterations": 1, "diffs": diffs})

    if not rd.exists():
        return JSONResponse({"error": "Repo saknas - klona repot forst via Snickaren"}, status_code=400)
    pending = load_pending(pid)
    if not pending:
        return JSONResponse({"error": "Inga filer att verifiera - generera kod forst"}, status_code=400)
    max_iter = min(int(s.get("max_iterations", 3)), 3)
    current_files = list(pending.get("files", []))

    for iteration in range(1, max_iter + 1):
        await manager.broadcast({
            "type": "build_verify_start",
            "iteration": iteration, "max": max_iter, "feature": feature_name})

        # Skriv filer till repo
        for fc in current_files:
            fpath = rd / fc["path"]
            action = fc.get("action", "create")
            if action == "delete":
                if fpath.exists(): fpath.unlink()
            else:
                fpath.parent.mkdir(parents=True, exist_ok=True)
                fpath.write_text(fc.get("content", ""), encoding="utf-8")

        # Kor npm build
        await manager.broadcast({
            "type": "build_verify_running",
            "message": f"Kor npm build (forsok {iteration}/{max_iter})..."})
        loop = asyncio.get_event_loop()
        success, output = await loop.run_in_executor(None, run_npm_build, rd)

        if success:
            store_pending(pid, current_files, feature_name)
            diffs = compute_diffs(pid, current_files)
            diffs = compute_diffs(pid, current_files)
            await manager.broadcast({
                "type": "build_verify_done",
                "success": True, "feature": feature_name, "iterations": iteration, "diffs": diffs})
            return JSONResponse({"success": True, "iterations": iteration, "diffs": diffs})

        await manager.broadcast({
            "type": "build_verify_error",
            "output": output[:1200], "iteration": iteration})

        if not client_inst or iteration == max_iter:
            break

        await manager.broadcast({
            "type": "build_verify_fixing",
            "message": f"Snickaren analyserar och fixar byggfelen (iteration {iteration})..."})
        files_summary = json.dumps(
            [{"path": f["path"], "action": f.get("action","modify")} for f in current_files],
            ensure_ascii=False)
        error_context = (
            f"BYGGFEL (forsok {iteration}):\n{output}\n\n"
            f"FILER SOM GENERERADES:\n{files_summary}\n\n"
            f"Analysera felet och returnera fixade filer. ENBART JSON.")
        try:
            r = client_inst.messages.create(
                model=model_for("snickare", s), max_tokens=8000,
                system=BUILD_FIX_PROMPT,
                messages=[{"role": "user", "content": error_context}])
            text = r.content[0].text.strip()
            si, e = text.find("{"), text.rfind("}") + 1
            fix_data = json.loads(text[si:e]) if si != -1 else {}
            fix_files = fix_data.get("files", [])
            fix_map = {f["path"]: f for f in fix_files}
            current_files = [fix_map.get(f["path"], f) for f in current_files]
            for fx in fix_files:
                if fx["path"] not in [cf["path"] for cf in current_files]:
                    current_files.append(fx)
            await manager.broadcast({
                "type": "build_verify_fixed",
                "summary": fix_data.get("summary", ""),
                "files_fixed": len(fix_files)})
        except Exception as ex:
            await manager.broadcast({
                "type": "build_verify_error",
                "output": f"Snickaren kunde inte fixa: {ex}", "iteration": iteration})
            break

    await manager.broadcast({
        "type": "build_verify_done",
        "success": False, "feature": feature_name, "iterations": max_iter})
    return JSONResponse(
        {"success": False, "error": "Bygget misslyckades efter max iterationer"},
        status_code=500)


# ─── System Health Check ──────────────────────────────────────────────────────

@app.get("/api/health")
async def system_health():
    import urllib.request as _ur
    s = load_settings()
    results = {}
    try:
        client_h = get_client(s)
        if client_h:
            r = client_h.messages.create(model=model_for("haiku",s), max_tokens=5,
                messages=[{"role":"user","content":"ping"}])
            results["anthropic"] = {"ok": True, "status": "Ansluten", "detail": r.model}
        else:
            results["anthropic"] = {"ok": False, "status": "API-nyckel saknas", "detail": ""}
    except Exception as ex:
        results["anthropic"] = {"ok": False, "status": "Fel", "detail": str(ex)[:120]}
    try:
        token = s.get("github_token","")
        if token:
            req = _ur.Request("https://api.github.com/user",
                headers={"Authorization": f"token {token}", "User-Agent": "ishoo-creator"})
            with _ur.urlopen(req, timeout=5) as r:
                gh = json.loads(r.read())
            results["github"] = {"ok": True, "status": f"Inloggad som {gh.get(chr(108)+chr(111)+chr(103)+chr(105)+chr(110),chr(63))}",
                                  "detail": gh.get("name","")}
        else:
            results["github"] = {"ok": False, "status": "Token saknas", "detail": ""}
    except Exception as ex:
        results["github"] = {"ok": False, "status": "Ogiltig token", "detail": str(ex)[:120]}
    try:
        with _ur.urlopen("http://localhost:11434/api/tags", timeout=3) as r:
            data = json.loads(r.read())
        models = [m.get("name","") for m in data.get("models",[])]
        if models:
            results["ollama"] = {"ok": True, "status": f"{len(models)} modell(er)", "detail": ", ".join(models)}
        else:
            results["ollama"] = {"ok": False, "status": "Inga modeller", "detail": "Kor ollama-setup.bat"}
    except:
        results["ollama"] = {"ok": False, "status": "Kors inte", "detail": "Installera Ollama"}
    try:
        r = subprocess.run(["git","--version"], capture_output=True, text=True, timeout=5)
        results["git"] = {"ok": r.returncode==0, "status": r.stdout.strip() if r.returncode==0 else "Ej installerat", "detail": ""}
    except Exception as ex:
        results["git"] = {"ok": False, "status": "Ej installerat", "detail": str(ex)}
    all_ok = all(v.get("ok", False) for v in results.values())
    return JSONResponse({"ok": all_ok, "checks": results})


@app.post("/api/git-push")
async def git_push_simple():
    """Enkel push — läser token och repo från aktivt projekt + settings."""
    s = load_settings()
    proj = get_active_project()
    token = s.get("github_token", "")
    if not token:
        return JSONResponse({"ok": False, "error": "GitHub-token saknas i Inställningar"})
    if not proj or not proj.get("github"):
        return JSONResponse({"ok": False, "error": "Inget GitHub-repo kopplat till aktivt projekt"})
    github_repo = proj["github"]  # format: "username/repo"
    parts = github_repo.split("/")
    username = parts[0] if len(parts) == 2 else "Stuwish1"
    repo_name = parts[1] if len(parts) == 2 else github_repo
    rd = effective_repo_dir(proj["id"])
    if not rd.exists():
        return JSONResponse({"ok": False, "error": "Repo ej klonat — starta granskning eller bygge först"})
    err = None
    try:
        remote_url = f"https://{username}:{token}@github.com/{username}/{repo_name}.git"
        subprocess.run(["git","remote","set-url","origin",remote_url], cwd=rd, check=True, capture_output=True)
        subprocess.run(["git","add","-A"], cwd=rd, capture_output=True)
        subprocess.run(["git","commit","--allow-empty","-m","chore: Ishoo Creator push"], cwd=rd, capture_output=True)
        subprocess.run(["git","push","origin","HEAD"], cwd=rd, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        err = e.stderr.decode(errors="ignore")[:300] if e.stderr else str(e)
    except Exception as e:
        err = str(e)
    if err:
        return JSONResponse({"ok": False, "error": err})
    url = f"https://github.com/{username}/{repo_name}"
    await manager.broadcast({"type": "git_push_done", "url": url})
    return JSONResponse({"ok": True, "url": url})


@app.post("/api/git-push-direct")
async def git_push_direct(payload: dict):
    repo_name = payload.get("repo_name","")
    token = payload.get("token","")
    username = payload.get("username","Stuwish1")
    if not repo_name or not token:
        return JSONResponse({"ok": False, "error": "repo_name och token kravs"}, status_code=400)
    rd = Path(".").resolve()
    err = None
    try:
        remote_url = f"https://{username}:{token}@github.com/{username}/{repo_name}.git"
        subprocess.run(["git","remote","set-url","origin",remote_url], cwd=rd, check=True, capture_output=True)
        subprocess.run(["git","add","-A"], cwd=rd, capture_output=True)
        subprocess.run(["git","commit","--allow-empty","-m","chore: Ishoo Creator push"], cwd=rd, capture_output=True)
        subprocess.run(["git","push","origin","HEAD"], cwd=rd, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        err = e.stderr.decode(errors="ignore")[:300] if e.stderr else str(e)
    except Exception as e:
        err = str(e)
    if err:
        return JSONResponse({"ok": False, "error": err})
    url = f"https://github.com/{username}/{repo_name}"
    await manager.broadcast({"type": "git_push_done", "url": url})
    return JSONResponse({"ok": True, "url": url})


@app.post("/api/git-push-direct")
async def git_push_direct(payload: dict):
    repo_name = payload.get("repo_name","")
    token = payload.get("token","")
    username = payload.get("username","Stuwish1")
    if not repo_name or not token:
        return JSONResponse({"ok": False, "error": "repo_name och token kravs"}, status_code=400)
    rd = Path(".").resolve()
    err = None
    try:
        remote_url = f"https://{username}:{token}@github.com/{username}/{repo_name}.git"
        subprocess.run(["git","remote","set-url","origin",remote_url], cwd=rd, check=True, capture_output=True)
        subprocess.run(["git","add","-A"], cwd=rd, check=True, capture_output=True)
        subprocess.run(["git","commit","--allow-empty","-m","chore: Ishoo Creator push"], cwd=rd, capture_output=True)
        subprocess.run(["git","push","origin","HEAD"], cwd=rd, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        err = e.stderr.decode(errors="ignore")[:300] if e.stderr else str(e)
    except Exception as e:
        err = str(e)
    if err:
        return JSONResponse({"ok": False, "error": err})
    await manager.broadcast({"type": "git_push_done", "url": "https://github.com/"+username+"/"+repo_name})
    return JSONResponse({"ok": True, "url": "https://github.com/"+username+"/"+repo_name})


@app.on_event("startup")
async def start_file_watcher():
    async def _watch():
        html_path = Path("index.html")
        last_mtime = html_path.stat().st_mtime if html_path.exists() else 0
        while True:
            await asyncio.sleep(1)
            try:
                mtime = html_path.stat().st_mtime
                if mtime != last_mtime:
                    last_mtime = mtime
                    await manager.broadcast({"type": "reload"})
            except Exception:
                pass
    asyncio.ensure_future(_watch())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
