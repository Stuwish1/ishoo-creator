#!/usr/bin/env python3
"""Git setup for Ishoo Creator - pushar till GitHub."""
import json, subprocess, sys, urllib.request
from pathlib import Path

base = Path(__file__).parent
print("=" * 50)
print("  Ishoo Creator v6 - GitHub Setup")
print("=" * 50)

# 1. Las token fran settings.json
try:
    s = json.loads((base / "settings.json").read_text(encoding="utf-8"))
    token = s.get("github_token", "")
except Exception as e:
    print(f"FEL: Kunde inte lasa settings.json: {e}")
    input("Tryck Enter for att stanga...")
    sys.exit(1)

if not token:
    print("FEL: GitHub-token saknas!")
    print("Gaa till http://localhost:8000 > Installningar och lagg till token.")
    input("Tryck Enter for att stanga...")
    sys.exit(1)

print(f"OK: Token hittad ({len(token)} tecken)")

# 2. Skapa GitHub-repo
print("\nSkapar GitHub-repo: Stuwish1/ishoo-creator...")
data = json.dumps({
    "name": "ishoo-creator",
    "description": "Ishoo Creator v6 - AI-driven app builder",
    "private": False,
    "auto_init": False
}).encode()
req = urllib.request.Request("https://api.github.com/user/repos", data=data, method="POST")
req.add_header("Authorization", f"token {token}")
req.add_header("Content-Type", "application/json")
req.add_header("Accept", "application/vnd.github.v3+json")
try:
    with urllib.request.urlopen(req) as r:
        resp = json.loads(r.read())
    print(f"OK: Repo skapat: {resp.get('html_url','')}")
except urllib.error.HTTPError as e:
    body = e.read().decode()
    if "already exists" in body or "name already exists" in body:
        print("OK: Repo finns redan, fortsatter...")
    else:
        print(f"FEL: {body[:200]}")
        input("Tryck Enter for att stanga...")
        sys.exit(1)

# 3. Git init
print("\nInitierar git...")
def git(*args):
    r = subprocess.run(["git", "-C", str(base)] + list(args),
                       capture_output=True, text=True)
    if r.stdout.strip(): print(r.stdout.strip())
    if r.stderr.strip(): print(r.stderr.strip())
    return r.returncode

if not (base / ".git").exists():
    git("init")
    git("branch", "-M", "main")
    print("OK: Git initierat")
else:
    print("OK: .git finns redan")

git("config", "user.name", "Stiven Ishoo")
git("config", "user.email", "stiven@2snickare.se")

# 4. Satt remote med token
remote_url = f"https://{token}@github.com/Stuwish1/ishoo-creator.git"
git("remote", "remove", "origin")
git("remote", "add", "origin", remote_url)
print("OK: Remote satt")

# 5. Commit
print("\nLagger till filer...")
git("add", "-A")
r = subprocess.run(["git", "-C", str(base), "status", "--short"],
                   capture_output=True, text=True)
print(r.stdout[:500] if r.stdout.strip() else "Inga andrade filer")

print("\nSkapar commit...")
git("commit", "-m",
    "feat: Ishoo Creator v6 - Spec-driven Edition\n\n"
    "- 10 parallella granskaragenter\n"
    "- Spec-granskare fore byggstart\n"
    "- Build-verify loop (npm build + auto-fix)\n"
    "- Ollama-stod for lokal AI (RTX 3080)\n"
    "- Systemstatus-panel")

# 6. Push
print("\nPushar till GitHub...")
rc = git("push", "-u", "origin", "main")
if rc != 0:
    print("\nForsok med force push (om repot har annat innehall)...")
    rc2 = git("push", "-u", "--force", "origin", "main")
    if rc2 != 0:
        print("FEL: Push misslyckades")
        input("Tryck Enter for att stanga...")
        sys.exit(1)

print("\n" + "=" * 50)
print("  KLART!")
print("  https://github.com/Stuwish1/ishoo-creator")
print("=" * 50)
input("\nTryck Enter for att stanga...")
