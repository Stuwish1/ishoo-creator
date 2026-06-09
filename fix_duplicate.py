#!/usr/bin/env python3
"""
Engångs-skript: tar bort den FÖRSTA (enklare) definitionen av git_push_direct
Behåller definitionen på rad ~2856 (med payload-parameter).

Kör: python fix_duplicate.py
Verifiera: grep -c 'def git_push_direct' app.py  -> ska returnera 1
"""
import re, sys, ast
from pathlib import Path

APP = Path("app.py")

if not APP.exists():
    print("FEL: app.py hittades inte i aktuell mapp.")
    sys.exit(1)

src = APP.read_text(encoding="utf-8")

# Räkna förekomster
count = src.count("async def git_push_direct")
print(f"Hittade {count} definition(er) av 'async def git_push_direct'")

if count == 0:
    print("Inga definitioner hittades — inget att fixa.")
    sys.exit(0)

if count == 1:
    print("✅ Redan fixat — exakt 1 definition finns.")
    # Validera syntax
    try:
        ast.parse(src)
        print("✅ Syntax OK")
    except SyntaxError as e:
        print(f"❌ Syntaxfel: {e}")
        sys.exit(1)
    sys.exit(0)

# Hitta båda positionerna
positions = []
start = 0
while True:
    idx = src.find("async def git_push_direct", start)
    if idx == -1:
        break
    positions.append(idx)
    start = idx + 1

print(f"Position för definition 1: rad {src[:positions[0]].count(chr(10)) + 1}")
print(f"Position för definition 2: rad {src[:positions[1]].count(chr(10)) + 1}")

# Hitta @app.post-dekoratören för den FÖRSTA definitionen
# Gå bakåt från positions[0] för att hitta @app.post
block_start = src.rfind("@app.post", 0, positions[0])
if block_start == -1:
    print("FEL: Kunde inte hitta @app.post för första definitionen")
    sys.exit(1)

print(f"Blockstart (med @app.post): rad {src[:block_start].count(chr(10)) + 1}")

# Hitta slutet av första funktionen
# Sök efter nästa @app. eller nästa async def på toppnivå
# Vi vet att position[1] innehåller den andra definitionen
# Hitta @app.post för andra definitionen och använd som block_end
block_end = src.rfind("@app.post", positions[0], positions[1])
if block_end == -1:
    # Inga decorator mellan — använd positions[1] direkt
    block_end = positions[1]
    # Gå bakåt för att få med ev. blankrader
    while block_end > 0 and src[block_end-1] in ' \t\n':
        nl = src.rfind('\n', 0, block_end)
        prev_nl = src.rfind('\n', 0, nl) if nl > 0 else -1
        line = src[prev_nl+1:nl].strip()
        if line == '':
            block_end = prev_nl + 1 if prev_nl >= 0 else 0
        else:
            break
else:
    # block_end pekar på @app.post för den andra definitionen
    pass

print(f"Blockslut (exklusivt): rad {src[:block_end].count(chr(10)) + 1}")

# Verifiera att block_endär före positions[1]
assert block_end <= positions[1], "Blockslut är efter andra definitionens start — logikfel"

# Ta bort första blocket
new_src = src[:block_start] + src[block_end:]

# Verifiera att bara 1 definition kvar
new_count = new_src.count("async def git_push_direct")
if new_count != 1:
    print(f"FEL: After removal got {new_count} definitions. Aborting.")
    sys.exit(1)

# Validera syntax
try:
    ast.parse(new_src)
    print("✅ Syntax OK efter borttagning")
except SyntaxError as e:
    print(f"❌ Syntaxfel efter borttagning: {e}")
    print("Ingen fil skrevs — originalet behålls.")
    sys.exit(1)

# Skriv backup
backup = Path("app.py.bak")
backup.write_text(src, encoding="utf-8")
print(f"💾 Backup sparad till {backup}")

# Skriv fixad fil
APP.write_text(new_src, encoding="utf-8")
final_count = new_src.count("async def git_push_direct")
print(f"✅ Klar! app.py uppdaterad. Definitioner kvar: {final_count}")
print(f"Ny filstorlek: {len(new_src)} tecken ({len(new_src.splitlines())} rader)")
print()
print("Kör för att verifiera:")
print('  python -c "import ast; ast.parse(open(\'app.py\').read()); print(\'OK\')\") ')
