import json
import re
import urllib.request

from app.core.version import APP_VERSION

try:
    from packaging.version import parse as _parse_version

    def _is_version_newer(current, latest):
        return _parse_version(latest) > _parse_version(current)
except Exception:
    def _normalize(v):
        v = v.lstrip('vV')
        parts = re.split(r'[.\-+]', v)
        norm = []
        for p in parts:
            if p.isdigit():
                norm.append(int(p))
            else:
                m = re.match(r'(\d+)(.*)', p)
                if m:
                    norm.append(int(m.group(1)))
                    norm.append(m.group(2))
                else:
                    norm.append(p)
        return norm

    def _cmp_lists(a, b):
        for ai, bi in zip(a, b):
            if isinstance(ai, int) and isinstance(bi, int):
                if ai < bi:
                    return -1
                if ai > bi:
                    return 1
            else:
                sa, sb = str(ai), str(bi)
                if sa < sb:
                    return -1
                if sa > sb:
                    return 1
        if len(a) < len(b):
            return -1
        if len(a) > len(b):
            return 1
        return 0

    def _is_version_newer(current, latest):
        try:
            a = _normalize(current)
            b = _normalize(latest)
            return _cmp_lists(a, b) < 0
        except Exception:
            return False


CURRENT_VERSION = APP_VERSION
REPO_OWNER = 'Abosmra3'
REPO_NAME = 'Tessera'
GITHUB_LATEST_API = f'https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest'
RELEASES_URL = f'https://github.com/{REPO_OWNER}/{REPO_NAME}/releases' if REPO_OWNER and REPO_NAME else ''


def get_update_status(timeout: int = 8):
    """
    Check GitHub release API for version updates.

    Returns:
        (update_available: bool, latest_tag: str|None, release_url: str)
    """
    if not REPO_OWNER or not REPO_NAME:
        return False, None, RELEASES_URL
    try:
        req = urllib.request.Request(
            GITHUB_LATEST_API,
            headers={'User-Agent': 'AutomationToolkit/1.0'},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read().decode('utf-8')

        payload = json.loads(data)
        latest_tag = payload.get('tag_name') or payload.get('name')
        release_url = payload.get('html_url') or RELEASES_URL

        if not latest_tag:
            return False, None, release_url

        return _is_version_newer(CURRENT_VERSION, latest_tag), latest_tag, release_url
    except Exception:
        return False, None, RELEASES_URL
