#!/usr/bin/env python3
"""Claude Code statusline: model | directory | git branch | changes | context | MCP servers"""
import json
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone

LOG_PATH = os.path.expanduser("~/.claude/statusline.log")
LOG_MAX_SIZE = 1024 * 1024  # 1MB


class Logger:
    """Structlog-style structured logger."""

    def __init__(self, path: str, max_size: int = LOG_MAX_SIZE):
        self._path = path
        self._max_size = max_size

    def _rotate_if_needed(self):
        try:
            if os.path.exists(self._path) and os.path.getsize(self._path) > self._max_size:
                backup = f"{self._path}.1"
                if os.path.exists(backup):
                    os.remove(backup)
                os.rename(self._path, backup)
        except Exception:
            pass

    def _write(self, level: str, event: str, **kwargs):
        try:
            self._rotate_if_needed()
            entry = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "level": level,
                "event": event,
                **kwargs,
            }
            with open(self._path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass

    def debug(self, event: str, **kwargs):
        self._write("DEBUG", event, **kwargs)

    def info(self, event: str, **kwargs):
        self._write("INFO", event, **kwargs)

    def warning(self, event: str, **kwargs):
        self._write("WARNING", event, **kwargs)

    def error(self, event: str, **kwargs):
        self._write("ERROR", event, exc_info=traceback.format_exc(), **kwargs)


log = Logger(LOG_PATH)


# Terminal color palette (Molokai)
# Foreground: "#rrggbb"
# Background: ("#fg", "#bg")
MOLOKAI = {
    "black": "#121212",
    "red": "#fa2573",
    "green": "#98e123",
    "yellow": "#dfd460",
    "blue": "#1080d0",
    "magenta": "#8700ff",
    "cyan": "#43a8d0",
    "white": "#bbbbbb",
    "brightBlack": "#555555",
    "brightRed": "#f6669d",
    "brightGreen": "#b1e05f",
    "brightYellow": "#fff26d",
    "brightBlue": "#00afff",
    "brightMagenta": "#af87ff",
    "brightCyan": "#51ceff",
    "brightWhite": "#ffffff",
    "bgBlack": ("#ffffff", "#121212"),
    "bgRed": ("#ffffff", "#fa2573"),
    "bgGreen": ("#000000", "#98e123"),
    "bgYellow": ("#000000", "#dfd460"),
    "bgBlue": ("#ffffff", "#1080d0"),
    "bgMagenta": ("#ffffff", "#8700ff"),
    "bgCyan": ("#ffffff", "#43a8d0"),
    "bgWhite": ("#000000", "#bbbbbb"),
    "bgBrightBlack": ("#ffffff", "#555555"),
    "bgBrightRed": ("#ffffff", "#f6669d"),
    "bgBrightGreen": ("#000000", "#b1e05f"),
    "bgBrightYellow": ("#000000", "#fff26d"),
    "bgBrightBlue": ("#ffffff", "#00afff"),
    "bgBrightMagenta": ("#ffffff", "#af87ff"),
    "bgBrightCyan": ("#ffffff", "#51ceff"),
    "bgBrightWhite": ("#000000", "#ffffff"),
}

# Element styling: element -> condition -> (fg_color, bg_color)
STYLES = {
    "model": ("white", None),
    "directory": ("white", None),
    "branch": ("white", None),
    "branch_detached": ("bgYellow", None),
    "changes_clean": ("white", None),
    "changes_dirty": ("yellow", None),
    "context": ("white", None),
    "mcp_title": ("white", None),
    "mcp_connected": ("green", None),
    "mcp_disconnected": ("red", None),
}


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    """Convert '#rrggbb' to (r, g, b)."""
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def style(text: str, fg_color: str | None, bg_color: str | None = None) -> str:
    """Apply foreground and/or background color to text."""
    if not fg_color and not bg_color:
        return text
    prefix = ""
    color = MOLOKAI.get(fg_color) if fg_color else None
    if color and isinstance(color, tuple):
        # bgX color: ("#fg", "#bg")
        fg_r, fg_g, fg_b = hex_to_rgb(color[0])
        bg_r, bg_g, bg_b = hex_to_rgb(color[1])
        prefix = f"\033[38;2;{fg_r};{fg_g};{fg_b}m\033[48;2;{bg_r};{bg_g};{bg_b}m"
    elif color:
        r, g, b = hex_to_rgb(color)
        prefix = f"\033[38;2;{r};{g};{b}m"
        if bg_color:
            bg_hex = MOLOKAI.get(bg_color)
            if bg_hex and isinstance(bg_hex, str):
                r, g, b = hex_to_rgb(bg_hex)
                prefix += f"\033[48;2;{r};{g};{b}m"
    return f"{prefix}{text}\033[0m"

CACHE_DIR = os.path.join(
    os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")),
    "claude-statusline",
)
CACHE_TTL = 3
MCP_CACHE_TTL = 10


def get_cache_path(session_id: str) -> str:
    safe_id = session_id.replace("/", "_") if session_id else "default"
    return os.path.join(CACHE_DIR, f"{safe_id}.cache")


def get_cached(session_id: str) -> str | None:
    try:
        path = get_cache_path(session_id)
        age = time.time() - os.path.getmtime(path)
        if age > CACHE_TTL:
            log.debug("cache_expired", session_id=session_id, age=age, ttl=CACHE_TTL)
            return None
        with open(path) as f:
            cached = f.read()
        log.debug("cache_hit", session_id=session_id, age=age)
        return cached
    except FileNotFoundError:
        log.debug("cache_miss", session_id=session_id)
        return None
    except Exception:
        log.error("cache_read_failed", session_id=session_id)
        return None


def set_cache(session_id: str, output: str):
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        path = get_cache_path(session_id)
        tmp = f"{path}.tmp.{os.getpid()}"
        with open(tmp, "w") as f:
            f.write(output)
        os.rename(tmp, path)
        log.debug("cache_set", session_id=session_id, path=path)
    except Exception:
        log.error("cache_set_failed", session_id=session_id)


MCP_CACHE_PATH = os.path.join(CACHE_DIR, "mcp.cache")
MCP_LOCAL_PATH = os.path.expanduser("~/.claude/mcp.local.json")


def get_local_mcp_servers() -> list[str]:
    """Read server names from mcp.local.json."""
    try:
        with open(MCP_LOCAL_PATH) as f:
            data = json.load(f)
        servers = data.get("mcpServers", data)
        if isinstance(servers, dict):
            names = list(servers.keys())
            log.debug("mcp_local_loaded", path=MCP_LOCAL_PATH, servers=names)
            return names
        log.warning("mcp_local_invalid_format", path=MCP_LOCAL_PATH)
    except FileNotFoundError:
        log.debug("mcp_local_not_found", path=MCP_LOCAL_PATH)
    except json.JSONDecodeError as e:
        log.error("mcp_local_parse_error", path=MCP_LOCAL_PATH, error=str(e))
    except Exception:
        log.error("mcp_local_read_failed", path=MCP_LOCAL_PATH)
    return []


def get_mcp_servers() -> str | None:
    """Read MCP servers from local config and cached global list."""
    local_servers = get_local_mcp_servers()
    conn_r, conn_g, conn_b = hex_to_rgb(MOLOKAI[STYLES["mcp_connected"][0]])
    local_styled = [
        f"\033[38;2;{conn_r};{conn_g};{conn_b}m{name}\033[0m"
        for name in local_servers
    ]
    try:
        mtime = os.path.getmtime(MCP_CACHE_PATH)
        age = time.time() - mtime
        with open(MCP_CACHE_PATH) as f:
            cached = f.read().strip()
        log.debug("mcp_cache_read", age=age, has_cached=bool(cached))
    except FileNotFoundError:
        log.debug("mcp_cache_not_found", path=MCP_CACHE_PATH)
        age = MCP_CACHE_TTL + 1
        cached = ""
    except Exception:
        log.error("mcp_cache_read_failed", path=MCP_CACHE_PATH)
        age = MCP_CACHE_TTL + 1
        cached = ""
    if age >= MCP_CACHE_TTL:
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            tmp = f"{MCP_CACHE_PATH}.tmp.{os.getpid()}"
            disc_r, disc_g, disc_b = hex_to_rgb(MOLOKAI[STYLES["mcp_disconnected"][0]])
            cmd = f"timeout 10 claude mcp list 2>/dev/null | awk -F: 'NF>1 {{if (/Connected/) print \"\\033[38;2;{conn_r};{conn_g};{conn_b}m\" $1 \"\\033[0m\"; else print \"\\033[38;2;{disc_r};{disc_g};{disc_b}m!\" $1 \"\\033[0m\"}}' | paste -sd, | sed 's/,/, /g' > {tmp} && mv {tmp} {MCP_CACHE_PATH}"
            subprocess.Popen(
                cmd,
                shell=True,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            log.debug("mcp_cache_refresh_spawned", age=age, ttl=MCP_CACHE_TTL)
        except Exception:
            log.error("mcp_cache_refresh_failed")
    all_servers = local_styled.copy()
    if cached:
        all_servers.append(cached)
    if not all_servers:
        log.debug("mcp_no_servers")
        return None
    log.debug("mcp_servers_result", local_count=len(local_servers), has_cached=bool(cached))
    fg_c, bg_c = STYLES["mcp_title"]
    title = style("MCP:", fg_c, bg_c)
    return f"{title} {', '.join(all_servers)}"


def is_dippy_configured() -> bool:
    """Check if Dippy hook is correctly configured with an executable file."""
    try:
        settings_path = os.path.expanduser("~/.claude/settings.json")
        with open(settings_path) as f:
            settings = json.load(f)
        hooks = settings.get("hooks", {}).get("PreToolUse", [])
        for hook in hooks:
            if "Bash" in hook.get("matcher", ""):
                for h in hook.get("hooks", []):
                    cmd = h.get("command", "")
                    path = os.path.expanduser(cmd.split()[0]) if cmd else ""
                    if path and os.path.isfile(path) and os.access(path, os.X_OK):
                        log.debug("dippy_configured", path=path)
                        return True
        log.debug("dippy_not_configured")
    except FileNotFoundError:
        log.debug("dippy_settings_not_found", path=settings_path)
    except Exception:
        log.error("dippy_check_failed")
    return False


def get_context_from_transcript(transcript_path: str) -> int | None:
    """Read transcript JSONL and get actual context length from most recent message."""
    if not transcript_path:
        log.debug("transcript_no_path")
        return None
    try:
        with open(transcript_path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            chunk_size = min(size, 64 * 1024)
            f.seek(max(0, size - chunk_size))
            lines = f.read().decode("utf-8", errors="ignore").strip().split("\n")
        for line in reversed(lines):
            try:
                entry = json.loads(line)
                usage = entry.get("message", {}).get("usage")
                if usage:
                    total = (
                        usage.get("input_tokens", 0)
                        + usage.get("output_tokens", 0)
                        + usage.get("cache_read_input_tokens", 0)
                        + usage.get("cache_creation_input_tokens", 0)
                    )
                    log.debug("transcript_tokens_found", tokens=total, path=transcript_path)
                    return total
            except json.JSONDecodeError:
                continue
        log.debug("transcript_no_usage", path=transcript_path, lines_checked=len(lines))
    except FileNotFoundError:
        log.debug("transcript_not_found", path=transcript_path)
    except Exception:
        log.error("transcript_read_failed", path=transcript_path)
    return None


def get_context_remaining(data: dict) -> str | None:
    try:
        ctx = data.get("context_window", {})
        size = ctx.get("context_window_size", 0)
        if not size:
            log.debug("context_no_window_size")
            return None
        used = get_context_from_transcript(data.get("transcript_path", ""))
        if used is None:
            log.debug("context_no_usage_data", size=size)
            fg_c, bg_c = STYLES["context"]
            return style("ctx: 80% left", fg_c, bg_c)
        used_pct = used * 100 // size
        until_compact = max(0, 80 - used_pct)
        log.debug("context_calculated", size=size, used=used, used_pct=used_pct, remaining_pct=until_compact)
        fg_c, bg_c = STYLES["context"]
        return style(f"ctx: {until_compact}% left", fg_c, bg_c)
    except Exception:
        log.error("context_remaining_failed")
        return None


def get_git_changes(cwd: str) -> str | None:
    if not cwd:
        log.debug("git_changes_no_cwd")
        return None
    try:
        result = subprocess.run(
            ["git", "-C", cwd, "diff", "--shortstat", "HEAD"],
            capture_output=True,
            text=True,
            timeout=1,
        )
        if result.returncode != 0:
            log.debug("git_changes_not_repo", cwd=cwd, returncode=result.returncode)
            return None
        stat = result.stdout.strip()
        if not stat:
            log.debug("git_changes_clean", cwd=cwd)
            fg_c, bg_c = STYLES["changes_clean"]
            return style("clean", fg_c, bg_c)
        added = removed = 0
        for part in stat.split(","):
            part = part.strip()
            if "insertion" in part:
                added = int(part.split()[0])
            elif "deletion" in part:
                removed = int(part.split()[0])
        log.debug("git_changes_dirty", cwd=cwd, added=added, removed=removed)
        fg_c, bg_c = STYLES["changes_dirty"]
        return style(f"Δ +{added},-{removed}", fg_c, bg_c)
    except subprocess.TimeoutExpired:
        log.warning("git_changes_timeout", cwd=cwd)
    except Exception:
        log.error("git_changes_failed", cwd=cwd)
    return None


def get_git_branch(cwd: str) -> str | None:
    if not cwd:
        log.debug("git_branch_no_cwd")
        return None
    try:
        result = subprocess.run(
            ["git", "-C", cwd, "branch", "--show-current"],
            capture_output=True,
            text=True,
            timeout=1,
        )
        if result.returncode == 0:
            branch = result.stdout.strip()
            if branch:
                log.debug("git_branch_found", cwd=cwd, branch=branch)
                fg_c, bg_c = STYLES["branch"]
                return style(f"⎇ {branch}", fg_c, bg_c)
            log.debug("git_branch_detached", cwd=cwd)
            fg_c, bg_c = STYLES["branch_detached"]
            return style("⎇ [detached head]", fg_c, bg_c)
        log.debug("git_branch_not_repo", cwd=cwd, returncode=result.returncode)
    except subprocess.TimeoutExpired:
        log.warning("git_branch_timeout", cwd=cwd)
    except Exception:
        log.error("git_branch_failed", cwd=cwd)
    return None


def build_statusline(data: dict) -> str:
    model = "?"
    cwd = ""
    try:
        model = data.get("model", {}).get("display_name") or "?"
    except Exception:
        log.error("build_statusline_model_failed")
    try:
        cwd = data.get("workspace", {}).get("current_dir") or ""
    except Exception:
        log.error("build_statusline_cwd_failed")
    log.debug("build_statusline_start", model=model, cwd=cwd)
    fg_c, bg_c = STYLES["model"]
    model = style(model, fg_c, bg_c)
    if is_dippy_configured():
        model = f"🐤 {model}"
    display_cwd = os.path.basename(cwd) if cwd else ""
    if display_cwd:
        fg_c, bg_c = STYLES["directory"]
        display_cwd = style(display_cwd, fg_c, bg_c)
    parts = [model, display_cwd] if display_cwd else [model]
    branch = get_git_branch(cwd)
    if branch:
        parts.append(branch)
    changes = get_git_changes(cwd)
    if changes:
        parts.append(changes)
    ctx_remaining = get_context_remaining(data)
    if ctx_remaining:
        parts.append(ctx_remaining)
    mcp = get_mcp_servers()
    if mcp:
        parts.append(mcp)
    log.debug("build_statusline_done", parts_count=len(parts))
    return " | ".join(parts)


def main():
    log.info("main_start")
    try:
        data = json.load(sys.stdin)
        log.debug("main_input_parsed", session_id=data.get("session_id", ""))
    except Exception:
        log.warning("main_input_parse_failed")
        data = {}
    session_id = data.get("session_id", "")
    cached = get_cached(session_id)
    if cached:
        log.info("main_served_cached", session_id=session_id)
        print(cached)
        return
    output = build_statusline(data)
    set_cache(session_id, output)
    log.info("main_built_fresh", session_id=session_id)
    print(output)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log.error("main_fatal")
        print("?")
