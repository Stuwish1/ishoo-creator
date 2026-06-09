"""
Syntax Guard — validerar Python-filer innan commit.
Använder py_compile.compile() + ast.parse() för dubbel säkerhet.
"""
import ast
import os
import re
import tempfile
import py_compile


def validate_python_syntax(content: str, filepath: str) -> dict | None:
    """
    Validerar Python-syntax med ast.parse() och py_compile.compile().
    Returnerar None om OK, annars dict med felinformation.
    """
    if not filepath.endswith('.py') or not content.strip():
        return None

    # Steg 1: ast.parse — snabb, ingen tempfil
    try:
        ast.parse(content)
    except SyntaxError as se:
        return {
            "file": filepath,
            "line": se.lineno,
            "message": se.msg,
            "method": "ast.parse",
            "offset": se.offset,
            "text": (se.text or "").strip()[:120],
        }

    # Steg 2: py_compile — fångar edge cases (encoding, BOM, etc)
    tmp_fd = None
    tmp_path = None
    try:
        tmp_fd, tmp_path = tempfile.mkstemp(suffix='.py', prefix='syntaxguard_')
        os.write(tmp_fd, content.encode('utf-8'))
        os.close(tmp_fd)
        tmp_fd = None
        py_compile.compile(tmp_path, doraise=True)
    except py_compile.PyCompileError as pce:
        err_msg = str(pce)
        line_no = None
        line_match = re.search(r'line (\d+)', err_msg)
        if line_match:
            line_no = int(line_match.group(1))
        return {
            "file": filepath,
            "line": line_no,
            "message": err_msg[:200],
            "method": "py_compile",
            "offset": None,
            "text": "",
        }
    except Exception:
        pass
    finally:
        if tmp_fd is not None:
            try:
                os.close(tmp_fd)
            except OSError:
                pass
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    return None


def validate_file_changes(file_changes: list) -> list[dict]:
    """
    Validerar alla .py-filer i file_changes.
    Returnerar lista med felinformation för filer med syntaxfel.
    Tom lista = allt OK.
    """
    errors = []
    for fc in file_changes:
        filepath = fc.get("path", "")
        action = fc.get("action", "create")
        content = fc.get("content", "")

        if action == "delete":
            continue

        error = validate_python_syntax(content, filepath)
        if error:
            errors.append(error)

    return errors
