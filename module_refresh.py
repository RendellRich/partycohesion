"""Make sure a deploy's new code is used without restarting the app.

Streamlit re-reads app.py and the pages on every run, but helper modules (ui, platform_utils and the rest) stay in
memory once imported. When a deploy changes one of them, a page can import a name the old copy doesn't have and fail
with an ImportError until the app is rebooted. drop_changed_local_modules() runs at the top of app.py: if any of the
site's own helper modules in memory is older than its file on disk, all of them are forgotten, so the next import
reads the new code. All are dropped together so no module keeps a reference to an old copy of another.

How a module's age is known: when Python imports a module it writes (or checks) the compiled copy in __pycache__,
whose header records the size and modification time of the source it was compiled from. If the source on disk no
longer matches that header, the module in memory came from an older file. Where no compiled copy exists, the file's
modification time is recorded the first time this check sees the module and compared from then on.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STAMP = "_pc_loaded_mtime"


def _compiled_source_stamp(mod) -> tuple[int, int] | None:
    """(mtime, size) of the source the module's compiled copy was built from, or None if unknown."""
    cached = getattr(getattr(mod, "__spec__", None), "cached", None)
    try:
        header = Path(cached).read_bytes()[:16]
    except (OSError, TypeError):
        return None
    if len(header) < 16 or int.from_bytes(header[4:8], "little") != 0:  # hash-based copies carry no mtime
        return None
    return int.from_bytes(header[8:12], "little"), int.from_bytes(header[12:16], "little")


def _is_stale(mod, path: Path) -> bool:
    try:
        st = path.stat()
    except OSError:
        return True
    compiled = _compiled_source_stamp(mod)
    if compiled is not None:
        return compiled != (int(st.st_mtime) & 0xFFFFFFFF, st.st_size & 0xFFFFFFFF)
    stamp = getattr(mod, STAMP, None)
    if stamp is None:
        setattr(mod, STAMP, st.st_mtime)
        return False
    return stamp != st.st_mtime


def local_modules(root: Path = ROOT) -> dict:
    """The site's own helper modules in memory: files directly in the repo root, not the app script itself."""
    out = {}
    for name, mod in list(sys.modules.items()):
        path = getattr(mod, "__file__", None)
        if name.startswith("__") or not path:
            continue
        p = Path(path).resolve()
        if p.parent == root and p.suffix == ".py" and p.name != "app.py":
            out[name] = (mod, p)
    return out


def drop_changed_local_modules(root: Path = ROOT) -> list[str]:
    """Forget the site's own helper modules if any is older than its file. Returns the names dropped."""
    local = local_modules(root)
    stale = [_is_stale(mod, path) for mod, path in local.values()]  # check all, so each gets its fallback stamp
    if not any(stale):
        return []
    for name in local:
        del sys.modules[name]
    return sorted(local)
