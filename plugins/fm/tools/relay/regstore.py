#!/usr/bin/env python3
"""Safe read / write of <vault>/_system/fm/registry.json, shared by relay.py and fm_role.py (P0-1, 2026-10-09).

20+ Claude sessions on one machine hit the registry from hooks at the same time, and the file lives on Google Drive.
Rules enforced here:
  * ONE cross-process lock, ~/.fmos/registry.lock (local disk, never on Drive), around every load→modify→save:
        with regstore.edit(path, {"sessions": {}}) as reg:
            reg["sessions"][sid] = {...}
    The lock is an OS byte-range lock (msvcrt on Windows, fcntl on macOS/Linux): released by the OS if the holder
    dies, so there is no stale-lock cleanup to get wrong. The same mechanism is exported as file_lock(path) for the
    other shared local files (relay.py: ~/.fmos/baton.lock for state/<project>.md, ~/.fmos/relay_state.lock).
  * Atomic writes: temp file in the same folder + os.replace, retried on Windows PermissionError (a reader or the
    Drive client holding the file open).
  * A rolling registry.json.bak (the previous content) before every write.
  * An existing file that cannot be read / parsed is NEVER written over: RegistryReadError is raised and a line goes
    to stderr. A missing file → the default.
Pure standard library, Python 3.9+, macOS / Windows / Linux.
"""
import contextlib
import copy
import json
import os
import sys
import tempfile
import time
from pathlib import Path

if os.name == "nt":
    import msvcrt
else:
    import fcntl

LOCK_TIMEOUT = 30.0  # seconds; a registry edit takes milliseconds, 30 s means something is badly wrong


class RegistryReadError(Exception):
    """registry.json exists but could not be read/parsed — callers must not write it."""


def log(msg):
    try:
        sys.stderr.write("[fm registry] %s\n" % msg)
    except UnicodeEncodeError:
        sys.stderr.buffer.write(("[fm registry] %s\n" % msg).encode("utf-8"))
    except Exception:
        pass


def lock_path():
    return Path.home() / ".fmos" / "registry.lock"


_held = {}  # lock path → [depth, file handle]; re-entrant within one process (nested edits must not deadlock)


@contextlib.contextmanager
def file_lock(path, timeout=LOCK_TIMEOUT, what="lock"):
    """Cross-process exclusive lock on a local lock file (OS byte-range lock, released by the OS if the holder
    dies). Re-entrant per path within one process. Used for registry.json, batons and the relay state file."""
    key = str(Path(path))
    if key in _held:
        _held[key][0] += 1
        try:
            yield
        finally:
            _held[key][0] -= 1
        return
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fh = open(str(p), "a+b")
    end = time.time() + timeout
    delay = 0.005
    while True:
        try:
            if os.name == "nt":
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except OSError:
            if time.time() > end:
                fh.close()
                raise TimeoutError("%s busy > %ss: %s" % (what, timeout, p))
            time.sleep(delay)
            delay = min(delay * 2, 0.1)
    _held[key] = [1, fh]
    try:
        yield
    finally:
        _held.pop(key, None)
        try:
            if os.name == "nt":
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        finally:
            fh.close()


def registry_lock(timeout=LOCK_TIMEOUT):
    """Cross-process exclusive lock on ~/.fmos/registry.lock."""
    return file_lock(lock_path(), timeout, what="registry lock")


def read(path, default, attempts=5):
    """Parsed JSON object at path. Missing → deep copy of default. Unreadable / corrupt / empty / not an object →
    RegistryReadError (after a few short retries: Windows sharing violations, a non-atomic writer mid-write)."""
    path = Path(path)
    err = None
    for i in range(attempts):
        if not path.exists():
            return copy.deepcopy(default)
        try:
            text = path.read_bytes().decode("utf-8-sig")
            data = json.loads(text)
            if isinstance(data, dict):
                return data
            err = "not a JSON object"
        except (OSError, ValueError) as e:  # ValueError covers JSONDecodeError + UnicodeDecodeError
            err = e
        time.sleep(0.05 * (i + 1))
    log("%s уншигдсангүй (%s) — дарж бичихгүй. Сэргээх: %s" % (path, err, path.name + ".bak"))
    raise RegistryReadError("%s: %s" % (path, err))


def _replace(src, dst, attempts=40):
    """os.replace with retries: on Windows it fails while another process has dst open."""
    for i in range(attempts):
        try:
            os.replace(str(src), str(dst))
            return
        except PermissionError:
            if i == attempts - 1:
                raise
            time.sleep(min(0.02 * (i + 1), 0.25))


def _write_tmp(folder, prefix, data_bytes):
    fd, tmp = tempfile.mkstemp(prefix=prefix, suffix=".tmp", dir=str(folder))
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data_bytes)
            fh.flush()
            os.fsync(fh.fileno())
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise
    return tmp


def write_atomic(path, data, indent=1, backup=True):
    """Write JSON atomically (same-folder temp + os.replace). backup=True first copies the current file to
    <name>.bak (also atomically)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if backup and path.exists():
        try:
            old = path.read_bytes()
            if old.strip():
                tmp = _write_tmp(path.parent, "." + path.name + ".bak.", old)
                try:
                    _replace(tmp, path.with_name(path.name + ".bak"))
                except BaseException:
                    with contextlib.suppress(OSError):
                        os.unlink(tmp)
                    raise
        except OSError as e:  # a missing backup must not block the write itself
            log("backup %s.bak бичигдсэнгүй (%s)" % (path.name, e))
    body = (json.dumps(data, ensure_ascii=False, indent=indent) + "\n").encode("utf-8")
    tmp = _write_tmp(path.parent, "." + path.name + ".", body)
    try:
        _replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise
    return path


@contextlib.contextmanager
def edit(path, default, normalize=None, indent=1):
    """Locked load→modify→save. Yields the registry dict; writes it back (with .bak) only if it changed.
    Raises RegistryReadError (nothing written) if the existing file cannot be read."""
    with registry_lock():
        data = read(path, default)
        if normalize:
            normalize(data)
        before = json.dumps(data, sort_keys=True, ensure_ascii=False)
        yield data
        if json.dumps(data, sort_keys=True, ensure_ascii=False) != before:
            write_atomic(path, data, indent=indent)
