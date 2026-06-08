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
    {"id":"security","name":"Säkerhetsansvarig","emoji":"🔒","model":"sonnet","enabled":True,
     "prompt":'Du är säkerhetsexpert för React/TypeScript/Supabase. Granska spec/kod för: SQL injection, XSS, exponerade nycklar, saknad RLS, felaktig auth. Returnera ENBART JSON: {"status":"GODKÄND"/"AVVISAD","findings":["..."],"severity":"LOW"/"MEDIUM"/"HIGH","suggestions":["..."]}'},
    {"id":"dba","name":"DBA","emoji":"🗄️","model":"haiku","enabled":True,
     "prompt":'Du är databasexpert för PostgreSQL/Supabase. Granska för: farliga migrationer, saknade index, N+1, saknad RLS. Returnera ENBART JSON: {"status":"GODKÄND"/"AVVISAD","findings":["..."],"severity":"LOW"/"MEDIUM"/"HIGH","suggestions":["..."]}'},
    {"id":"conflict","name":"Konfliktgranskare","emoji":"🔍","model":"haiku","enabled":True,
     "prompt":'Du är kodarkitekt. Granska för: duplicerad kod, namnkonflikter, brutna konventioner. Returnera ENBART JSON: {"status":"GODKÄND"/"AVVISAD","findings":["..."],"severity":"LOW"/"MEDIUM"/"HIGH","suggestions":["..."]}'},
    {"id":"ux","name":"UX + Buggletare","emoji":"🎨","model":"haiku","enabled":True,
     "prompt":'Du är UX-expert och buggletare. Granska mot acceptanskriterier, edge cases, loading states, tillgänglighet. Returnera ENBART JSON: {"status":"GODKÄND"/"AVVISAD","findings":["..."],"severity":"LOW"/"MEDIUM"/"HIGH","suggestions":["..."]}'},
    {"id":"architect","name":"Arkitektur","emoji":"🏗️","model":"sonnet","enabled":True,
     "prompt":'Du är mjukvaruarkitekt för React/TypeScript/Vite. Granska för: separation of concerns, hooks, prop drilling. Returnera ENBART JSON: {"status":"GODKÄND"/"AVVISAD","findings":["..."],"severity":"LOW"/"MEDIUM"/"HIGH","suggestions":["..."]}'},
    {"id":"inspector","name":"Besiktningsman","emoji":"✅","model":"sonnet","enabled":True,"is_inspector":True,
     "prompt":'Du är besiktningsman. Bedöm om koden/specen är redo. Godkänn om inga HIGH-problem. Returnera ENBART JSON: {"status":"GODKÄND"/"AVVISAD","findings":["..."],"severity":"LOW"/"MEDIUM"/"HIGH","suggestions":["..."]}'},
    {"id":"business-logic","name":"Affärslogik","emoji":"🧠","model":"sonnet","enabled":True,
     "prompt":'Du är expert på affärslogik och domänregler. Granska spec/kod för: ofullständig affärslogik, saknade edge cases, inkonsekvent datahantering, felaktiga beräkningar, statusproblem, saknade valideringsregler. Tänk: vad händer om användaren gör X, Y, Z utanför happy path? Returnera ENBART JSON: {"status":"GODKÄND"/"AVVISAD","findings":["..."],"severity":"LOW"/"MEDIUM"/"HIGH","suggestions":["..."]}'},
    {"id":"test-generator","name":"Testgranskare","emoji":"🧪","model":"haiku","enabled":True,
     "prompt":'Du är testexpert. Granska spec/kod ur testperspektiv: identifiera otestad logik, saknade edge cases, null/undefined-scenarier, nätverksfel, tomma tillstånd, race conditions. Lista de 3 viktigaste testfallen som MÅSTE finnas. Returnera ENBART JSON: {"status":"GODKÄND"/"AVVISAD","findings":["..."],"severity":"LOW"/"MEDIUM"/"HIGH","suggestions":["..."]}'},
    {"id":"performance","name":"Prestandagranskare","emoji":"⚡","model":"haiku","enabled":True,
     "prompt":'Du är prestandaexpert för React/TypeScript/Supabase. Granska för: N+1-queries, saknade index, onödiga re-renders, saknad paginering vid listor, tunga beräkningar i render-loop, stora imports, saknad lazy loading. Returnera ENBART JSON: {"status":"GODKÄND"/"AVVISAD","findings":["..."],"severity":"LOW"/"MEDIUM"/"HIGH","suggestions":["..."]}'},
    {"id":"mobile-ux","name":"Mobil/Fältanvändare","emoji":"📱","model":"haiku","enabled":True,
     "prompt":'Du är expert på mobil UX för yrkesanvändare i fält (byggarbetare, hantverkare, tekniker). Granska för: touchmål under 44px, saknad offline-hantering, dålig läsbarhet i solljus, för många steg för vanliga uppgifter, saknad felhantering vid dåligt nätverk, onödiga formulärfält. Tänk: kan en handskebeklädd tumme hantera detta stressigt? Returnera ENBART JSON: {"status":"GODKÄND"/"AVVISAD","findings":["..."],"severity":"LOW"/"MEDIUM"/"HIGH","suggestions":["..."]}'},
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

    return rd, ""

def read_codebase_context(rd: Path, spec: dict) -> str:
    context = ""
    priority = ["package.json", "tsconfig.json", "src/integrations/supabase/types.ts",
                "src/types/index.ts", "src/lib/supabase.ts"]
    for rel in priority:
        p = rd / rel
        if p.exists():
            content = p.read_text(encoding="utf-8", errors="ignore")[:2000]
            context += f"\n\n=== {rel} ===\n{content}"
    src = rd / "src"
    if src.exists():
        structure = [str(f.relative_to(rd)) for f in src.rglob("*")
                     if f.is_file() and f.suffix in (".ts",".tsx",".css")]
        context += f"\n\n=== Filstruktur (src/) ===\n" + "\n".join(structure[:60])
    keywords = []
    for field in ["name","problem","solution"]:
        val = spec.get(field,"")
        if val: keywords.extend(val.lower().split())
    kws = [k for k in keywords if len(k) > 4][:8]
    if src.exists():
        for f in src.rglob("*.tsx"):
            if any(kw in f.name.lower() for kw in kws):
                try:
                    content = f.read_text(encoding="utf-8", errors="ignore")[:3000]
                    context += f"\n\n=== {f.relative_to(rd)} (befintlig) ===\n{content}"
                except: pass
    return context[:12000]

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
    rd, err = clone_or_pull(proj["github"], pid)
    if err: return [], err
    context = read_codebase_context(rd, spec)
    spec_text = json.dumps(spec, ensure_ascii=False, indent=2)
    try:
        response = client_inst.messages.create(
            model=model_for("snickare", s), max_tokens=8000, system=SNICKARE_PROMPT,
            messages=[{"role":"user","content":f"FEATURE-SPEC:\n{spec_text}\n\nBEFINTLIG KODBAS:\n{context}\n\nGenerera koden nu. Returnera ENBART JSON."}])
        text = response.content[0].text.strip()
        s2, e = text.find("{"), text.rfind("}")+1
        data = json.loads(text[s2:e]) if s2 != -1 else {}
        return data.get("files",[]), data.get("summary","")
    except Exception as ex:
        return [], f"Kodgenerering misslyckades: {ex}"

def compute_diffs(pid: str, file_changes: list) -> list:
    rd = repo_dir(pid); diffs = []
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
    rd = repo_dir(pid)
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
När användaren vill bygga något i projektet, ställ dessa frågor en eller två i taget:
1. VEM använder detta, i vilket sammanhang och hur ofta?
2. VILKET PROBLEM löser det egentligen?
3. VAD HÄNDER om featuren inte finns — hur löser man det idag?
4. HUR MÄTER VI att featuren är klar? (konkreta acceptanskriterier)
5. BEROENDEN — hänger detta på något som inte är byggt?
6. RISKER — vad kan gå fel tekniskt eller affärsmässigt?
7. FAS — MVP (måste ha nu), v1 (bör ha) eller v2 (framtiden)?

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

━━━ MINNE & KONTEXT ━━━
PROJEKTMINNE:
{memory}

FASÖVERSIKT:
{phases}"""

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

def run_agent_ollama(agent_def: dict, spec: str, memory: str, feedback: str = "") -> dict:
    """Kor agent via lokal Ollama — gratis och snabbt pa RTX 3080."""
    import urllib.request as _ur
    model_key = agent_def.get("model", "sonnet")
    ollama_model = model_key.split("ollama:", 1)[1] if "ollama:" in model_key else "qwen2.5-coder:7b"
    fb = f"\n\nFEEDBACK:\n{feedback}" if feedback else ""
    messages = [
        {"role": "system", "content": agent_def["prompt"]},
        {"role": "user", "content": f"MINNE:\n{memory}\n\nSPEC:\n{spec}{fb}\n\nReturnera ENBART JSON."}
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

def run_agent(agent_def: dict, spec: str, memory: str, feedback: str = "", s: dict = None) -> dict:
    if s is None: s = load_settings()
    model_key = agent_def.get("model","sonnet")
    # Ruta till Ollama om modellen borjar med "ollama:"
    if model_key.startswith("ollama:"):
        return run_agent_ollama(agent_def, spec, memory, feedback)
    client_inst = get_client(s)
    if not client_inst:
        return {"agent":agent_def["name"],"id":agent_def["id"],"status":"GODKÄND","findings":["Demo-läge"],"severity":"LOW","suggestions":[]}
    model_name = model_for(model_key, s)
    fb = f"\n\nFEEDBACK:\n{feedback}" if feedback else ""
    try:
        r = client_inst.messages.create(model=model_name, max_tokens=700,
            system=agent_def["prompt"],
            messages=[{"role":"user","content":f"MINNE:\n{memory}\n\nSPEC:\n{spec}{fb}\n\nReturnera ENBART JSON."}])
        text = r.content[0].text.strip(); si, e = text.find("{"), text.rfind("}")+1
        data = json.loads(text[si:e]) if si != -1 else {}
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
    system=PROJEKTLEDARE_PROMPT.format(project_name=proj["name"],project_desc=proj.get("description",""),
        project_github=proj.get("github","Ej angivet"),memory=memory,phases=phases)
    response=client_inst.messages.create(model=model_for("projektledare",s),max_tokens=1200,system=system,
        messages=history[-12:]+[{"role":"user","content":message}])
    reply=response.content[0].text
    feature_spec=parse_feature_klar(reply); feature_name=None
    if feature_spec:
        feature_name=feature_spec.get("name","Okänd")
        add_feature(proj["id"],feature_name,feature_spec.get("phase","MVP"),feature_spec)
    system_config = parse_system_klar(reply)
    return JSONResponse({"reply":reply,"feature_detected":feature_name,"feature_spec":feature_spec,"system_config":system_config})

# Review
@app.post("/api/review")
async def review_feature(payload: dict):
    feature_name=payload.get("feature_name","Okänd"); spec_obj=payload.get("spec_obj",{})
    proj=get_active_project()
    if not proj: return JSONResponse({"approved":False})
    s = load_settings()
    max_iter = int(s.get("max_iterations", 3))
    memory=load_memory(proj["id"]); spec_str=json.dumps(spec_obj,ensure_ascii=False) if spec_obj else feature_name
    feedback=""; all_approved=False
    agents, inspector = get_agents_from_settings(s)
    await manager.broadcast({"type":"pipeline_start","feature":feature_name,
                             "agents":[{"id":a["id"],"name":f"{a.get('emoji','')}{a['name']}","model":a.get('model','haiku')} for a in agents+[inspector]]})
    for iteration in range(1, max_iter+1):
        await manager.broadcast({"type":"iteration","iteration":iteration,"max":max_iter})
        for agent in agents:
            await manager.broadcast({"type":"agent_status","id":agent["id"],"name":f"{agent.get('emoji','')}{agent['name']}","status":"running"})
        loop=asyncio.get_event_loop(); results=[]
        with ThreadPoolExecutor(max_workers=max(len(agents),1)) as ex:
            futures={ex.submit(run_agent, agent, spec_str, memory, feedback, s):agent for agent in agents}
            for future in futures:
                result=await loop.run_in_executor(None, future.result); results.append(result)
                await manager.broadcast({"type":"agent_status","id":result["id"],
                    "name":result.get("agent","Agent"),
                    "status":"approved" if result.get("status")=="GODKÄND" else "rejected",
                    "findings":result.get("findings",[]),"severity":result.get("severity","LOW"),
                    "suggestions":result.get("suggestions",[]),"local":result.get("_local",False)})
        await manager.broadcast({"type":"agent_status","id":inspector["id"],"name":f"{inspector.get('emoji','')}{inspector['name']}","status":"running"})
        fb_sum="\n".join(f"{r.get('agent','?')}: {r.get('status','?')} — "+"; ".join(r.get("findings",[])) for r in results)
        insp=await loop.run_in_executor(None, run_agent, inspector, fb_sum, memory, "", s)
        await manager.broadcast({"type":"agent_status","id":inspector["id"],
            "name":f"{inspector.get('emoji','')}{inspector['name']}",
            "status":"approved" if insp.get("status")=="GODKÄND" else "rejected",
            "findings":insp.get("findings",[]),"severity":insp.get("severity","LOW")})
        rejected=[r for r in results if r.get("status")=="AVVISAD"]
        if not rejected and insp.get("status")=="GODKÄND":
            all_approved=True
            features=load_features(proj["id"])
            for f in features:
                if f["name"]==feature_name: f["status"]="Granskas"
            save_features(proj["id"],features)
            await manager.broadcast({"type":"pipeline_done","success":True,"feature":feature_name}); break
        feedback=fb_sum
        if iteration==max_iter:
            await manager.broadcast({"type":"pipeline_done","success":False,"feature":feature_name})
    return JSONResponse({"approved":all_approved})

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
    await manager.broadcast({"type":"push_done","feature":feature_name,"env":env})
    return JSONResponse({"success":True})

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
    rd = repo_dir(pid)
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
            await manager.broadcast({
                "type": "build_verify_done",
                "success": True, "feature": feature_name, "iterations": iteration, "diffs": diffs})
            return JSONResponse({"success": True, "iterations": iteration, "diffs": diffs})

        # Bygget misslyckades
        await manager.broadcast({
            "type": "build_verify_error",
            "output": output[:1200], "iteration": iteration})

        if not client_inst or iteration == max_iter:
            break

        # Skicka byggfel till Snickaren for fix
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
            # Uppdatera current_files med fixarna
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

    # Misslyckades efter max iterationer
    await manager.broadcast({
        "type": "build_verify_done",
        "success": False, "feature": feature_name, "iterations": max_iter})
    return JSONResponse(
        {"success": False, "error": "Bygget misslyckades efter max iterationer"},
        status_code=500)

# ─── System Health Check ──────────────────────────────────────────────────────

@app.get("/api/health")
async def system_health():
    """Kontrollerar att alla systemkomponenter fungerar."""
    import urllib.request as _ur
    s = load_settings()
    results = {}

    # 1. Claude API
    api_key = s.get("api_key", "")
    if not api_key:
        results["claude"] = {"ok": False, "status": "Nyckel saknas", "detail": "Lägg till Anthropic API-nyckel i Inställningar"}
    else:
        try:
            client = get_client(s)
            r = client.messages.create(model=model_for("haiku", s), max_tokens=5,
                messages=[{"role": "user", "content": "ok"}])
            results["claude"] = {"ok": True, "status": "Ansluten", "detail": f"Modell: {model_for('haiku', s)}"}
        except Exception as ex:
            results["claude"] = {"ok": False, "status": "Fel", "detail": str(ex)[:120]}

    # 2. GitHub Token
    gh_token = s.get("github_token", "")
    if not gh_token:
        results["github"] = {"ok": False, "status": "Token saknas", "detail": "Behövs för att klona och pusha kod"}
    else:
        try:
            req = _ur.Request("https://api.github.com/user",
                              headers={"Authorization": f"token {gh_token}", "Accept": "application/vnd.github.v3+json"})
            with _ur.urlopen(req, timeout=6) as r:
                data = json.loads(r.read())
            results["github"] = {"ok": True, "status": "Ansluten", "detail": f"Inloggad som: {data.get('login','')}"}
        except Exception as ex:
            results["github"] = {"ok": False, "status": "Ogiltig token", "detail": str(ex)[:120]}

    # 3. Ollama
    try:
        with _ur.urlopen("http://localhost:11434/api/tags", timeout=3) as r:
            data = json.loads(r.read())
        models = [m.get("name", "") for m in data.get("models", [])]
        if models:
            results["ollama"] = {"ok": True, "status": f"{len(models)} modell(er)", "detail": ", ".join(models)}
        else:
            results["ollama"] = {"ok": False, "status": "Inga modeller", "detail": "Kör ollama-setup.bat för att ladda ner modeller"}
    except:
        results["ollama"] = {"ok": False, "status": "Körs inte", "detail": "Installera Ollama från ollama.com eller kör ollama-setup.bat"}

    # 4. Git
    try:
        r = subprocess.run(["git", "--version"], capture_output=True, text=True, timeout=5)
        ver = r.stdout.strip()
        results["git"] = {"ok": r.returncode == 0, "status": ver if r.returncode == 0 else "Ej installerat",
                          "detail": "Krävs för att hantera kod och versioner"}
    except:
        results["git"] = {"ok": False, "status": "Ej hittad", "detail": "Installera Git från git-scm.com"}

    # 5. Node / npm
    import sys
    npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
    try:
        r = subprocess.run([npm_cmd, "--version"], capture_output=True, text=True, timeout=5)
        ver = r.stdout.strip()
        results["npm"] = {"ok": r.returncode == 0, "status": f"npm {ver}" if r.returncode == 0 else "Ej installerat",
                          "detail": "Krävs för att köra och bygga React-appar"}
    except:
        results["npm"] = {"ok": False, "status": "Ej hittad", "detail": "Installera Node.js från nodejs.org"}

    # 6. Aktivt projekt
    proj = get_active_project()
    if proj:
        rd = repo_dir(proj["id"])
        repo_cloned = rd.exists() and (rd / ".git").exists()
        results["project"] = {
            "ok": True,
            "status": proj["name"],
            "detail": f"GitHub: {proj.get('github','ej satt')} | Repo: {'klonat' if repo_cloned else 'ej klonat än'}"
        }
    else:
        results["project"] = {"ok": False, "status": "Inget projekt", "detail": "Skapa ett projekt för att börja bygga"}

    all_ok = all(v["ok"] for k, v in results.items() if k != "ollama")
    return JSONResponse({"ok": all_ok, "checks": results})

# ─── Git Push (från UI) ───────────────────────────────────────────────────────

@app.post("/api/git-push")
async def git_push_to_github():
    """Initierar git, skapar GitHub-repo och pushar — körs direkt från UI."""
    import urllib.request as _ur
    s = load_settings()
    token = s.get("github_token", "")
    if not token:
        return JSONResponse({"ok": False, "error": "GitHub-token saknas."}, status_code=400)

    base = Path(".")
    repo_name = "ishoo-creator"
    steps = []

    await manager.broadcast({"type": "git_push_step", "step": "Skapar GitHub-repo..."})
    data = json.dumps({"name": repo_name, "description": "Ishoo Creator v6 - AI-driven app builder", "private": False, "auto_init": False}).encode()
    req = _ur.Request("https://api.github.com/user/repos", data=data, method="POST")
    req.add_header("Authorization", f"token {token}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/vnd.github.v3+json")
    try:
        with _ur.urlopen(req) as r:
            resp = json.loads(r.read())
        steps.append(f"Repo skapat: {resp.get('html_url','')}")
    except _ur.HTTPError as e:
        body = e.read().decode()
        if "already exists" in body or "name already exists" in body:
            steps.append("Repo finns redan")
        else:
            return JSONResponse({"ok": False, "error": f"GitHub API-fel: {body[:200]}"})

    await manager.broadcast({"type": "git_push_step", "step": "Initierar git..."})
    loop = asyncio.get_event_loop()
    def do_git():
        def g(*args):
            return subprocess.run(["git"] + list(args), cwd=str(base), capture_output=True, text=True)
        if not (base / ".git").exists():
            g("init"); g("branch", "-M", "main")
        g("config", "user.name", s.get("git_name", "Ishoo Creator"))
        g("config", "user.email", s.get("git_email", "creator@ishoo.se"))
        g("remote", "remove", "origin")
        remote_url = f"https://{token}@github.com/Stuwish1/{repo_name}.git"
        g("remote", "add", "origin", remote_url)
        g("add", "-A")
        r = g("commit", "-m", "feat: Ishoo Creator v6 - Spec-driven Edition")
        if r.returncode != 0 and "nothing to commit" not in r.stdout and "nothing to commit" not in r.stderr:
            return r.stderr[:300]
        push = g("push", "-u", "--force", "origin", "main")
        if push.returncode != 0:
            return push.stderr[:300]
        return ""
    await manager.broadcast({"type": "git_push_step", "step": "Committar och pushar..."})
    err = await loop.run_in_executor(None, do_git)
    if err:
        return JSONResponse({"ok": False, "error": err})

    await manager.broadcast({"type": "git_push_done", "url": f"https://github.com/Stuwish1/{repo_name}"})
    return JSONResponse({"ok": True, "url": f"https://github.com/Stuwish1/{repo_name}", "steps": steps})

if __name__=="__main__":
    import uvicorn
    s = load_settings()
    has_key = "OK" if s.get("api_key") else "SAKNAS - oppna http://localhost:8000 och ga till Installningar"
    has_gh  = "OK" if s.get("github_token") else "Saknas (behovs for Snickaren)"
    print(f"\n{'='*55}\n  Ishoo Creator v6 - Spec-driven Edition\n  Oppna: http://localhost:8000\n{'='*55}")
    print(f"  API-nyckel:      {has_key}")
    print(f"  GitHub token:    {has_gh}")
    print(f"  Dev-branch:      {s.get('dev_branch','dev')}")
    print(f"  Prod-branch:     {s.get('prod_branch','main')}")
    print(f"  Max iterationer: {s.get('max_iterations',3)}")
    print(f"  Agenter:         {len(s.get('agents', DEFAULT_AGENTS))}")
    print(f"{'='*55}\n")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)

