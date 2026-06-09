"""
agents_config.py — Agent-definitioner, prompts och konfiguration.
Importeras av app.py. Ändra prompts och agenter här.
"""

DEFAULT_AGENTS = [

    # ══ STEG 0: SPEC-GRANSKNING (kör alltid, kan stoppa pipelinen direkt) ══════

    # ── Kravanalytikorn ──────────────────────────────────────────────────────────
    {"id":"kravanalytiker","name":"Kravanalytikorn","emoji":"🔍","model":"haiku","enabled":True,
     "prompt":'''Du granskar om spec är byggbar. Var EXTREMT generös.

Kod-fixar, bugg-fixar, tekniska förbättringar och iterativa ändringar GODKÄNNS alltid.
AVVISAD HIGH ENBART om: spec är helt tom (0-3 ord utan mening).
I alla andra fall returnerar du GODKÄND.

Returnera ENBART JSON: {"status":"GODKÄND","findings":[],"severity":"LOW","suggestions":[]}'''},

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
    {"id":"uidesigner","name":"UI Designern","emoji":"🖼️","model":"sonnet","enabled":True,
     "prompt":'''Du är UI Designer. Ge KONKRETA designbeslut för featuren.
Vilka komponenter? Vilken layout? Färger, spacing, responsivitet.
Returnera ENBART JSON:
{"status":"GODKÄND","findings":["Komponent X med layout Y"],"severity":"LOW","suggestions":["CSS-klass eller designmönster"]}'''},

    {"id":"frontend","name":"Frontend Kodaren","emoji":"💻","model":"sonnet","enabled":True,
     "prompt":'''Du är Frontend Kodare. Ge Snickaren EXAKTA implementationsinstruktioner.
Vilka filer? Vilket state-hantering? Hur ska fetch struktureras?
Returnera ENBART JSON:
{"status":"GODKÄND","findings":["Konkret impl-detalj"],"severity":"LOW","suggestions":["Exakt kod-mönster"]}'''},

    {"id":"backend","name":"Backend Kodaren","emoji":"⚙️","model":"sonnet","enabled":True,
     "prompt":'''Du är Backend Kodare. Ge Snickaren EXAKTA API-instruktioner.
Vilka endpoints? Request/response-schema? Felhantering? Dubblera aldrig befintliga endpoints.
Returnera ENBART JSON:
{"status":"GODKÄND","findings":["Konkret API-design"],"severity":"LOW","suggestions":["Exakt endpoint-struktur"]}'''},

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
    "model_snickare": OPUS_DEFAULT,
    "model_sonnet": SONNET_DEFAULT,
    "model_haiku": HAIKU_DEFAULT,
    "agents": DEFAULT_AGENTS,
}

_settings_cache2: dict = {}
_settings_mtime2: float = 0.0
def load_settings() -> dict:
    global _settings_cache2, _settings_mtime2
    stored = {}
    if SETTINGS_FILE.exists():
        try:
            mt = SETTINGS_FILE.stat().st_mtime
            if mt == _settings_mtime2: return dict(_settings_cache2)
            stored = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            _settings_mtime2 = mt
            _settings_cache2 = {**DEFAULT_SETTINGS, **stored}
            return dict(_settings_cache2)
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
    if role == "snickare":      return s.get("model_snickare", OPUS_DEFAULT)
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

SNICKARE_PROMPT = """Du är Snickaren — expert på att bygga kod och modifiera filer.
Du får en feature-spec, arkitektplan och relevanta kodsektioner.

GRUNDREGLER:
- Skriv komplett, körbar kod — inga TODO-kommentarer
- Modifiera DIREKT i rätt fil — skapa ALDRIG patch-filer, helper-skript eller install-skript
- Skapa ALDRIG filer som heter patch_*.py, install_*.py, startup_*.py eller *_patch.py
- För Python/FastAPI-projekt: skriv Python direkt i app.py. För HTML/JS: skriv direkt i index.html
- Om du ska lägga till en funktion i app.py: returnera app.py med funktionen inlagd på rätt ställe

NÄR DU ÄNDRAR EN STOR FIL (app.py, index.html):
Du får INDEX + relevanta sektioner — INTE hela filen.
Returnera BARA de ändrade funktionerna/sektionerna med tydliga markeringar:

<file>
  <path>app.py</path>
  <action>patch</action>
  <description>Vad som ändrades</description>
  <content>
# PATCH: Ersätt funktionen apply_and_push med denna version
def apply_and_push(...):
    # HELA den nya funktionen här
    ...

# PATCH: Lägg till denna nya funktion efter rad X / efter def foo():
def ny_funktion():
    ...
  </content>
</file>

NÄR DU SKAPAR EN NY FIL (<300 rader):
Returnera hela filen normalt med action=create.

RETURNERA EXAKT detta XML-format:
<response>
<summary>Kort beskrivning</summary>
<file>
  <path>relativ/sökväg/fil.py</path>
  <action>create/modify/patch/delete</action>
  <description>Vad filen gör</description>
  <content>
KOD HÄR
  </content>
</file>
</response>

KRITISKT: Skapa aldrig patch_*.py, install_*.py eller startup_*.py — integrera direkt.
KRITISKT: <content> får aldrig vara tomt.
KRITISKT: action=patch betyder att du returnerar BARA ändrade funktioner med # PATCH: kommentarer."""

async def build_code(spec: dict, pid: str) -> tuple[list, str]:
    s = load_settings()
    client_inst = get_client(s)
    if not client_inst: return [], "API-nyckel saknas. Lägg till i Inställningar."
    proj = get_active_project()
    if not proj or not proj.get("github"): return [], "Inget GitHub-repo kopplat."
    if is_self_project(pid):
        rd = effective_repo_dir(pid)
        # Ishoo Creator: Python/HTML projekt — ge Snickaren rätt kontext
        ctx_parts = ["PROJEKTTYP: Python/FastAPI backend (app.py) + vanilla HTML/JS frontend (index.html). INTE React/TypeScript."]
        spec_lower_kw = json.dumps(spec, ensure_ascii=False).lower()
        import re as _rp2
        for fname in ["app.py", "index.html"]:
            fp = rd / fname
            if fp.exists():
                raw = fp.read_text(encoding="utf-8", errors="ignore")
                raw_lines = raw.splitlines()
                idx_txt = build_file_index(fp)
                # Stor fil (>600 rader): skicka index + relevanta sektioner, inte hela filen
                if len(raw_lines) > 600:
                    kws = [w for w in spec_lower_kw.split() if len(w) > 4][:20]
                    relevant = []
                    seen = set()
                    for i2, line in enumerate(raw_lines):
                        if any(_rp2.search(r'\b' + _rp2.escape(kw) + r'\b', line.lower()) for kw in kws):
                            s2, e2 = max(0,i2-5), min(len(raw_lines),i2+20)
                            key = (s2,e2)
                            if key not in seen:
                                seen.add(key)
                                relevant.append(f"# rad {s2+1}-{e2}:\n" + "\n".join(raw_lines[s2:e2]))
                    rel_txt = "\n\n".join(relevant[:6]) or "(inga matchande sektioner)"
                    ctx_parts.append(
                        f"=== {fname} INDEX ({len(raw_lines)} rader) ===\n{idx_txt}\n\n"
                        f"=== {fname} RELEVANTA SEKTIONER ===\n{rel_txt}"
                    )
                else:
                    ctx_parts.append(
                        f"=== {fname} INDEX ===\n{idx_txt}\n\n"
                        f"=== {fname} FULL KOD ({len(raw_lines)} rader) ===\n{raw}"
                    )
        # Inkludera även JSON-datafiler om spec nämner dem
        spec_text_lower = json.dumps(spec, ensure_ascii=False).lower()
        data_files = ["features.json", "settings.json", "memory.md"]
        for data_fname in data_files:
            if any(kw in spec_text_lower for kw in [data_fname.split(".")[0], data_fname]):
                # Sök i projects-mappen
                import glob as _glob
                matches = list(_glob.glob(str(rd / "**" / data_fname), recursive=True))
                if not matches:
                    proj_data = project_dir(pid) / data_fname
                    if proj_data.exists():
                        matches = [str(proj_data)]
                for m in matches[:1]:
                    try:
                        data_content = Path(m).read_text(encoding="utf-8", errors="ignore")
                        rel = Path(m).relative_to(rd) if Path(m).is_relative_to(rd) else Path(m)
                        ctx_parts.append(f"=== {rel} (datafil) ===\n{data_content[:3000]}")
                    except Exception:
                        pass
        context = "\n\n".join(ctx_parts) if ctx_parts else "Inga filer hittades."
    else:
        rd, err = clone_or_pull(proj["github"], pid)
        if err: return [], err
        context = read_codebase_context(rd, spec)
    # Trim context om för stor (skyddar mot token-overflow)
    if len(context) > 60000:
        context = context[:60000] + "\n\n[KONTEXT TRUNKERAD — för stor]"
    spec_text = json.dumps(spec, ensure_ascii=False, indent=2)
    try:
        response = client_inst.messages.create(
            model=model_for("snickare", s), max_tokens=16000, system=SNICKARE_PROMPT,
            messages=[{"role":"user","content":f"FEATURE-SPEC:\n{spec_text}\n\nBEFINTLIG KODBAS (INDEX + SEKTIONER):\n{context}\n\nVIKTIGT: För app.py och index.html — använd action=patch och returnera BARA de ändrade funktionerna med # PATCH: prefix. Returnera ALDRIG hela filen. Generera koden nu. Returnera ENBART XML."}])
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
            # Fallback 1: JSON-block
            try:
                s2, e2 = text.find("{"), text.rfind("}")+1
                if s2 != -1:
                    d2 = json.loads(text[s2:e2])
                    files = d2.get("files",[])
                    summary = d2.get("summary", summary)
            except Exception:
                pass
        # Rensa filer med tomt content (förhindrar tomma diffs)
        # Filtrera ogiltiga filer + tidig storlek-guard
        def _valid_file(f):
            p = f.get("path","").strip()
            c = f.get("content","").strip()
            if not p or p in ("?", "unknown", "...", "path/to/file"): return False
            if f.get("action") in ("delete","patch"): return True
            if not c or len(c) < 10: return False
            return True
        files = [f for f in files if _valid_file(f)]
        # Avvisa trunkerade filer innan diff visas — patch-filer undantagna
        rd_check = effective_repo_dir(pid)
        safe_files = []
        for _f in files:
            _act = _f.get("action","create")
            _cw  = _f.get("content","").strip()
            # Patch och delete behöver inte storlek-check
            if _act == "delete":
                safe_files.append(_f); continue
            # Patch måste ha content men ingen storlek-jämförelse
            if _act == "patch":
                if _cw:
                    safe_files.append(_f)
                # tom patch hoppas över (Fix #13)
                continue
            # Modify/create: avvisa om ny fil är <30% av original
            _fp = rd_check / _f.get("path","")
            if _fp.exists() and str(_fp).endswith((".py",".html",".js")):
                _orig = len(_fp.read_text(encoding="utf-8", errors="ignore"))
                _new  = len(_cw)
                if _orig > 5000 and _new < _orig * 0.3:
                    continue  # trunkerad — hoppa över
            safe_files.append(_f)
        files = safe_files
        if not files:
            # Fallback 2: Direkt kod i svaret
            if any(kw in text for kw in ["def ", "class ", "import ", "function ", "const ", "async "]):
                main_file = "app.py"
                if spec:
                    comps = spec.get("filer_att_andra", spec.get("komponenter", []))
                    if comps:
                        main_file = str(comps[0]).split(":")[0].strip()
                files.append({"path": main_file, "action": "modify", "content": text[:12000], "description": "Extraherad"})
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

    # Applicera filer — MED SYNTAX-SKYDD
    import ast as _ast_guard, shutil as _sh_guard
    _NULL = chr(0)
    skipped = []
    for fc in pending.get("files",[]):
        fpath = rd / fc["path"]; action = fc.get("action","create")
        if action == "delete":
            if fpath.exists(): fpath.unlink()
        else:
            cw = fc.get("content","")
            # Null-byte check
            if _NULL in cw:
                skipped.append(f"AVVISAT {fc['path']}: null bytes i content")
                continue
            # Storlek-guard — avvisa trunkerade filer
            if str(fpath).endswith('.py') and fpath.exists():
                orig_size = len(fpath.read_text(encoding="utf-8", errors="ignore"))
                if orig_size > 5000 and len(cw) < orig_size * 0.3:
                    pct = int(len(cw)/orig_size*100)
                    skipped.append(f"AVVISAT {fc['path']}: ny version ({len(cw)} bytes) ar bara {pct}% av original ({orig_size} bytes) — troligen trunkerad av Snickaren")
                    continue
            # Python syntax-check
            if str(fpath).endswith('.py') and cw.strip():
                try:
                    _ast_guard.parse(cw)
                except SyntaxError as se:
                    skipped.append(f"AVVISAT {fc['path']}: SyntaxError rad {se.lineno} - {se.msg}")
                    continue
            fpath.parent.mkdir(parents=True, exist_ok=True)
            if fpath.name == "app.py" and fpath.exists():
                _sh_guard.copy2(str(fpath), str(fpath)+".bak")
            prev_size = len(fpath.read_text(encoding="utf-8",errors="ignore")) if fpath.exists() else 0
            # Patch-läge: applicera PATCH-kommenterade funktioner direkt i filen
            if action == "patch" and cw and fpath.exists() and str(fpath).endswith((".py",".html")):
                import re as _rp
                orig = fpath.read_text(encoding="utf-8", errors="ignore")
                patched = orig
                blocks = _rp.split(r"(?m)^# PATCH:", cw)
                for blk in blocks[1:]:
                    blk = blk.strip()
                    m = _rp.search(r"^(?:async )?def (\w+)", blk, _rp.MULTILINE)
                    if m:
                        fn = m.group(1)
                        # Inkludera dekoratorer (@app.post etc) ovanför funktionen
                        pat = _rp.compile(
                            r"(?:^@[^\n]+\n)*^(?:async )?def " + fn + r"\b.*?(?=^(?:@|async def |def )|\Z)",
                            _rp.MULTILINE | _rp.DOTALL)
                        if pat.search(patched):
                            patched = pat.sub(blk.rstrip() + "\n\n", patched, count=1)
                        else:
                            patched = patched.rstrip() + "\n\n" + blk + "\n"
                cw = patched
            fpath.write_text(cw, encoding="utf-8")
            # Logga stora fil-ändringar i memory (>10% storlek-förändring)
            if prev_size > 5000 and str(fpath).endswith('.py'):
                new_size = len(cw)
                change_pct = int((new_size - prev_size) / prev_size * 100)
                if abs(change_pct) > 10:
                    try:
                        mem_file = project_dir(pid) / "memory.md"
                        from datetime import datetime as _dt2
                        ts2 = _dt2.now().strftime("%Y-%m-%d %H:%M")
                        note = f"\n\n## 📝 FILÄNDRING {ts2}\n{fc['path']}: {prev_size} → {new_size} bytes ({change_pct:+d}%)\nFeature: {feature_name}\n"
                        existing2 = mem_file.read_text(encoding="utf-8") if mem_file.exists() else ""
                        mem_file.write_text(existing2 + note, encoding="utf-8")
                    except Exception:
                        pass
    if skipped:
        # Logga incidenten i memory.md
        try:
            mem_file = project_dir(pid) / "memory.md"
            from datetime import datetime as _dt
            ts = _dt.now().strftime("%Y-%m-%d %H:%M")
            incident_lines = "\n".join(skipped)
            incident_entry = f"\n\n## ⚠️ INCIDENT {ts} — Syntax-guard aktiverades\n{incident_lines}\nFeature: {feature_name}\n"
            existing = mem_file.read_text(encoding="utf-8") if mem_file.exists() else ""
            mem_file.write_text(existing + incident_entry, encoding="utf-8")
        except Exception:
            pass
        return "SYNTAX-GUARD STOPPADE:\n" + "\n".join(skipped)

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


def _gather_live_context(proj: dict) -> str:
    """Samlar och VERIFIERAR kontext för Projektledaren — fakta, inte påståenden."""
    import subprocess as _sp, ast as _ast, re as _re
    import signal as _sig
    # Samlad timeout 8s för hela funktionen
    class _Timeout(Exception): pass
    def _alarm(s,f): raise _Timeout()
    try:
        import signal as _s2
        _s2.signal(_s2.SIGALRM, _alarm)
        _s2.alarm(8)
    except (AttributeError, OSError):
        pass  # Windows har inte SIGALRM
    pid = proj["id"]
    rd = effective_repo_dir(pid)
    parts = []

    # ── Git-status + branch ──────────────────────────────────────────────────
    try:
        gs  = _sp.run(["git","status","--short"],    cwd=str(rd), capture_output=True, text=True, timeout=5)
        gl  = _sp.run(["git","log","--oneline","-8"],cwd=str(rd), capture_output=True, text=True, timeout=5)
        gbr = _sp.run(["git","branch","--show-current"], cwd=str(rd), capture_output=True, text=True, timeout=3)
        parts.append(
            f"GIT STATUS: {gs.stdout.strip() or 'Rent'}\n"
            f"BRANCH: {gbr.stdout.strip() or 'okänd'}\n"
            f"SENASTE COMMITS:\n{gl.stdout.strip() or 'Inga'}"
        )
    except Exception as e:
        parts.append(f"GIT: kunde inte köra ({e})")

    # ── Backlog ──────────────────────────────────────────────────────────────
    try:
        features = load_features(pid)
        blocked  = [f for f in features if f.get("status") == "Blockerad"]
        planerad = [f for f in features if f.get("status") == "Planerad"][:6]
        byggda   = [f for f in features if f.get("status") in ("Byggd","Klar","Pushad")][-4:]
        bl = "\n".join(f"  ⛔ {f['name']}" for f in blocked)
        pl = "\n".join(f"  · {f['name']} [{f.get('phase','?')}]" for f in planerad)
        bg = "\n".join(f"  ✅ {f['name']}" for f in byggda)
        parts.append(f"BACKLOG ({len(features)} totalt):\nBlockerade:{chr(10)+bl if bl else ' Inga'}\nPlanerade:\n{pl or '  Inga'}\nNyligen byggda:\n{bg or '  Inga'}")
    except Exception:
        pass

    # ── VERIFIERING AV KOD — faktakontroll mot disk ──────────────────────────
    # Hitta Python-filer att verifiera
    py_files = []
    for candidate in ["app.py", "main.py", "server.py", "backend.py"]:
        fp = rd / candidate
        if fp.exists():
            py_files.append(fp)
            break
    # Ishoo Creator:s egna app.py
    self_app = Path(__file__).parent / "app.py"
    if self_app.exists() and self_app not in py_files:
        py_files.append(self_app)

    verification_lines = []
    for fp in py_files[:2]:
        try:
            src = fp.read_text(encoding="utf-8", errors="ignore")
            fname = fp.name

            # Syntax-check
            try:
                _ast.parse(src)
                verification_lines.append(f"  ✅ {fname}: Python-syntax OK")
            except SyntaxError as se:
                verification_lines.append(f"  ❌ {fname}: SyntaxError rad {se.lineno} — {se.msg}")

            # Duplicerade funktioner / endpoints
            defs = _re.findall(r"^(?:async )?def (\w+)", src, _re.MULTILINE)
            dupes = [d for d in set(defs) if defs.count(d) > 1]
            if dupes:
                for d in dupes[:5]:
                    positions = [i+1 for i,line in enumerate(src.splitlines()) if _re.match(rf"(?:async )?def {d}\b", line.strip())]
                    verification_lines.append(f"  ⚠️ {fname}: DUPLICERAD FUNKTION '{d}' på rader {positions}")
            else:
                verification_lines.append(f"  ✅ {fname}: Inga duplicerade funktioner")

            # Endpoints-duplikat (FastAPI)
            routes = _re.findall(r'@app\.(get|post|put|delete|patch)\("([^"]+)"', src)
            seen_routes = {}
            for method, path in routes:
                key = f"{method.upper()} {path}"
                seen_routes[key] = seen_routes.get(key, 0) + 1
            dupe_routes = {k:v for k,v in seen_routes.items() if v > 1}
            if dupe_routes:
                for r,c in list(dupe_routes.items())[:3]:
                    verification_lines.append(f"  ⚠️ {fname}: DUPLICERAD ENDPOINT {r} ({c}x)")
            else:
                verification_lines.append(f"  ✅ {fname}: Inga duplicerade endpoints")

            # Filstorlek
            lines_count = src.count("\n") + 1
            verification_lines.append(f"  📄 {fname}: {lines_count} rader, {len(src)//1024}KB")

        except Exception as e:
            verification_lines.append(f"  ⚠️ Kunde inte verifiera {fp.name}: {e}")

    if verification_lines:
        parts.append("VERIFIERAD KOD-STATUS (körd mot disk — inte backlog-påståenden):\n" + "\n".join(verification_lines))

    # ── Fil-träd ─────────────────────────────────────────────────────────────
    try:
        if rd.exists():
            tree = "\n".join(
                f"  {'📁' if (rd/f).is_dir() else '📄'} {f}"
                for f in sorted(rd.iterdir(), key=lambda p: (p.is_file(), p.name))
                if not str(f).startswith('.') and str(f) not in ('node_modules','__pycache__','.git')
            )
            parts.append(f"FIL-TRÄD (rot):\n{tree[:600]}")
    except Exception:
        pass

    try:
        import signal as _s3; _s3.alarm(0)
    except (AttributeError, OSError): pass
    return "\n\n".join(parts) if parts else "Ingen kontext tillgänglig."


PROJEKTLEDARE_PROMPT = """Du är en extremt noggrann projektledare OCH systemarkitekt i Ishoo Creator.

PROJEKT: {project_name}
BESKRIVNING: {project_desc}
GITHUB: {project_github}

Du är en beslutssam projektledare som ALDRIG fastnar.

GRUNDREGEL: Förstå intentionen → fyll i rimliga gap → agera DIREKT.
STÄLL NOLL FRÅGOR om du kan gissa ett rimligt svar. Berätta vad du antog istället.
MAX 1 fråga totalt — bara om det är absolut omöjligt att gissa.

SPECIALREGEL — NUMMER-VAL: Om användaren skriver "1", "2", "3" eller liknande:
Tolka det som att de bekräftar det senaste alternativet/prioriteten.
Skapa featuren DIREKT utan att fråga om detaljer — använd feature-namnet + din kodanalys.
Säg aldrig "Kan du beskriva X mer exakt" — leta i koden istället.

━━━ TYP 1: FEATURE (bygga ny funktionalitet) ━━━
Gör detta omedelbart utan att fråga:
- Tolka vad som ska byggas (fyll i gaps)
- Antag: vem använder det, vilken fas (MVP om oklart)
- Skapa 2-4 konkreta acceptanskriterier
- Lägg till feature direkt

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
Inga frågor — gissa rimliga defaults och kör direkt.
Modell: haiku för snabba checks, sonnet för komplex analys.

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

━━━ TYP 3: STRATEGISK ANALYS (vad ska jag göra härnäst?) ━━━
Triggas när: användaren frågar "vad ska jag göra?", "nästa steg?", "hur mår projektet?",
"vad borde vi prioritera?", "vad är kvar?", eller liknande öppna status-frågor.

Kör alltid VERIFIERAD KOD-STATUS och backlog-data INNAN du svarar.
Analysera sedan:
1. KOD-HÄLSA — finns syntax-fel, saknade filer, duplicerade endpoints?
2. BACKLOG — vilka features är PENDING?
3. RISKER — vad är farligast att ignorera?
4. Rangordna 3 konkreta nästa steg:
   🔴 KRITISKT — måste göras nu (kraschar, säkerhet, dataförlust)
   🟡 VIKTIGT — bör göras snart (stabilitet, robusthet)
   🟢 VÄRDESKAPANDE — nästa feature med mest nytta

Format:
## Projektstatus
[1-2 meningar baserat på VERIFIERAD data]

## Rekommenderade nästa steg
1. 🔴 [Kritiskt] — [Konkret åtgärd]
2. 🟡 [Viktigt] — [Konkret åtgärd]
3. 🟢 [Feature] — [Vad det ger]

Inga frågor — ge bästa analys direkt.

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

━━━ DIN SUPERKRAFT: VERIFIERAD FAKTA ━━━
Varje svar du ger är grundat på VERIFIERADE fakta — inte gissningar.
Du får automatiskt:
  • Git-status och senaste commits (körd live)
  • Backlog med alla features och deras status
  • KOD-VERIFIERING: syntax-kontroll, duplikat-check, filstorlek — KÖRD MOT DISK

VIKTIGT: Sektionen "VERIFIERAD KOD-STATUS" nedan är fakta som körts precis nu.
Om verifieringen säger ✅ — tro på det, oavsett vad backlog påstår.
Om backlog säger att ett problem finns men verifieringen säger ✅ — är problemet LÖST.
Säg det explicit: "Enligt verifieringen är detta redan löst."

ANALYSREGLER:
1. Läs VERIFIERAD KOD-STATUS FÖRST — det är sanningen
2. Backlog-påståenden är hypoteser tills verifieringen bekräftar dem
3. Om du ser ⚠️ i verifieringen — det är ett verkligt problem, prioritera det
4. Du KAN INTE bygga kod (det är Snickarens jobb) men DU analyserar, identifierar och ger exakta instruktioner
5. Var direkt och konkret — "rad 2856 har X" är bättre än "det kan finnas ett problem"

PROJEKTMINNE:
{memory}

FASÖVERSIKT:
{phases}

LIVE-KONTEXT (uppdateras automatiskt):
{live_context}"""

# Cache för agentfynd — används av Besiktningsmannen post-build
_review_cache: dict = {}

# ── Loop-guard: förhindrar dubbla anrop och pipeline-loopar ──────────────────
_pipeline_running: dict = {}   # {feature_name: start_timestamp}
_pipeline_attempts: dict = {}  # {feature_name: antal_försök}
import threading as _threading
_pipeline_mutex = _threading.Lock()  # skyddar _pipeline_running/_pipeline_attempts
MAX_PIPELINE_ATTEMPTS = 3      # Max antal gånger samma feature får köra
PIPELINE_TIMEOUT_S = 300       # 5 min timeout per körning

# ─── Domare — aktiveras efter max_iter misslyckanden ─────────────────────────

DOMARE_PROMPT = """Du är Domaren. En feature-granskning misslyckades. Analysera SNABBT varför och bryt ner i minimala deluppgifter.

Returnera ENBART JSON — inga kommentarer, inget annat:
{
  "grundorsak": "En mening",
  "blockerare": [{"problem": "...", "kategori": "A"/"B", "berorda_agenter": ["..."]}],
  "deluppgifter": [
    {"prioritet": 1, "namn": "Kort namn", "spec": "Exakt vad som ska göras", "vem": "Snickaren"/"Användaren", "beroende_av": [], "beraknad_tid": "15min"}
  ],
  "nasta_steg": "Exakt ett konkret nästa steg",
  "projektledare_sammanfattning": "Max 2 meningar på svenska",
  "kan_byggas_nu": false
}"""

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
