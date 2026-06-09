"""
Patch: Ersätter apply_and_push med en version som broadcastar 
'syntax_error' WS-event vid Python-syntaxfel.

Importeras av app.py vid startup.
"""
import json
import shutil
import ast
from pathlib import Path
from datetime import datetime

from syntax_guard import validate_file_changes


def create_patched_apply_and_push(
    original_module,
    manager_ref,
    load_settings_fn,
    load_pending_fn,
    effective_repo_dir_fn,
    project_dir_fn,
    git_fn,
):
    """
    Skapar en async version av apply_and_push som broadcastar syntax_error events.
    """

    async def apply_and_push_async(pid: str, feature_name: str, env: str = "dev") -> str:
        """Applicerar ändringar och pushar till dev-branch eller mergar till prod.
        Broadcastar 'syntax_error' WS-event om Python-syntaxfel hittas."""
        s = load_settings_fn()
        pending = load_pending_fn(pid)
        if not pending:
            return "Inga väntande ändringar."
        rd = effective_repo_dir_fn(pid)
        if not rd.exists():
            return "Repo-mappen saknas."

        dev_branch = s.get("dev_branch", "dev")
        prod_branch = s.get("prod_branch", "main")

        # Se till att vi är på dev-branch
        r = git_fn(rd, "checkout", dev_branch)
        if r.returncode != 0:
            r = git_fn(rd, "checkout", "-b", dev_branch)
            if r.returncode != 0:
                return f"Kunde inte checka ut {dev_branch}: {r.stderr[:200]}"

        # ── SYNTAX-GUARD: Validera alla .py-filer INNAN något skrivs ─────────
        files_to_apply = pending.get("files", [])
        syntax_errors = validate_file_changes(files_to_apply)

        if syntax_errors:
            # Broadcast syntax_error event för varje fil med fel
            for err in syntax_errors:
                await manager_ref.broadcast({
                    "type": "syntax_error",
                    "feature": feature_name,
                    "file": err["file"],
                    "line": err.get("line"),
                    "message": err.get("message", "Syntaxfel"),
                    "method": err.get("method", "unknown"),
                    "text": err.get("text", ""),
                })

            # Logga incidenten i memory.md
            try:
                mem_file = project_dir_fn(pid) / "memory.md"
                ts = datetime.now().strftime("%Y-%m-%d %H:%M")
                incident_lines = "\n".join(
                    f"AVVISAT {e['file']}: SyntaxError rad {e.get('line', '?')} - {e.get('message', '?')}"
                    for e in syntax_errors
                )
                incident_entry = (
                    f"\n\n## ⚠️ INCIDENT {ts} — Syntax-guard aktiverades\n"
                    f"{incident_lines}\n"
                    f"Feature: {feature_name}\n"
                )
                existing = mem_file.read_text(encoding="utf-8") if mem_file.exists() else ""
                mem_file.write_text(existing + incident_entry, encoding="utf-8")
            except Exception:
                pass

            error_summary = "; ".join(
                f"{e['file']} rad {e.get('line', '?')}: {e.get('message', 'syntaxfel')}"
                for e in syntax_errors
            )
            return f"SYNTAX-GUARD STOPPADE PUSH:\n{error_summary}"

        # ── Applicera filer — MED extra guards ───────────────────────────────
        _NULL = chr(0)
        skipped = []
        for fc in files_to_apply:
            fpath = rd / fc["path"]
            action = fc.get("action", "create")
            if action == "delete":
                if fpath.exists():
                    fpath.unlink()
            else:
                cw = fc.get("content", "")
                # Null-byte check
                if _NULL in cw:
                    skipped.append(f"AVVISAT {fc['path']}: null bytes i content")
                    continue
                # Storlek-guard — avvisa trunkerade filer
                if str(fpath).endswith('.py') and fpath.exists():
                    orig_size = len(fpath.read_text(encoding="utf-8", errors="ignore"))
                    if orig_size > 5000 and len(cw) < orig_size * 0.3:
                        pct = int(len(cw) / orig_size * 100)
                        skipped.append(
                            f"AVVISAT {fc['path']}: ny version ({len(cw)} bytes) ar bara "
                            f"{pct}% av original ({orig_size} bytes) — troligen trunkerad"
                        )
                        continue
                # Python syntax-check (redan gjort ovan, men behåll som extra säkerhet)
                if str(fpath).endswith('.py') and cw.strip():
                    try:
                        ast.parse(cw)
                    except SyntaxError as se:
                        skipped.append(f"AVVISAT {fc['path']}: SyntaxError rad {se.lineno} - {se.msg}")
                        await manager_ref.broadcast({
                            "type": "syntax_error",
                            "feature": feature_name,
                            "file": fc["path"],
                            "line": se.lineno,
                            "message": se.msg,
                        })
                        continue
                fpath.parent.mkdir(parents=True, exist_ok=True)
                if fpath.name == "app.py" and fpath.exists():
                    shutil.copy2(str(fpath), str(fpath) + ".bak")
                prev_size = len(fpath.read_text(encoding="utf-8", errors="ignore")) if fpath.exists() else 0
                fpath.write_text(cw, encoding="utf-8")
                # Logga stora fil-ändringar i memory
                if prev_size > 5000 and str(fpath).endswith('.py'):
                    new_size = len(cw)
                    change_pct = int((new_size - prev_size) / prev_size * 100)
                    if abs(change_pct) > 10:
                        try:
                            mem_file = project_dir_fn(pid) / "memory.md"
                            ts2 = datetime.now().strftime("%Y-%m-%d %H:%M")
                            note = (
                                f"\n\n## 📝 FILÄNDRING {ts2}\n"
                                f"{fc['path']}: {prev_size} → {new_size} bytes ({change_pct:+d}%)\n"
                                f"Feature: {feature_name}\n"
                            )
                            existing2 = mem_file.read_text(encoding="utf-8") if mem_file.exists() else ""
                            mem_file.write_text(existing2 + note, encoding="utf-8")
                        except Exception:
                            pass

        if skipped:
            # Logga incidenten i memory.md
            try:
                mem_file = project_dir_fn(pid) / "memory.md"
                ts = datetime.now().strftime("%Y-%m-%d %H:%M")
                incident_lines = "\n".join(skipped)
                incident_entry = (
                    f"\n\n## ⚠️ INCIDENT {ts} — Syntax-guard aktiverades\n"
                    f"{incident_lines}\nFeature: {feature_name}\n"
                )
                existing = mem_file.read_text(encoding="utf-8") if mem_file.exists() else ""
                mem_file.write_text(existing + incident_entry, encoding="utf-8")
            except Exception:
                pass

            # Broadcast syntax_error for skipped files too
            for skip_msg in skipped:
                await manager_ref.broadcast({
                    "type": "syntax_error",
                    "feature": feature_name,
                    "file": skip_msg.split(":")[0].replace("AVVISAT ", ""),
                    "line": None,
                    "message": skip_msg,
                })

            return "SYNTAX-GUARD STOPPADE:\n" + "\n".join(skipped)

        # Commit på dev
        git_fn(rd, "add", "-A")
        commit_msg = f"feat: {feature_name}\n\nGenererat av Ishoo Creator [{env}]"
        r = git_fn(rd, "commit", "-m", commit_msg)
        if r.returncode != 0 and "nothing to commit" not in r.stdout:
            return f"git commit misslyckades: {r.stderr[:300]}"

        # Push dev
        r = git_fn(rd, "push", "--set-upstream", "origin", dev_branch)
        if r.returncode != 0:
            return f"git push {dev_branch} misslyckades: {r.stderr[:300]}"

        if env == "prod":
            # Merge dev → prod branch
            r = git_fn(rd, "checkout", prod_branch)
            if r.returncode != 0:
                r = git_fn(rd, "checkout", "-b", prod_branch, f"origin/{prod_branch}")
                if r.returncode != 0:
                    return f"Kunde inte checka ut {prod_branch}: {r.stderr[:200]}"
            r = git_fn(rd, "merge", "--no-ff", dev_branch, "-m", f"Merge: {feature_name} → produktion")
            if r.returncode != 0:
                return f"Merge {dev_branch} → {prod_branch} misslyckades: {r.stderr[:300]}"
            r = git_fn(rd, "push", "origin", prod_branch)
            if r.returncode != 0:
                return f"git push {prod_branch} misslyckades: {r.stderr[:300]}"

        (project_dir_fn(pid) / "pending_changes.json").unlink(missing_ok=True)
        return ""

    return apply_and_push_async
