"""
git_utils.py — Git-operationer: clone, pull, commit, push.
Importeras av app.py.
"""
from pathlib import Path
import subprocess, json

def git(rd: Path, *args) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(rd),
                          capture_output=True, text=True, timeout=60)


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
