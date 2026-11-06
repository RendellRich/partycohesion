"""After a deploy changes a helper module, the next run imports the new code instead of the copy in memory."""
import importlib
import os
import sys
import time
import types

from module_refresh import drop_changed_local_modules


def _write(path, text, offset):
    path.write_text(text)
    t = time.time() + offset
    os.utime(path, (t, t))


def test_changed_module_is_reimported_even_if_never_checked_before(tmp_path, monkeypatch):
    """The live failure: the module was imported, then the deploy changed its file before any check saw it."""
    monkeypatch.syspath_prepend(str(tmp_path))
    _write(tmp_path / "helper_a.py", "VALUE = 1\n", -100)
    _write(tmp_path / "helper_b.py", "import helper_a\nOTHER = 2\n", -100)
    import helper_b  # noqa: F401  (imports helper_a too)
    _write(tmp_path / "helper_a.py", "VALUE = 1\nNEW_NAME = 3\n", 0)  # the deploy
    assert drop_changed_local_modules(tmp_path) == ["helper_a", "helper_b"]  # all dropped together
    assert "helper_a" not in sys.modules and "helper_b" not in sys.modules
    assert importlib.import_module("helper_a").NEW_NAME == 3
    assert drop_changed_local_modules(tmp_path) == []  # the fresh copy is current


def test_unchanged_modules_kept(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(tmp_path))
    _write(tmp_path / "helper_c.py", "VALUE = 1\n", -100)
    import helper_c
    assert drop_changed_local_modules(tmp_path) == []
    assert sys.modules["helper_c"] is helper_c


def test_app_script_and_main_never_dropped(tmp_path, monkeypatch):
    fake_main = types.ModuleType("__main__")
    fake_main.__file__ = str(tmp_path / "app.py")
    (tmp_path / "app.py").write_text("")
    monkeypatch.setitem(sys.modules, "__main__", fake_main)
    drop_changed_local_modules(tmp_path)
    assert sys.modules["__main__"] is fake_main
