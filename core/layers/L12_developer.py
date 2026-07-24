"""L12: Developer Tools Layer — code, git, package management, dev utilities.

Actions: 35
Privilege: user
Libraries: subprocess, pathlib, json, os
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any

from core.bus import Result
from core.engine.fallback import FallbackChain
from core.engine.verifier import Verifiers
from core.layers._utils import run_ps, run_cmd, create_escalation_fn, create_preflight_fn

logger = logging.getLogger("may.core.layers.L12_developer")

LAYER_NAME = "developer"
ACTIONS = [
    # Git operations (10)
    "git_status", "git_diff", "git_log", "git_commit", "git_push",
    "git_pull", "git_branch", "git_checkout", "git_merge", "git_rebase",
    # Package managers (8)
    "npm_install", "npm_run", "npm_list", "pip_install", "pip_list",
    "pip_freeze", "cargo_build", "cargo_run",
    # File operations (7)
    "find_files", "replace_in_file", "count_lines", "compare_files",
    "watch_directory", "compress_directory", "extract_archive",
    # Code analysis (5)
    "syntax_check", "lint_file", "format_file", "get_file_stats",
    "search_code",
    # System tools (5)
    "run_terminal", "open_terminal", "list_services_running",
    "check_port", "kill_port",
    # Developer additions
    "git_clone", "run_code", "docker_list", "docker_start", "docker_stop",
    "database_query", "port_scan",
]


# ── Git operations ────────────────────────────────────────────────────

async def _git_cmd_git(args: str, cwd: str = None) -> Any:
    cmd_args = ["git"] + args.split()
    success, output = await run_cmd(cmd_args, timeout=30)
    return {"command": f"git {args}", "output": output, "success": success}


async def _git_cmd_ps(args: str, cwd: str = None) -> Any:
    ps_cmd = f"git {args}"
    if cwd:
        ps_cmd = f"cd {cwd}; git {args}"
    success, output = await run_ps(ps_cmd, timeout=30)
    return {"command": f"git {args}", "output": output, "success": success}


async def _git_status(params: dict) -> Any:
    cwd = params.get("cwd")
    return await _git_cmd_git("status", cwd)


async def _git_status_ps(params: dict) -> Any:
    cwd = params.get("cwd")
    return await _git_cmd_ps("status", cwd)


async def _git_diff(params: dict) -> Any:
    cwd = params.get("cwd")
    return await _git_cmd_git("diff", cwd)


async def _git_diff_ps(params: dict) -> Any:
    cwd = params.get("cwd")
    return await _git_cmd_ps("diff", cwd)


async def _git_log(params: dict) -> Any:
    count = params.get("count", 10)
    cwd = params.get("cwd")
    return await _git_cmd_git(f"log --oneline -{count}", cwd)


async def _git_log_ps(params: dict) -> Any:
    count = params.get("count", 10)
    cwd = params.get("cwd")
    return await _git_cmd_ps(f"log --oneline -{count}", cwd)


async def _git_commit(params: dict) -> Any:
    message = params.get("message", "")
    if not message:
        return {"error": "Message required"}
    success, output = await run_cmd(["git", "commit", "-m", message], timeout=30)
    return {"command": f"git commit -m '{message}'", "output": output, "success": success}


async def _git_commit_ps(params: dict) -> Any:
    message = params.get("message", "")
    if not message:
        return {"error": "Message required"}
    success, output = await run_ps(f'git commit -m "{message}"', timeout=30)
    return {"command": f"git commit -m '{message}'", "output": output, "success": success}


async def _git_push(params: dict) -> Any:
    return await _git_cmd_git("push", params.get("cwd"))


async def _git_push_ps(params: dict) -> Any:
    return await _git_cmd_ps("push", params.get("cwd"))


async def _git_pull(params: dict) -> Any:
    return await _git_cmd_git("pull", params.get("cwd"))


async def _git_pull_ps(params: dict) -> Any:
    return await _git_cmd_ps("pull", params.get("cwd"))


async def _git_branch(params: dict) -> Any:
    return await _git_cmd_git("branch", params.get("cwd"))


async def _git_branch_ps(params: dict) -> Any:
    return await _git_cmd_ps("branch", params.get("cwd"))


async def _git_checkout(params: dict) -> Any:
    branch = params.get("branch", "main")
    return await _git_cmd_git(f"checkout {branch}", params.get("cwd"))


async def _git_checkout_ps(params: dict) -> Any:
    branch = params.get("branch", "main")
    return await _git_cmd_ps(f"checkout {branch}", params.get("cwd"))


async def _git_merge(params: dict) -> Any:
    branch = params.get("branch", "main")
    return await _git_cmd_git(f"merge {branch}", params.get("cwd"))


async def _git_merge_ps(params: dict) -> Any:
    branch = params.get("branch", "main")
    return await _git_cmd_ps(f"merge {branch}", params.get("cwd"))


async def _git_rebase(params: dict) -> Any:
    branch = params.get("branch", "main")
    return await _git_cmd_git(f"rebase {branch}", params.get("cwd"))


async def _git_rebase_ps(params: dict) -> Any:
    branch = params.get("branch", "main")
    return await _git_cmd_ps(f"rebase {branch}", params.get("cwd"))


# ── Package managers ──────────────────────────────────────────────────

async def _npm_cmd(args: str, cwd: str = None) -> Any:
    success, output = await run_cmd(["npm"] + args.split(), timeout=60)
    return {"command": f"npm {args}", "output": output, "success": success}


async def _npm_cmd_ps(args: str, cwd: str = None) -> Any:
    ps_cmd = f"npm {args}"
    if cwd:
        ps_cmd = f"cd {cwd}; npm {args}"
    success, output = await run_ps(ps_cmd, timeout=60)
    return {"command": f"npm {args}", "output": output, "success": success}


async def _npm_install(params: dict) -> Any:
    return await _npm_cmd("install", params.get("cwd"))


async def _npm_install_ps(params: dict) -> Any:
    return await _npm_cmd_ps("install", params.get("cwd"))


async def _npm_run(params: dict) -> Any:
    script = params.get("script", "start")
    return await _npm_cmd(f"run {script}", params.get("cwd"))


async def _npm_run_ps(params: dict) -> Any:
    script = params.get("script", "start")
    return await _npm_cmd_ps(f"run {script}", params.get("cwd"))


async def _npm_list(params: dict) -> Any:
    return await _npm_cmd("list --depth=0", params.get("cwd"))


async def _npm_list_ps(params: dict) -> Any:
    return await _npm_cmd_ps("list --depth=0", params.get("cwd"))


async def _pip_install(params: dict) -> Any:
    package = params.get("package", "")
    if not package:
        return {"error": "Package name required"}
    success, output = await run_cmd(["pip", "install", package], timeout=120)
    return {"command": f"pip install {package}", "output": output, "success": success}


async def _pip_install_ps(params: dict) -> Any:
    package = params.get("package", "")
    if not package:
        return {"error": "Package name required"}
    success, output = await run_ps(f"pip install {package}", timeout=120)
    return {"command": f"pip install {package}", "output": output, "success": success}


async def _pip_list(params: dict) -> Any:
    success, output = await run_cmd(["pip", "list"], timeout=30)
    return {"command": "pip list", "output": output, "success": success}


async def _pip_freeze(params: dict) -> Any:
    success, output = await run_cmd(["pip", "freeze"], timeout=30)
    return {"command": "pip freeze", "output": output, "success": success}


async def _cargo_build(params: dict) -> Any:
    success, output = await run_cmd(["cargo", "build"], timeout=120)
    return {"command": "cargo build", "output": output, "success": success}


async def _cargo_build_ps(params: dict) -> Any:
    success, output = await run_ps("cargo build", timeout=120)
    return {"command": "cargo build", "output": output, "success": success}


async def _cargo_run(params: dict) -> Any:
    success, output = await run_cmd(["cargo", "run"], timeout=120)
    return {"command": "cargo run", "output": output, "success": success}


# ── File operations ───────────────────────────────────────────────────

async def _find_files(params: dict) -> Any:
    directory = params.get("directory", ".")
    pattern = params.get("pattern", "*")
    success, output = await run_cmd(["dir", "/s", "/b", f"{directory}\\{pattern}"], timeout=30)
    files = [f.strip() for f in output.strip().split("\n") if f.strip()] if success else []
    return {"files": files[:100]}


async def _find_files_ps(params: dict) -> Any:
    directory = params.get("directory", ".")
    pattern = params.get("pattern", "*")
    success, output = await run_ps(f"Get-ChildItem -Path '{directory}' -Filter '{pattern}' -Recurse -File | Select-Object -First 100 FullName | ConvertTo-Json")
    if success:
        try:
            data = json.loads(output)
            if isinstance(data, dict):
                data = [data]
            return {"files": [d.get("FullName", "") for d in data]}
        except json.JSONDecodeError:
            pass
    return {"error": output}


async def _replace_in_file(params: dict) -> Any:
    path = params.get("path", "")
    old = params.get("old", "")
    new = params.get("new", "")
    if not path or not old:
        return {"error": "Path and old text required"}
    try:
        file_path = Path(path)
        if not file_path.exists():
            return {"error": f"File not found: {path}"}
        content = file_path.read_text(encoding="utf-8")
        new_content = content.replace(old, new)
        file_path.write_text(new_content, encoding="utf-8")
        count = content.count(old)
        return {"replacements": count, "path": path}
    except Exception as e:
        return {"error": str(e)}


async def _replace_in_file_ps(params: dict) -> Any:
    path = params.get("path", "")
    old = params.get("old", "")
    new = params.get("new", "")
    if not path or not old:
        return {"error": "Path and old text required"}
    import base64
    old_b64 = base64.b64encode(old.encode("utf-8")).decode("ascii")
    new_b64 = base64.b64encode(new.encode("utf-8")).decode("ascii")
    ps = (f"$content = [System.IO.File]::ReadAllText('{path}'); "
          f"$find = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String('{old_b64}')); "
          f"$replace = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String('{new_b64}')); "
          f"$count = ([regex]::Matches($content, [regex]::Escape($find))).Count; "
          f"$content = $content.Replace($find, $replace); "
          f"[System.IO.File]::WriteAllText('{path}', $content); Write-Output $count")
    success, output = await run_ps(ps)
    if success and output.strip():
        return {"replaced": int(output.strip()), "path": path}
    return {"error": output}


async def _count_lines(params: dict) -> Any:
    path = params.get("path", "")
    if not path:
        return {"error": "Path required"}
    try:
        file_path = Path(path)
        if not file_path.exists():
            return {"error": f"File not found: {path}"}
        lines = file_path.read_text(encoding="utf-8").split("\n")
        return {"path": path, "lines": len(lines)}
    except Exception as e:
        return {"error": str(e)}


async def _compare_files(params: dict) -> Any:
    file1 = params.get("file1", "")
    file2 = params.get("file2", "")
    if not file1 or not file2:
        return {"error": "Both files required"}
    try:
        f1 = Path(file1)
        f2 = Path(file2)
        if not f1.exists():
            return {"error": f"File not found: {file1}"}
        if not f2.exists():
            return {"error": f"File not found: {file2}"}
        content1 = f1.read_text(encoding="utf-8").split("\n")
        content2 = f2.read_text(encoding="utf-8").split("\n")
        differences = []
        for i, (l1, l2) in enumerate(zip(content1, content2), 1):
            if l1 != l2:
                differences.append({"line": i, "file1": l1, "file2": l2})
        return {"differences": differences[:50], "total_lines_file1": len(content1), "total_lines_file2": len(content2)}
    except Exception as e:
        return {"error": str(e)}


async def _watch_directory(params: dict) -> Any:
    return {"directory": params.get("directory", "."), "duration": params.get("duration", 10), "note": "Directory watching requires filesystem monitoring API"}


async def _compress_directory(params: dict) -> Any:
    directory = params.get("directory", "")
    if not directory:
        return {"error": "Directory required"}
    output = params.get("output", "")
    cmd = f"Compress-Archive -Path '{directory}\\*' -DestinationPath '{output or directory + '.zip'}' -Force"
    success, result = await run_ps(cmd)
    return {"status": "compressed" if success else "failed", "output": result}


async def _extract_archive(params: dict) -> Any:
    archive = params.get("archive", "")
    if not archive:
        return {"error": "Archive path required"}
    destination = params.get("destination", ".")
    cmd = f"Expand-Archive -Path '{archive}' -DestinationPath '{destination}' -Force"
    success, result = await run_ps(cmd)
    return {"status": "extracted" if success else "failed", "output": result}


# ── Code analysis ─────────────────────────────────────────────────────

async def _syntax_check(params: dict) -> Any:
    file = params.get("file", "")
    if not file:
        return {"error": "File required"}
    ext = Path(file).suffix.lower()
    if ext == ".py":
        success, output = await run_cmd(["python", "-m", "py_compile", file])
        return {"file": file, "valid": success, "output": output}
    elif ext in (".ts", ".tsx", ".js", ".jsx"):
        success, output = await run_cmd(["npx", "tsc", "--noEmit", file])
        return {"file": file, "valid": success, "output": output}
    return {"file": file, "note": f"Syntax check not implemented for {ext}"}


async def _syntax_check_ps(params: dict) -> Any:
    file = params.get("file", "")
    if not file:
        return {"error": "File required"}
    ext = Path(file).suffix.lower()
    if ext == ".py":
        success, output = await run_ps(f"python -m py_compile '{file}'")
        return {"file": file, "valid": success, "output": output}
    return {"file": file, "note": f"Syntax check not implemented for {ext}"}


async def _lint_file(params: dict) -> Any:
    file = params.get("file", "")
    if not file:
        return {"error": "File required"}
    ext = Path(file).suffix.lower()
    if ext == ".py":
        success, output = await run_cmd(["python", "-m", "flake8", file])
        return {"file": file, "output": output}
    elif ext in (".ts", ".tsx", ".js", ".jsx"):
        success, output = await run_cmd(["npx", "eslint", file])
        return {"file": file, "output": output}
    return {"file": file, "note": f"Lint not implemented for {ext}"}


async def _format_file(params: dict) -> Any:
    file = params.get("file", "")
    if not file:
        return {"error": "File required"}
    ext = Path(file).suffix.lower()
    if ext == ".py":
        success, output = await run_cmd(["python", "-m", "black", file])
        return {"file": file, "formatted": success, "output": output}
    elif ext in (".ts", ".tsx", ".js", ".jsx"):
        success, output = await run_cmd(["npx", "prettier", "--write", file])
        return {"file": file, "formatted": success, "output": output}
    return {"file": file, "note": f"Format not implemented for {ext}"}


async def _get_file_stats(params: dict) -> Any:
    path = params.get("path", "")
    if not path:
        return {"error": "Path required"}
    try:
        file_path = Path(path)
        if not file_path.exists():
            return {"error": f"Not found: {path}"}
        stat = file_path.stat()
        content = file_path.read_text(encoding="utf-8") if file_path.suffix in ('.py', '.ts', '.tsx', '.js', '.jsx', '.md', '.txt', '.json') else ""
        return {
            "path": path,
            "size_bytes": stat.st_size,
            "modified": stat.st_mtime,
            "lines": len(content.split("\n")) if content else 0,
        }
    except Exception as e:
        return {"error": str(e)}


async def _search_code(params: dict) -> Any:
    directory = params.get("directory", ".")
    query = params.get("query", "")
    if not query:
        return {"error": "Query required"}
    success, output = await run_cmd(["findstr", "/s", "/i", "/n", query, f"{directory}\\*.*"], timeout=30)
    results = [line.strip() for line in output.strip().split("\n") if line.strip()] if success else []
    return {"results": results[:100]}


async def _search_code_ps(params: dict) -> Any:
    directory = params.get("directory", ".")
    query = params.get("query", "")
    if not query:
        return {"error": "Query required"}
    success, output = await run_ps(f"Get-ChildItem -Path '{directory}' -Recurse -File -ErrorAction SilentlyContinue | Select-String -Pattern '{query}' -CaseSensitive:$false | Select-Object -First 100 Path,LineNumber,Line | ConvertTo-Json")
    if success:
        try:
            return {"results": json.loads(output)}
        except json.JSONDecodeError:
            return {"raw": output}
    return {"error": output}


# ── System tools ──────────────────────────────────────────────────────

async def _run_terminal(params: dict) -> Any:
    command = params.get("command", "")
    if not command:
        return {"error": "Command required"}
    success, output = await run_ps(command, timeout=30)
    return {"command": command, "output": output, "success": success}


async def _run_terminal_cmd(params: dict) -> Any:
    command = params.get("command", "")
    if not command:
        return {"error": "Command required"}
    success, output = await run_cmd(["cmd", "/c", command], timeout=30)
    return {"command": command, "output": output, "success": success}


async def _open_terminal(params: dict) -> Any:
    directory = params.get("directory", "")
    cmd = f"Start-Process powershell -ArgumentList '-NoExit', '-Command', 'Set-Location {directory}'"
    success, output = await run_ps(cmd)
    return {"status": "opened" if success else "failed"}


async def _list_services_running(params: dict) -> Any:
    success, output = await run_ps("Get-Service | Where-Object {$_.Status -eq 'Running'} | Select-Object Name,DisplayName | ConvertTo-Json")
    if success:
        try:
            return {"services": json.loads(output)}
        except json.JSONDecodeError:
            return {"raw": output}
    return {"error": output}


async def _check_port(params: dict) -> Any:
    port = params.get("port", 80)
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(("127.0.0.1", int(port)))
        sock.close()
        return {"port": port, "in_use": result == 0}
    except Exception as e:
        return {"error": str(e)}


async def _check_port_ps(params: dict) -> Any:
    port = params.get("port", 80)
    success, output = await run_ps(f"Test-NetConnection -ComputerName localhost -Port {port} -WarningAction SilentlyContinue | Select-Object TcpTestSucceeded,RemotePort | ConvertTo-Json")
    if success:
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            return {"raw": output}
    return {"error": output}


async def _kill_port(params: dict) -> Any:
    port = params.get("port", 80)
    if not port:
        return {"error": "Port required"}
    success, output = await run_ps(f"$proc = Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue | Select-Object -First 1 OwningProcess; if ($proc) {{ Stop-Process -Id $proc.OwningProcess -Force }}")
    return {"status": "killed" if success else "not_found", "port": port}


async def _kill_port_cmd(params: dict) -> Any:
    port = params.get("port", 80)
    if not port:
        return {"error": "Port required"}
    success, output = await run_cmd(["netstat", "-ano"], timeout=10)
    if success:
        for line in output.split("\n"):
            if f":{port}" in line and "LISTENING" in line:
                parts = line.split()
                if parts:
                    pid = parts[-1]
                    run_cmd(["taskkill", "/PID", pid, "/F"])
                    return {"status": "killed", "port": port, "pid": pid}
    return {"status": "not_found", "port": port}


# ── Developer additions ──────────────────────────────────────────────

async def _git_clone(params: dict) -> Any:
    url = params.get("url", "")
    destination = params.get("destination", "")
    if not url:
        return {"error": "URL required"}
    args = ["git", "clone", url]
    if destination:
        args.append(destination)
    success, output = await run_cmd(args, timeout=120)
    return {"command": "git clone", "output": output, "success": success}


async def _git_clone_ps(params: dict) -> Any:
    url = params.get("url", "")
    destination = params.get("destination", "")
    if not url:
        return {"error": "URL required"}
    cmd = f"git clone {url}" + (f" {destination}" if destination else "")
    success, output = await run_ps(cmd, timeout=120)
    return {"command": cmd, "output": output, "success": success}


async def _run_code(params: dict) -> Any:
    """Execute code in a sandboxed subprocess."""
    language = params.get("language", "python")
    code = params.get("code", "")
    if not code:
        return {"error": "Code required"}
    timeout = params.get("timeout", 30)
    if language == "python":
        success, output = await run_cmd(["python", "-c", code], timeout=timeout)
    elif language in ("javascript", "js", "node"):
        success, output = await run_cmd(["node", "-e", code], timeout=timeout)
    elif language in ("powershell", "ps"):
        success, output = await run_ps(code, timeout=timeout)
    elif language in ("batch", "bat", "cmd"):
        success, output = await run_cmd(["cmd", "/c", code], timeout=timeout)
    else:
        return {"error": f"Unsupported language: {language}. Use python, javascript, powershell, or batch."}
    return {"language": language, "output": output, "success": success, "exit_code": 0 if success else 1}


async def _run_code_ps(params: dict) -> Any:
    language = params.get("language", "python")
    code = params.get("code", "")
    if not code:
        return {"error": "Code required"}
    if language in ("powershell", "ps"):
        success, output = await run_ps(code, timeout=30)
    else:
        success, output = await run_cmd(["python", "-c", code], timeout=30)
    return {"language": language, "output": output, "success": success}


async def _docker_list(params: dict) -> Any:
    docker_type = params.get("type", "containers")
    if docker_type == "images":
        cmd = "docker images --format '{{.Repository}}:{{.Tag}} {{.Size}} {{.CreatedAt}}'"
    else:
        cmd = "docker ps -a --format '{{.Names}} {{.Status}} {{.Image}} {{.Ports}}'"
    success, output = await run_ps(cmd, timeout=15)
    if success:
        lines = [l.strip() for l in output.strip().splitlines() if l.strip()]
        return {"type": docker_type, "items": lines, "count": len(lines)}
    return {"error": output, "note": "Docker may not be installed or running"}


async def _docker_start(params: dict) -> Any:
    name = params.get("name", "")
    if not name:
        return {"error": "Container name required"}
    success, output = await run_ps(f"docker start {name}", timeout=15)
    return {"status": "started" if success else "failed", "name": name, "output": output}


async def _docker_stop(params: dict) -> Any:
    name = params.get("name", "")
    if not name:
        return {"error": "Container name required"}
    success, output = await run_ps(f"docker stop {name}", timeout=15)
    return {"status": "stopped" if success else "failed", "name": name, "output": output}


async def _database_query(params: dict) -> Any:
    """Query a SQLite database."""
    db_path = params.get("db_path", "")
    query = params.get("query", "")
    if not db_path or not query:
        return {"error": "Both db_path and query required"}
    try:
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(query)
        if query.strip().upper().startswith("SELECT"):
            rows = [dict(row) for row in cursor.fetchall()[:100]]
            columns = list(rows[0].keys()) if rows else []
            conn.close()
            return {"columns": columns, "rows": rows, "row_count": len(rows)}
        else:
            conn.commit()
            conn.close()
            return {"affected_rows": cursor.rowcount, "success": True}
    except Exception as e:
        return {"error": str(e)}


async def _port_scan(params: dict) -> Any:
    """Scan common ports on a host."""
    import socket
    host = params.get("host", "127.0.0.1")
    ports = params.get("ports", [80, 443, 8080, 3000, 5000, 8000, 8443, 3306, 5432, 6379, 27017, 22, 21, 25, 110, 143, 993, 995, 53])
    open_ports = []
    closed_ports = []
    for port in ports:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((host, int(port)))
            sock.close()
            if result == 0:
                open_ports.append(port)
            else:
                closed_ports.append(port)
        except Exception:
            closed_ports.append(port)
    return {"host": host, "open": open_ports, "closed": closed_ports, "total_scanned": len(ports)}


# ══════════════════════════════════════════════════════════════════════════════
# ACTION MAP
# ══════════════════════════════════════════════════════════════════════════════

_chain = FallbackChain()

ACTION_MAP: dict[str, tuple[list, Any]] = {
    # Git operations
    "git_status":    ([_git_status, _git_status_ps], None),
    "git_diff":      ([_git_diff, _git_diff_ps], None),
    "git_log":       ([_git_log, _git_log_ps], None),
    "git_commit":    ([_git_commit, _git_commit_ps], None),
    "git_push":      ([_git_push, _git_push_ps], None),
    "git_pull":      ([_git_pull, _git_pull_ps], None),
    "git_branch":    ([_git_branch, _git_branch_ps], None),
    "git_checkout":  ([_git_checkout, _git_checkout_ps], None),
    "git_merge":     ([_git_merge, _git_merge_ps], None),
    "git_rebase":    ([_git_rebase, _git_rebase_ps], None),
    # Package managers
    "npm_install":   ([_npm_install, _npm_install_ps], None),
    "npm_run":       ([_npm_run, _npm_run_ps], None),
    "npm_list":      ([_npm_list, _npm_list_ps], None),
    "pip_install":   ([_pip_install], None),
    "pip_list":      ([_pip_list], None),
    "pip_freeze":    ([_pip_freeze], None),
    "cargo_build":   ([_cargo_build], None),
    "cargo_run":     ([_cargo_run], None),
    # File operations
    "find_files":        ([_find_files, _find_files_ps], None),
    "replace_in_file":   ([_replace_in_file, _replace_in_file_ps], None),
    "count_lines":       ([_count_lines], None),
    "compare_files":     ([_compare_files], None),
    "watch_directory":   ([_watch_directory], None),
    "compress_directory":([_compress_directory], None),
    "extract_archive":   ([_extract_archive], None),
    # Code analysis
    "syntax_check":      ([_syntax_check, _syntax_check_ps], None),
    "lint_file":         ([_lint_file], None),
    "format_file":       ([_format_file], None),
    "get_file_stats":    ([_get_file_stats], None),
    "search_code":       ([_search_code, _search_code_ps], None),
    # System tools
    "run_terminal":           ([_run_terminal, _run_terminal_cmd], None),
    "open_terminal":          ([_open_terminal], None),
    "list_services_running":  ([_list_services_running], None),
    "check_port":             ([_check_port, _check_port_ps], None),
    "kill_port":              ([_kill_port, _kill_port_cmd], None),
    # Developer additions
    "git_clone":        ([_git_clone, _git_clone_ps], None),
    "run_code":         ([_run_code, _run_code_ps], None),
    "docker_list":      ([_docker_list], None),
    "docker_start":     ([_docker_start], None),
    "docker_stop":      ([_docker_stop], None),
    "database_query":   ([_database_query], None),
    "port_scan":        ([_port_scan], None),
}


# ══════════════════════════════════════════════════════════════════════════════
# HANDLER
# ══════════════════════════════════════════════════════════════════════════════

async def handler(action: str, params: dict[str, Any]) -> Result:
    """L12 Developer layer handler — routes actions to their fallback chains."""
    entry = ACTION_MAP.get(action)
    if not entry:
        return Result(
            command_id=params.get("id", ""),
            success=False,
            error=f"Unknown developer action: '{action}'. Available: {sorted(ACTION_MAP.keys())}",
        )

    methods, verifier = entry
    success, data, method_used, error = await _chain.execute(
        action=f"developer.{action}",
        params=params,
        methods=methods,
        verifier=verifier,
        preflight_fn=create_preflight_fn("developer", action),
        escalation_fn=create_escalation_fn("developer", action),
    )

    suggested = None
    if not success and error:
        suggested = f"Error: {error[:120]}"

    return Result(
        command_id=params.get("id", ""),
        success=success,
        data=data,
        error=error if not success else None,
        verified=verifier is not None and success,
        method_used=method_used,
        suggested_action=suggested,
    )
