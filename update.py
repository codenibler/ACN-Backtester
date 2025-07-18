import sys
import json
import subprocess
import time

from bot.config import __version__
from PySide6.QtWidgets import QMessageBox, QApplication

GITHUB_TOKEN = "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"
GITHUB_API      = "https://api.github.com/repos/codenibler/ACN-Backtester/releases/latest"
GITHUB_TAGS_API = "https://api.github.com/repos/codenibler/ACN-Backtester/tags"

def _log(msg: str):
    print(f"[update-debug] {msg}", file=sys.stderr)

def _fetch(url: str) -> tuple[str, str] | None:
    """
    GET *url* with curl and return (body, status_code) as strings.

    Assumes the repository is public, so no Authorization header is included.
    Returns None if curl itself fails (network/TLS error).
    """
    _log(f"curl → {url}")

    # -s  : silent
    # -w  : append status code on a new line
    cmd = ["curl", "-s", "-w", "\n%{http_code}", url]
    proc = subprocess.run(cmd, capture_output=True, text=True)

    _log(f"curl exit code: {proc.returncode}")
    if proc.returncode != 0:
        return None                               # network failure, not HTTP error

    body, status = proc.stdout.rsplit("\n", 1)    # last line is status
    _log(f"HTTP status: {status}")
    _log(f"Response preview: {body[:200]!r} …")

    return body, status

def _get_latest_tag_via_tags_api() -> str | None:
    _log("Falling back to tags API")
    out = _fetch(GITHUB_TAGS_API)
    if not out:
        _log("Tags API fetch failed")
        return None
    body, status = out
    if status != "200":
        _log(f"Tags API returned {status}")
        return None
    tags = json.loads(body)
    latest = tags[0]["name"] if tags else None
    _log(f"Latest tag from tags API: {latest!r}")
    return latest

def _download(url: str, out: str, tries: int = 4) -> bool:
    headers = ["-H", "Accept: application/octet-stream"]
    for attempt in range(1, tries + 1):
        _log(f"Download attempt {attempt}/{tries}")
        cmd = ["curl", "-fLSs"] + headers + ["-o", out, url]
        if subprocess.run(cmd).returncode == 0:
            return True
        time.sleep(2 * attempt)
    return False

def check_for_updates() -> None:
    _log("Starting update check (current version: " + __version__ + ")")
    out = _fetch(GITHUB_API)
    if not out:
        _log("Releases API fetch failed, aborting")
        return
    body, status = out

    if status == "404":
        _log("No published release found (404)")
        latest_tag = _get_latest_tag_via_tags_api()
    elif status == "200":
        data = json.loads(body)
        latest_tag = data.get("tag_name")
        _log(f"Found release tag: {latest_tag!r}")
    else:
        _log(f"Unexpected HTTP status: {status}, aborting")
        return

    if not latest_tag:
        _log("No tag obtained, aborting")
        return

    _log(f"Comparing tags: latest={latest_tag!r} vs current={__version__!r}")
    if latest_tag <= __version__:
        _log("Already up-to-date")
        return

    # find the right asset
    arch = subprocess.run(["uname", "-m"], capture_output=True, text=True).stdout.strip()
    _log(f"Machine arch: {arch}")
    asset_name = f"ACN-Backtester-{arch}.dmg"
    _log(f"Looking for asset named {asset_name}")

    if status == "200":
        assets = data.get("assets", [])
    else:
        # re-fetch the full release data now that we know the tag
        full = _fetch(GITHUB_API)
        if not full:
            _log("Failed to re-fetch release data, aborting")
            return
        assets = json.loads(full[0]).get("assets", [])

    asset = next((a for a in assets if a["name"] == asset_name), None)
    if not asset:
        _log("No matching asset found, aborting")
        return

    download_url = asset["browser_download_url"]
    _log(f"Update available! Asset URL: {download_url}")

    # prompt
    answer = QMessageBox.question(
        None,
        "Update Available",
        f"A new version ({latest_tag}) is available.\nDownload and install now?",
        QMessageBox.Yes | QMessageBox.No,
    )
    _log(f"User response: {'Yes' if answer == QMessageBox.Yes else 'No'}")
    if answer != QMessageBox.Yes:
        _log("User declined update")
        return


    # download & mount
    _log("Downloading update…")
    if not _download(download_url, asset_name):
        _log("Download failed, aborting.")
        QMessageBox.critical(None, "Update failed", "Couldn't download the installer.")
        return   
    
    _log("Opening DMG…")
    subprocess.run(["open", asset_name])
    _log("Exiting for install…")
    QApplication.quit()
    sys.exit(0)