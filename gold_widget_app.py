import ctypes
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
from ctypes import wintypes
from tkinter import messagebox
import urllib.error
import urllib.request
import webbrowser
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from websocket import create_connection

try:
    import winreg
except ImportError:  # pragma: no cover - non-Windows fallback
    winreg = None


SOURCE_DIR = Path(__file__).resolve().parent
RUNTIME_DIR = (
    Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False)
    else SOURCE_DIR
)
APP_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "JDGoldWidget"
POSITION_PATH = APP_DIR / "widget_position.json"
CHROME_PROFILE_DIR = APP_DIR / "jd-gold-chrome-profile"
SECONDARY_CHROME_PROFILE_DIR = APP_DIR / "jd-gold-chrome-session"
STARTUP_SCRIPT_PATH = (
    Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    / "Microsoft"
    / "Windows"
    / "Start Menu"
    / "Programs"
    / "Startup"
    / "JD Gold Widget AutoStart.vbs"
)
SITE_URL = "https://gold-price-pro.pf.jd.com/"
WINDOW_TITLE = "JD Gold Widget"
SINGLE_INSTANCE_MUTEX = "Local\\JDGoldWidget_SingleInstance"
WINDOW_PROP_NAME = "JDGoldWidget.IsWidget"
DEVTOOLS_TIMEOUT_SECONDS = 15
WEBSOCKET_RECV_TIMEOUT_SECONDS = 8
RESUME_GAP_SECONDS = 5.0
POLL_INTERVAL_MS = 200
ZORDER_CHECK_MS = 250
HWND_TOPMOST = -1
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
GW_HWNDPREV = 3
GA_ROOT = 2
GWL_EXSTYLE = -20
WS_EX_TOPMOST = 0x00000008
WS_EX_LAYERED = 0x00080000
LWA_ALPHA = 0x00000002
ERROR_ALREADY_EXISTS = 183
TRANSPARENT_COLOR = "#010203"
_SINGLE_INSTANCE_MUTEX_HANDLE = None
TEXT_COLOR = "#2F3A46"
SEPARATOR_COLOR = "#556270"
WINDOW_PADDING_X = 16
WINDOW_PADDING_Y = 10
# Win32 layered alpha (1/255): receives mouse; nearly invisible over the chroma-keyed text window.
HIT_OVERLAY_ALPHA_BYTE = 1
MAX_OVERLAY_WIDTH = 900
MAX_OVERLAY_HEIGHT = 240
# Park any leaked browser window far off-screen (some GPUs ignore headless).
CHROME_OFFSCREEN_POSITION = "-32000,-32000"
DEFAULT_Y = 42
BROWSER_ENV_VARS = ("JD_GOLD_BROWSER", "CHROME_PATH", "GOOGLE_CHROME_BIN")
SKIP_AUTO_STARTUP_ENV = "JD_GOLD_SKIP_AUTO_STARTUP"
WINDOWS_BROWSER_CANDIDATES = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Chromium\Application\chrome.exe",
    r"C:\Program Files (x86)\Chromium\Application\chrome.exe",
    r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
    r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
)
WINDOWS_USER_BROWSER_CANDIDATES = (
    r"Google\Chrome\Application\chrome.exe",
    r"Microsoft\Edge\Application\msedge.exe",
    r"Chromium\Application\chrome.exe",
    r"BraveSoftware\Brave-Browser\Application\brave.exe",
)
BROWSER_REGISTRY_APP_PATHS = (
    "chrome.exe",
    "msedge.exe",
    "brave.exe",
)
PATH_BROWSER_NAMES = (
    "chrome.exe",
    "msedge.exe",
    "brave.exe",
    "chromium.exe",
    "chrome",
    "msedge",
    "brave",
    "chromium",
)


def _user32():
    return ctypes.windll.user32


def _kernel32():
    return ctypes.windll.kernel32


def _tk_hwnd(widget: tk.Misc) -> int:
    """Return the real top-level HWND (TkTopLevel), not the child from winfo_id()."""
    hwnd = int(widget.winfo_id())
    if sys.platform != "win32":
        return hwnd
    top = int(_user32().GetAncestor(hwnd, GA_ROOT) or 0)
    return top or hwnd


def _ensure_ex_topmost(hwnd: int) -> None:
    style = int(_user32().GetWindowLongW(hwnd, GWL_EXSTYLE))
    if style & WS_EX_TOPMOST:
        return
    _user32().SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_TOPMOST)


def _set_hwnd_layered_alpha(hwnd: int, alpha_byte: int) -> bool:
    """Apply per-pixel alpha via Win32. More reliable than Tk -alpha on some GPUs."""
    if sys.platform != "win32" or not hwnd:
        return False
    try:
        user32 = _user32()
        style = int(user32.GetWindowLongW(hwnd, GWL_EXSTYLE))
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED)
        return bool(
            user32.SetLayeredWindowAttributes(
                hwnd,
                0,
                max(1, min(int(alpha_byte), 255)),
                LWA_ALPHA,
            )
        )
    except Exception:
        return False


def _measure_toplevel_size(widget: tk.Misc) -> tuple[int, int]:
    """Return a sane overlay size; winfo_width/height can be wrong before first map."""
    widget.update_idletasks()
    width = int(widget.winfo_width())
    height = int(widget.winfo_height())
    if width <= 1 or height <= 1:
        width = int(widget.winfo_reqwidth())
        height = int(widget.winfo_reqheight())
    screen_w = max(int(widget.winfo_screenwidth()), 1)
    screen_h = max(int(widget.winfo_screenheight()), 1)
    if width > screen_w // 2 or height > screen_h // 2:
        width = min(int(widget.winfo_reqwidth()), MAX_OVERLAY_WIDTH)
        height = min(int(widget.winfo_reqheight()), MAX_OVERLAY_HEIGHT)
    width = max(1, min(width, MAX_OVERLAY_WIDTH))
    height = max(1, min(height, MAX_OVERLAY_HEIGHT))
    return width, height


def _park_process_windows_offscreen(pid: int) -> None:
    """Move visible top-level windows for a process off-screen (headless leak workaround)."""
    if sys.platform != "win32" or pid <= 0:
        return

    user32 = _user32()
    flags = SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def _enum(hwnd, _lparam):
        window_pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
        if int(window_pid.value) != pid:
            return True
        if not user32.IsWindowVisible(hwnd):
            return True
        user32.SetWindowPos(hwnd, 0, -32000, -32000, 0, 0, flags)
        return True

    user32.EnumWindows(_enum, 0)


def _taskbar_hwnds() -> list[int]:
    user32 = _user32()
    found: list[int] = []
    primary = int(user32.FindWindowW("Shell_TrayWnd", None) or 0)
    if primary:
        found.append(primary)
    secondary = int(user32.FindWindowW("Shell_SecondaryTrayWnd", None) or 0)
    if secondary:
        found.append(secondary)
    return found


def _hwnd_is_behind_taskbar(hwnd: int) -> bool:
    """True when any taskbar top-level window is above hwnd in EnumWindows z-order."""
    return _top_covering_taskbar(hwnd) is not None


def _top_covering_taskbar(hwnd: int) -> int | None:
    """Return the highest taskbar HWND currently above hwnd, if any."""
    trays = {tray for tray in _taskbar_hwnds() if tray}
    if not trays:
        return None

    found: list[int] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def _enum(enum_hwnd, _lparam):
        current = int(enum_hwnd)
        if current == hwnd:
            return False
        if current in trays:
            found.append(current)
            return False
        return True

    _user32().EnumWindows(_enum, 0)
    return found[0] if found else None


def _set_hwnd_topmost(hwnd: int, *, force_restack: bool = False) -> None:
    """Keep hwnd TOPMOST. force_restack re-inserts it above the taskbar when demoted."""
    user32 = _user32()
    _ensure_ex_topmost(hwnd)
    flags = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
    if force_restack:
        # HWND_TOPMOST alone does not reclaim order after the taskbar jumps ahead
        # inside the TOPMOST band. Insert immediately above the covering taskbar.
        tray = _top_covering_taskbar(hwnd)
        if tray:
            prev = int(user32.GetWindow(tray, GW_HWNDPREV) or 0)
            insert_after = prev if prev and prev != hwnd else HWND_TOPMOST
            user32.SetWindowPos(hwnd, insert_after, 0, 0, 0, 0, flags)
    user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, flags)


def _activate_existing_gui() -> None:
    matches: list[int] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def _enum(hwnd, _lparam):
        if _user32().GetPropW(hwnd, WINDOW_PROP_NAME):
            matches.append(int(hwnd))
            return False
        return True

    _user32().EnumWindows(_enum, 0)
    hwnd = matches[0] if matches else int(_user32().FindWindowW(None, WINDOW_TITLE) or 0)
    if not hwnd:
        return
    _set_hwnd_topmost(hwnd)
    _user32().ShowWindow(hwnd, 5)  # SW_SHOW


def ensure_single_gui_instance() -> bool:
    """Keep only one GUI process. Return False if another instance already owns the lock."""
    global _SINGLE_INSTANCE_MUTEX_HANDLE

    if sys.platform != "win32":
        return True

    _kernel32().SetLastError(0)
    handle = _kernel32().CreateMutexW(None, False, SINGLE_INSTANCE_MUTEX)
    if not handle:
        return True

    if _kernel32().GetLastError() == ERROR_ALREADY_EXISTS:
        _kernel32().CloseHandle(handle)
        _activate_existing_gui()
        return False

    _SINGLE_INSTANCE_MUTEX_HANDLE = handle
    return True


@dataclass
class PageSnapshot:
    london_gold_text: str
    london_gold_cny_text: str
    update_time_text: str
    seq: int


def _iter_existing_paths(paths: Iterable[Path]) -> Iterable[Path]:
    seen: set[str] = set()
    for path in paths:
        try:
            normalized = os.path.normcase(str(path.resolve()))
        except OSError:
            normalized = os.path.normcase(str(path))
        if normalized in seen:
            continue
        seen.add(normalized)
        if path.exists():
            yield path


def _iter_browser_candidates() -> Iterable[Path]:
    for env_name in BROWSER_ENV_VARS:
        raw_path = os.environ.get(env_name)
        if raw_path:
            yield Path(raw_path).expanduser()

    for raw_path in WINDOWS_BROWSER_CANDIDATES:
        yield Path(raw_path)

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        for relative_path in WINDOWS_USER_BROWSER_CANDIDATES:
            yield Path(local_app_data) / relative_path

    if winreg is not None:
        registry_roots = (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE)
        for app_name in BROWSER_REGISTRY_APP_PATHS:
            subkey = rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{app_name}"
            for root in registry_roots:
                try:
                    with winreg.OpenKey(root, subkey) as key:
                        value, _ = winreg.QueryValueEx(key, None)
                    if value:
                        yield Path(value)
                except OSError:
                    continue

    for binary_name in PATH_BROWSER_NAMES:
        resolved = shutil.which(binary_name)
        if resolved:
            yield Path(resolved)


def find_chrome_binary() -> Path:
    for candidate in _iter_existing_paths(_iter_browser_candidates()):
        return candidate

    raise FileNotFoundError(
        "No supported Chromium browser was found. Install Chrome, Edge, Chromium, or Brave, "
        "or set JD_GOLD_BROWSER to the browser executable path."
    )


def load_position(screen_width: int) -> tuple[int, int]:
    default_x = max(screen_width - 330, 0)
    default_y = DEFAULT_Y

    if not POSITION_PATH.exists():
        return default_x, default_y

    try:
        payload = json.loads(POSITION_PATH.read_text(encoding="utf-8"))
        return int(payload.get("x", default_x)), int(payload.get("y", default_y))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return default_x, default_y


def save_position(x: int, y: int) -> None:
    try:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        POSITION_PATH.write_text(
            json.dumps({"x": x, "y": y}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass


def pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def cleanup_stale_chrome_profiles(active_dir: Path | None = None) -> None:
    for path in APP_DIR.glob("jd-gold-chrome-*"):
        if path == CHROME_PROFILE_DIR:
            continue
        if path.is_dir() and path != active_dir:
            shutil.rmtree(path, ignore_errors=True)
    if (
        SECONDARY_CHROME_PROFILE_DIR.is_dir()
        and SECONDARY_CHROME_PROFILE_DIR != active_dir
    ):
        shutil.rmtree(SECONDARY_CHROME_PROFILE_DIR, ignore_errors=True)


def _subprocess_no_window_kwargs() -> dict[str, int]:
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return {"creationflags": creationflags} if creationflags else {}


def _terminate_process_tree(pid: int) -> None:
    try:
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            text=True,
            timeout=10,
            **_subprocess_no_window_kwargs(),
        )
    except (OSError, subprocess.SubprocessError):
        pass


def _iter_browser_processes() -> Iterable[tuple[int, str]]:
    script = (
        "$names = @('chrome.exe','msedge.exe','brave.exe','chromium.exe');"
        "Get-CimInstance Win32_Process |"
        "Where-Object { $names -contains $_.Name -and $_.CommandLine } |"
        "Select-Object ProcessId, CommandLine |"
        "ConvertTo-Json -Compress"
    )
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            timeout=15,
            **_subprocess_no_window_kwargs(),
        )
    except (OSError, subprocess.SubprocessError):
        return

    payload = (completed.stdout or "").strip()
    if not payload or completed.returncode != 0:
        return

    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return

    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        return

    for item in data:
        try:
            pid = int(item.get("ProcessId"))
            command_line = str(item.get("CommandLine") or "")
        except (TypeError, ValueError, AttributeError):
            continue
        if command_line:
            yield pid, command_line


def terminate_stale_profile_browsers(
    profile_dirs: Iterable[Path] | None = None,
) -> None:
    targets = [
        os.path.normcase(str(path.resolve()))
        for path in (
            profile_dirs
            if profile_dirs is not None
            else (CHROME_PROFILE_DIR, SECONDARY_CHROME_PROFILE_DIR)
        )
    ]
    if not targets:
        return

    pids: list[int] = []
    for pid, command_line in _iter_browser_processes():
        normalized = os.path.normcase(command_line)
        if any(target in normalized for target in targets):
            pids.append(pid)

    for pid in sorted(set(pids)):
        _terminate_process_tree(pid)


def ensure_chrome_profile_dir() -> Path:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    CHROME_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    return CHROME_PROFILE_DIR


def prepare_profile_dir(profile_dir: Path, reset: bool = False) -> Path:
    if reset and profile_dir.exists():
        terminate_stale_profile_browsers((profile_dir,))
        shutil.rmtree(profile_dir, ignore_errors=True)
    profile_dir.mkdir(parents=True, exist_ok=True)
    return profile_dir


def _escape_vbs_string(value: str) -> str:
    return value.replace('"', '""')


def build_launch_command() -> str:
    if getattr(sys, "frozen", False):
        return subprocess.list2cmdline([str(Path(sys.executable).resolve())])

    executable = Path(sys.executable).resolve()
    if executable.name.lower() == "python.exe":
        pythonw_executable = executable.with_name("pythonw.exe")
        if pythonw_executable.exists():
            executable = pythonw_executable

    return subprocess.list2cmdline([str(executable), str(Path(__file__).resolve())])


def build_startup_script() -> str:
    launch_command = build_launch_command()
    return "\n".join(
        [
            'Set shell = CreateObject("WScript.Shell")',
            f'shell.CurrentDirectory = "{_escape_vbs_string(str(RUNTIME_DIR))}"',
            f'shell.Run "{_escape_vbs_string(launch_command)}", 0',
        ]
    )


def is_startup_enabled() -> bool:
    try:
        return (
            STARTUP_SCRIPT_PATH.exists()
            and STARTUP_SCRIPT_PATH.read_text(encoding="utf-8") == build_startup_script()
        )
    except OSError:
        return False


def ensure_startup_enabled() -> None:
    try:
        STARTUP_SCRIPT_PATH.parent.mkdir(parents=True, exist_ok=True)
        script = build_startup_script()
        if (
            not STARTUP_SCRIPT_PATH.exists()
            or STARTUP_SCRIPT_PATH.read_text(encoding="utf-8") != script
        ):
            STARTUP_SCRIPT_PATH.write_text(script, encoding="utf-8")
    except OSError:
        pass


def disable_startup() -> None:
    try:
        if STARTUP_SCRIPT_PATH.exists():
            STARTUP_SCRIPT_PATH.unlink()
    except OSError:
        pass


class ChromeDomSource:
    def __init__(self) -> None:
        self.chrome_process: subprocess.Popen[str] | None = None
        self.ws = None
        self.ws_id = 0
        self.last_seq = -1
        self.lock = threading.Lock()
        self.remote_debugging_port = pick_free_port()
        self.devtools_http = f"http://127.0.0.1:{self.remote_debugging_port}"
        self.profile_dir = ensure_chrome_profile_dir()
        self.cleanup_profile_dir_on_close = False
        cleanup_stale_chrome_profiles(self.profile_dir)

    def start(self) -> None:
        with self.lock:
            if self.ws is not None:
                return

            last_error = None
            terminate_stale_profile_browsers()
            attempt_plans = (
                (
                    (CHROME_PROFILE_DIR, False),
                    (SECONDARY_CHROME_PROFILE_DIR, True),
                ),
                (
                    (CHROME_PROFILE_DIR, True),
                    (SECONDARY_CHROME_PROFILE_DIR, True),
                ),
            )
            for profile_options in attempt_plans:
                for profile_dir, reset_profile in profile_options:
                    self.profile_dir = prepare_profile_dir(
                        profile_dir,
                        reset=reset_profile,
                    )
                    self.cleanup_profile_dir_on_close = profile_dir == SECONDARY_CHROME_PROFILE_DIR
                    for headless_args in (
                        ["--headless=new"],
                        ["--headless", "--disable-gpu"],
                        ["--headless=old", "--disable-gpu"],
                    ):
                        try:
                            self._spawn_chrome(headless_args)
                            self._connect()
                            self._wait_for_page_ready()
                            self._install_observer()
                            return
                        except Exception as exc:
                            last_error = exc
                            self._cleanup_locked()
                terminate_stale_profile_browsers()

            raise RuntimeError(
                f"Failed to start a compatible headless browser session: {last_error}"
            )

    def reset(self) -> None:
        with self.lock:
            self._cleanup_locked()
            self._prepare_new_session_locked()
            self.last_seq = -1

    def close(self) -> None:
        with self.lock:
            self._cleanup_locked()

    def _cleanup_locked(self) -> None:
        if self.ws is not None:
            try:
                self.ws.close()
            except Exception:
                pass
            self.ws = None

        if self.chrome_process is not None:
            pid = self.chrome_process.pid
            try:
                self.chrome_process.terminate()
                self.chrome_process.wait(timeout=3)
            except Exception:
                _terminate_process_tree(pid)
                try:
                    self.chrome_process.kill()
                except Exception:
                    pass
            else:
                if self.chrome_process.poll() is None:
                    _terminate_process_tree(pid)
            self.chrome_process = None

        if self.cleanup_profile_dir_on_close:
            shutil.rmtree(self.profile_dir, ignore_errors=True)
            self.cleanup_profile_dir_on_close = False

    def _prepare_new_session_locked(self) -> None:
        self.profile_dir = ensure_chrome_profile_dir()
        self.cleanup_profile_dir_on_close = False
        self.remote_debugging_port = pick_free_port()
        self.devtools_http = f"http://127.0.0.1:{self.remote_debugging_port}"

    def read_snapshot(self) -> PageSnapshot | None:
        self.start()

        with self.lock:
            payload = self._evaluate(
                """
                (() => {
                  const state = window.__jdGoldObserver;
                  if (!state) {
                    return null;
                  }
                  return JSON.stringify({
                    seq: state.seq,
                    london: state.data.london,
                    cny: state.data.cny,
                    updateTime: state.data.updateTime
                  });
                })()
                """,
                return_by_value=True,
            )

        if not payload:
            return None

        data = json.loads(payload)
        return PageSnapshot(
            london_gold_text=str(data.get("london", "")).strip(),
            london_gold_cny_text=str(data.get("cny", "")).strip(),
            update_time_text=str(data.get("updateTime", "")).strip(),
            seq=int(data.get("seq", 0)),
        )

    def read_once(self) -> PageSnapshot | None:
        for attempt in range(2):
            deadline = time.time() + DEVTOOLS_TIMEOUT_SECONDS
            while time.time() < deadline:
                snapshot = self.read_snapshot()
                if snapshot and snapshot.update_time_text:
                    return snapshot
                time.sleep(0.2)
            if attempt == 0:
                self.reset()
        return None

    def _spawn_chrome(self, headless_args: list[str]) -> None:
        chrome_binary = find_chrome_binary()
        prepare_profile_dir(self.profile_dir)
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        args = [
            str(chrome_binary),
            *headless_args,
            f"--remote-debugging-port={self.remote_debugging_port}",
            "--remote-allow-origins=*",
            f"--user-data-dir={self.profile_dir}",
            "--disable-extensions",
            "--disable-sync",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-networking",
            "--disable-default-apps",
            "--window-size=1280,720",
            f"--window-position={CHROME_OFFSCREEN_POSITION}",
            SITE_URL,
        ]
        self.chrome_process = subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
        if self.chrome_process is not None:
            time.sleep(0.25)
            _park_process_windows_offscreen(self.chrome_process.pid)

    def _connect(self) -> None:
        page_socket = self._wait_for_page_socket()
        self.ws = create_connection(page_socket, timeout=10)
        self.ws.settimeout(WEBSOCKET_RECV_TIMEOUT_SECONDS)

    def _wait_for_page_socket(self) -> str:
        deadline = time.time() + DEVTOOLS_TIMEOUT_SECONDS
        last_error = None

        while time.time() < deadline:
            if self.chrome_process is not None:
                exit_code = self.chrome_process.poll()
                if exit_code is not None:
                    raise RuntimeError(
                        f"Browser exited early with code {exit_code} "
                        f"(profile may be locked or incompatible): {self.profile_dir}"
                    )
            try:
                with urllib.request.urlopen(f"{self.devtools_http}/json/list", timeout=2) as response:
                    pages = json.loads(response.read().decode("utf-8"))
                for page in pages:
                    if page.get("type") == "page" and SITE_URL in page.get("url", ""):
                        socket_url = page.get("webSocketDebuggerUrl")
                        if socket_url:
                            return socket_url
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc
            if self.chrome_process is not None:
                _park_process_windows_offscreen(self.chrome_process.pid)
            time.sleep(0.25)

        raise RuntimeError(f"Failed to connect to hidden Chrome page: {last_error}")

    def _wait_for_page_ready(self) -> None:
        deadline = time.time() + DEVTOOLS_TIMEOUT_SECONDS
        while time.time() < deadline:
            ready = self._evaluate(
                "!!document.querySelector('.main-price-row .main-price-item .main-value')",
                return_by_value=True,
            )
            if ready is True:
                return
            time.sleep(0.2)
        raise RuntimeError("Gold page DOM did not become ready in time")

    def _install_observer(self) -> None:
        self._evaluate(
            """
            (() => {
              const pick = () => {
                const values = Array.from(
                  document.querySelectorAll('.main-price-row .main-price-item .main-value')
                ).map(el => (el.innerText || '').trim());
                const updateTimeRaw = document.querySelector('.update-time')?.innerText || '';
                return {
                  london: values[0] || '',
                  cny: values[1] || '',
                  updateTime: updateTimeRaw.replace('最后更新时间', '').trim()
                };
              };

              if (!window.__jdGoldObserver) {
                const state = {
                  seq: 0,
                  data: pick()
                };
                const refresh = () => {
                  const next = pick();
                  const changed =
                    next.london !== state.data.london ||
                    next.cny !== state.data.cny ||
                    next.updateTime !== state.data.updateTime;
                  if (changed) {
                    state.data = next;
                    state.seq += 1;
                  }
                };
                const observer = new MutationObserver(refresh);
                observer.observe(document.body, {
                  subtree: true,
                  childList: true,
                  characterData: true
                });
                state.observer = observer;
                state.refresh = refresh;
                window.__jdGoldObserver = state;
              }

              window.__jdGoldObserver.refresh();
              return true;
            })()
            """,
            return_by_value=True,
        )

    def _evaluate(self, expression: str, return_by_value: bool) -> object:
        if self.ws is None:
            raise RuntimeError("DevTools websocket is not connected")

        self.ws_id += 1
        self.ws.send(
            json.dumps(
                {
                    "id": self.ws_id,
                    "method": "Runtime.evaluate",
                    "params": {
                        "expression": expression,
                        "returnByValue": return_by_value,
                    },
                }
            )
        )

        while True:
            response = json.loads(self.ws.recv())
            if response.get("id") != self.ws_id:
                continue
            if "exceptionDetails" in response.get("result", {}):
                raise RuntimeError("JavaScript evaluation failed inside hidden Chrome")
            return response["result"]["result"].get("value")


class GoldWidgetApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.is_refreshing = False
        self.monitor = ChromeDomSource()
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.save_position_job: str | None = None
        self.last_seq = -1
        self.last_poll_at: float | None = None

        self.london_var = tk.StringVar(value="----.--")
        self.cny_var = tk.StringVar(value="----.--")
        self._hwnd: int | None = None
        self._overlay_hwnd: int | None = None
        self.hit_overlay: tk.Toplevel | None = None
        self._overlay_usable = True
        self._content_container: tk.Widget | None = None
        self._zorder_job: str | None = None

        self._build_window()
        self._build_layout()
        self._build_hit_overlay()
        self._configure_context_menu()

        self.root.after(250, self.refresh_async)
        self.root.after(POLL_INTERVAL_MS, self._schedule_refresh)

    def _build_window(self) -> None:
        self.root.title(WINDOW_TITLE)
        self.root.overrideredirect(True)
        self.root.configure(bg=TRANSPARENT_COLOR)
        self.root.attributes("-topmost", True)

        try:
            self.root.wm_attributes("-transparentcolor", TRANSPARENT_COLOR)
        except tk.TclError:
            pass

        try:
            self.root.wm_attributes("-toolwindow", True)
        except tk.TclError:
            pass

        # transparentcolor can reshuffle styles; re-assert topmost afterwards.
        self.root.attributes("-topmost", True)

        screen_width = self.root.winfo_screenwidth()
        x, y = load_position(screen_width)
        self.root.geometry(f"+{x}+{y}")

        self.root.bind("<Escape>", lambda _event: self.shutdown())
        self.root.bind("<Configure>", self._on_root_configure)
        self.root.after(0, self._install_zorder_guard)

    def _raise_widget_stack(self, *, force_restack: bool = False) -> None:
        """Raise text window, then hit overlay. Order matters for click targeting."""
        if sys.platform != "win32":
            return
        try:
            if self.root.winfo_exists():
                self._hwnd = _tk_hwnd(self.root)
            if self.hit_overlay is not None and self.hit_overlay.winfo_exists():
                self._overlay_hwnd = _tk_hwnd(self.hit_overlay)
            if self._hwnd:
                _set_hwnd_topmost(self._hwnd, force_restack=force_restack)
            if self._overlay_hwnd:
                if force_restack and self._hwnd:
                    # Park overlay immediately above the text window.
                    flags = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
                    prev = int(_user32().GetWindow(self._hwnd, GW_HWNDPREV) or 0)
                    insert_after = (
                        prev
                        if prev and prev != self._overlay_hwnd
                        else HWND_TOPMOST
                    )
                    _ensure_ex_topmost(self._overlay_hwnd)
                    _user32().SetWindowPos(
                        self._overlay_hwnd,
                        insert_after,
                        0,
                        0,
                        0,
                        0,
                        flags,
                    )
                _set_hwnd_topmost(self._overlay_hwnd, force_restack=False)
        except tk.TclError:
            pass

    def _needs_zorder_fix(self) -> bool:
        if sys.platform != "win32" or not self._hwnd:
            return False
        if _hwnd_is_behind_taskbar(self._hwnd):
            return True
        if self._overlay_hwnd and _hwnd_is_behind_taskbar(self._overlay_hwnd):
            return True
        return False

    def _repair_zorder_if_needed(self) -> None:
        # Only restack when we are actually under the taskbar.
        if not self._needs_zorder_fix():
            return
        self._raise_widget_stack(force_restack=True)

    def _install_zorder_guard(self) -> None:
        try:
            self.root.attributes("-topmost", True)
        except tk.TclError:
            return

        if sys.platform != "win32":
            return

        try:
            self._hwnd = _tk_hwnd(self.root)
            _user32().SetPropW(self._hwnd, WINDOW_PROP_NAME, 1)
            self._raise_widget_stack()
            self._schedule_zorder_check()
            self.root.after(0, self._sync_hit_overlay)
        except Exception:
            self._hwnd = None

    def _schedule_zorder_check(self) -> None:
        self._repair_zorder_if_needed()
        try:
            self._zorder_job = self.root.after(ZORDER_CHECK_MS, self._schedule_zorder_check)
        except tk.TclError:
            self._zorder_job = None

    def _remove_zorder_guard(self) -> None:
        if self._zorder_job is not None:
            try:
                self.root.after_cancel(self._zorder_job)
            except tk.TclError:
                pass
            self._zorder_job = None

        if sys.platform == "win32" and self._hwnd:
            try:
                _user32().RemovePropW(self._hwnd, WINDOW_PROP_NAME)
            except Exception:
                pass
        self._hwnd = None
        self._overlay_hwnd = None

    def _bind_interactions(self, widget: tk.Widget) -> None:
        widget.bind("<ButtonPress-1>", self._start_drag)
        widget.bind("<B1-Motion>", self._drag_window)
        widget.bind("<ButtonRelease-1>", self._finish_drag)
        widget.bind("<Double-Button-1>", self._open_site)
        widget.bind("<Button-3>", self._show_context_menu)
        widget.bind("<Escape>", lambda _event: self.shutdown())

    def _build_hit_overlay(self) -> None:
        # Color-keyed transparent pixels are click-through on Windows, so a near-invisible
        # layered overlay sits above the text window and owns all mouse interactions.
        # Avoid Tk -alpha here: on some GPUs/drivers it renders as a huge opaque panel.
        overlay = tk.Toplevel(self.root)
        overlay.withdraw()
        overlay.overrideredirect(True)
        overlay.configure(bg="#000000", cursor="hand2")
        overlay.attributes("-topmost", True)
        try:
            overlay.wm_attributes("-toolwindow", True)
        except tk.TclError:
            pass
        overlay.attributes("-topmost", True)
        self._bind_interactions(overlay)
        self.hit_overlay = overlay
        self.root.after_idle(self._sync_hit_overlay)

    def _bind_content_interactions(self) -> None:
        container = self._content_container
        if container is None:
            return
        self._bind_interactions(container)
        for child in container.winfo_children():
            self._bind_interactions(child)
            for grandchild in child.winfo_children():
                self._bind_interactions(grandchild)

    def _apply_overlay_transparency(self) -> bool:
        if sys.platform != "win32" or not self._overlay_hwnd:
            return False
        return _set_hwnd_layered_alpha(self._overlay_hwnd, HIT_OVERLAY_ALPHA_BYTE)

    def _on_root_configure(self, _event: tk.Event | None = None) -> None:
        self._sync_hit_overlay()

    def _sync_hit_overlay(self) -> None:
        overlay = self.hit_overlay
        if overlay is None:
            return
        try:
            width, height = _measure_toplevel_size(self.root)
            x = int(self.root.winfo_x())
            y = int(self.root.winfo_y())
            overlay.geometry(f"{width}x{height}+{x}+{y}")

            if sys.platform == "win32":
                self._hwnd = _tk_hwnd(self.root)
                self._overlay_hwnd = _tk_hwnd(overlay)
                if not self._apply_overlay_transparency():
                    if self._overlay_usable:
                        self._overlay_usable = False
                        overlay.withdraw()
                        self._bind_content_interactions()
                    return

            if not self._overlay_usable:
                return

            if not overlay.winfo_ismapped():
                overlay.deiconify()
            self._repair_zorder_if_needed()
        except tk.TclError:
            pass

    def _build_layout(self) -> None:
        container = tk.Frame(
            self.root,
            bg=TRANSPARENT_COLOR,
            padx=WINDOW_PADDING_X,
            pady=WINDOW_PADDING_Y,
        )
        container.pack(fill="both", expand=True)
        self._content_container = container

        content = tk.Frame(container, bg=TRANSPARENT_COLOR)
        content.pack()

        self._build_value_label(content, self.london_var).pack(side="left")

        separator = tk.Label(
            content,
            text="|",
            font=("Segoe UI", 22),
            fg=SEPARATOR_COLOR,
            bg=TRANSPARENT_COLOR,
            padx=14,
        )
        separator.pack(side="left")

        self._build_value_label(content, self.cny_var).pack(side="left")

    def _build_value_label(self, parent: tk.Widget, value_var: tk.StringVar) -> tk.Label:
        return tk.Label(
            parent,
            textvariable=value_var,
            font=("Segoe UI Semibold", 22),
            fg=TEXT_COLOR,
            bg=TRANSPARENT_COLOR,
        )

    def _configure_context_menu(self) -> None:
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="打开京东金价页面", command=self._open_site_from_menu)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="启用开机自启动", command=self._enable_startup_from_ui)
        self.context_menu.add_command(label="关闭开机自启动", command=self._disable_startup_from_ui)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="退出", command=self.shutdown)

    def _schedule_refresh(self) -> None:
        now = time.monotonic()
        if (
            self.last_poll_at is not None
            and now - self.last_poll_at > RESUME_GAP_SECONDS
        ):
            self._handle_system_resume()
        self.last_poll_at = now
        self.refresh_async()
        self.root.after(POLL_INTERVAL_MS, self._schedule_refresh)

    def _handle_system_resume(self) -> None:
        self.last_seq = -1
        threading.Thread(target=self._reset_monitor_worker, daemon=True).start()

    def _reset_monitor_worker(self) -> None:
        try:
            self.monitor.reset()
        except Exception:
            pass

    def refresh_async(self) -> None:
        if self.is_refreshing:
            return

        self.is_refreshing = True
        threading.Thread(target=self._refresh_worker, daemon=True).start()

    def _refresh_worker(self) -> None:
        try:
            snapshot = self.monitor.read_snapshot()
        except Exception as exc:
            try:
                self.monitor.reset()
            except Exception:
                pass
            self.root.after(0, lambda error=exc: self._apply_error(error))
            self.root.after(0, self._finish_refresh)
            return

        if (
            snapshot is not None
            and snapshot.update_time_text
            and snapshot.seq != self.last_seq
        ):
            self.root.after(0, lambda value=snapshot: self._apply_snapshot(value))
        elif snapshot is None:
            self.root.after(0, lambda: self._apply_error("页面暂无数据"))
        self.root.after(0, self._finish_refresh)

    def _apply_snapshot(self, snapshot: PageSnapshot) -> None:
        self.last_seq = snapshot.seq
        if snapshot.london_gold_text:
            self.london_var.set(snapshot.london_gold_text)
        if snapshot.london_gold_cny_text:
            self.cny_var.set(snapshot.london_gold_cny_text)
        self.root.update_idletasks()
        self._sync_hit_overlay()

    def _apply_error(self, error: object) -> None:
        if self.london_var.get() not in {"----.--", "获取失败"}:
            return
        self.london_var.set("获取失败")
        self.cny_var.set("自动重试中")
        self.root.update_idletasks()
        self._sync_hit_overlay()

    def _finish_refresh(self) -> None:
        self.is_refreshing = False

    def _start_drag(self, event: tk.Event) -> None:
        self.drag_start_x = event.x_root - self.root.winfo_x()
        self.drag_start_y = event.y_root - self.root.winfo_y()

    def _drag_window(self, event: tk.Event) -> None:
        new_x = event.x_root - self.drag_start_x
        new_y = event.y_root - self.drag_start_y
        self.root.geometry(f"+{new_x}+{new_y}")
        overlay = self.hit_overlay
        if overlay is not None and self._overlay_usable:
            try:
                width, height = _measure_toplevel_size(self.root)
                overlay.geometry(f"{width}x{height}+{new_x}+{new_y}")
            except tk.TclError:
                pass
        self._repair_zorder_if_needed()

    def _finish_drag(self, _event: tk.Event) -> None:
        if self.save_position_job is not None:
            self.root.after_cancel(self.save_position_job)
        self.save_position_job = self.root.after(80, self._persist_position)
        self._sync_hit_overlay()
        self._raise_widget_stack()

    def _open_site(self, _event: tk.Event) -> None:
        webbrowser.open(SITE_URL)

    def _open_site_from_menu(self) -> None:
        webbrowser.open(SITE_URL)

    def _show_context_menu(self, event: tk.Event) -> None:
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def _enable_startup_from_ui(self) -> None:
        ensure_startup_enabled()
        status = "已启用开机自启动" if is_startup_enabled() else "启用开机自启动失败"
        messagebox.showinfo("JD Gold Widget", status)

    def _disable_startup_from_ui(self) -> None:
        disable_startup()
        status = "已关闭开机自启动" if not is_startup_enabled() else "关闭开机自启动失败"
        messagebox.showinfo("JD Gold Widget", status)

    def _persist_position(self) -> None:
        self.save_position_job = None
        save_position(self.root.winfo_x(), self.root.winfo_y())

    def shutdown(self) -> None:
        self._remove_zorder_guard()
        self.monitor.close()
        cleanup_stale_chrome_profiles()
        try:
            self.root.destroy()
        except tk.TclError:
            pass


def print_once() -> int:
    monitor = ChromeDomSource()
    try:
        snapshot = monitor.read_once()
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    finally:
        monitor.close()
        cleanup_stale_chrome_profiles()

    if snapshot is None:
        print(json.dumps({"error": "No page values detected"}, ensure_ascii=False, indent=2))
        return 1

    print(json.dumps(asdict(snapshot), ensure_ascii=False, indent=2))
    return 0


def print_cli_usage() -> int:
    print(
        "\n".join(
            [
                "JD Gold Widget CLI",
                "",
                "用法:",
                "  JDGoldWidgetCli.exe --once",
                "  JDGoldWidgetCli.exe --runtime-check",
                "  JDGoldWidgetCli.exe --startup-status",
                "  JDGoldWidgetCli.exe --enable-startup",
                "  JDGoldWidgetCli.exe --disable-startup",
                "",
                "日常桌面挂件请使用 JDGoldWidget.exe，不要双击 CLI。",
            ]
        )
    )
    return 2


def print_startup_status() -> int:
    print(
        json.dumps(
            {
                "startup_enabled": is_startup_enabled(),
                "startup_script": str(STARTUP_SCRIPT_PATH),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def print_runtime_info() -> int:
    browser_path = ""
    browser_error = ""

    try:
        browser_path = str(find_chrome_binary())
    except FileNotFoundError as exc:
        browser_error = str(exc)

    print(
        json.dumps(
            {
                "browser_path": browser_path,
                "browser_error": browser_error,
                "startup_enabled": is_startup_enabled(),
                "startup_script": str(STARTUP_SCRIPT_PATH),
                "chrome_profile_dir": str(CHROME_PROFILE_DIR),
                "python_executable": str(Path(sys.executable).resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def main(*, allow_gui: bool = True) -> int:
    if "--enable-startup" in sys.argv:
        ensure_startup_enabled()
        return print_startup_status()

    if "--disable-startup" in sys.argv:
        disable_startup()
        return print_startup_status()

    if "--startup-status" in sys.argv:
        return print_startup_status()

    if "--runtime-check" in sys.argv:
        return print_runtime_info()

    if "--once" in sys.argv:
        return print_once()

    if not allow_gui:
        return print_cli_usage()

    if not ensure_single_gui_instance():
        return 0

    cleanup_stale_chrome_profiles()
    if os.environ.get(SKIP_AUTO_STARTUP_ENV) != "1":
        ensure_startup_enabled()

    root = tk.Tk()
    app = GoldWidgetApp(root)
    try:
        root.mainloop()
    finally:
        app.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
