"""tools/watchdog/fm_goom_agent.py (Mac LaunchAgents for goom dispatch/sync) + fm_health.check_goom + selfupdate SERVICES.
Everything runs against a temp HOME and stubbed launchctl/login: the real ~/Library/LaunchAgents and ~/.fmos are never touched."""
import base64, json, os, plistlib, stat, subprocess, sys, time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools" / "watchdog"))
import fm_goom_agent as ga  # noqa: E402
import fm_selfupdate as su  # noqa: E402

OK = lambda cmd, **k: subprocess.CompletedProcess(cmd, 0, "", "")


def jwt(exp):
    b = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")
    return f"{b({'alg': 'none'})}.{b({'exp': exp})}.sig"


def home(tmp_path, monkeypatch):
    monkeypatch.setattr(ga, "HOME", tmp_path)
    (tmp_path / ".fmos").mkdir()
    return tmp_path


def write_cfg(h, **over):
    cfg = {"url": "http://localhost:3000", "token": jwt(time.time() + 7200), "workspace_id": 1,
           "vault": "/v/Founder.Matrix", "sb_repo": "/w/second-brain", **over}
    ga.write_cfg(cfg)
    return cfg


def test_install_writes_both_plists(tmp_path, monkeypatch):
    h = home(tmp_path, monkeypatch); write_cfg(h)
    calls = []
    ga.install(run=lambda c, **k: calls.append(c) or OK(c), py="/opt/homebrew/bin/python3.12")
    d = plistlib.loads(ga.plist_path(ga.DISPATCH_LABEL).read_bytes())
    s = plistlib.loads(ga.plist_path(ga.SYNC_LABEL).read_bytes())
    assert ga.plist_path(ga.DISPATCH_LABEL) == h / "Library/LaunchAgents/com.fmos.goom-dispatch.plist"
    assert d["ProgramArguments"][0] == "/opt/homebrew/bin/python3.12" and d["ProgramArguments"][-1] == "--loop"
    assert d["ProgramArguments"][1].endswith("plugins/fm/scripts/fm_goom_dispatch.py")
    assert d["KeepAlive"] is True
    assert d["EnvironmentVariables"]["SB_TOOLS"] == "/w/second-brain" and d["EnvironmentVariables"]["FM_VAULT"] == "/v/Founder.Matrix"
    p = d["EnvironmentVariables"]["PATH"].split(":")
    assert str(h / ".local/bin") in p and "/opt/homebrew/bin" in p
    assert d["StandardOutPath"] == str(h / ".fmos/logs/goom-dispatch.log")
    assert s["StartInterval"] == 300 and s["ProgramArguments"][-1] == "sync-tick"
    # only launchctl, only the temp plists / labels, bootout -> bootstrap -> kickstart per job
    assert all(c[0] == "launchctl" for c in calls) and len(calls) == 6
    assert [c[1] for c in calls[:3]] == ["bootout", "bootstrap", "kickstart"]
    assert str(h) in calls[1][-1]


def test_install_dry_run_writes_nothing(tmp_path, monkeypatch, capsys):
    h = home(tmp_path, monkeypatch); write_cfg(h)
    ga.install(run=lambda c, **k: (_ for _ in ()).throw(AssertionError("no launchctl")), dry=True, py="/py")
    assert not (h / "Library").exists() and "fm_goom_dispatch.py" in capsys.readouterr().out


def test_install_needs_config(tmp_path, monkeypatch):
    home(tmp_path, monkeypatch)
    try:
        ga.install(run=OK, py="/py"); assert False
    except SystemExit as e:
        assert "fm_goom_agent.py init" in str(e)


def test_find_python_requires_312(monkeypatch):
    fake = lambda cmd, **k: subprocess.CompletedProcess(cmd, 0, "3.9\n" if "old" in cmd[0] else "3.12\n", "")
    assert ga.py_ok("/new/python3.12", fake) and not ga.py_ok("/old/python3", fake)
    assert not ga.py_ok("/x", lambda c, **k: subprocess.CompletedProcess(c, 1, "", "nope"))


def test_sync_tick_args(tmp_path, monkeypatch):
    h = home(tmp_path, monkeypatch); write_cfg(h)
    seen = []
    monkeypatch.setattr(ga.subprocess, "run", lambda cmd, **k: seen.append(cmd) or subprocess.CompletedProcess(cmd, 0))
    assert ga.sync_tick() == 0
    assert seen[0][1].endswith("fm_goom_sync.py") and seen[0][2:] == ["/v/Founder.Matrix", "--apply", "--no-covers"]


def test_init_writes_0600_and_no_password(tmp_path, monkeypatch):
    h = home(tmp_path, monkeypatch)
    (h / ".fmos/config.json").write_text(json.dumps({"vault": "/v/FM", "device": "Mac", "member": "Soyol"}))
    (h / "sb").mkdir()
    posted = []
    post = lambda url, body: posted.append((url, json.loads(body))) or {"JWT": jwt(time.time() + 9999)}
    args = ga.argparse.Namespace(url=None, vault=None, sb_repo=str(h / "sb"), workspace_id=7, owner_name=None,
                                 email="s@x.mn", save_keychain=False)
    cfg = ga.init(args, run=OK, post=post, prompt=lambda *_: "s3cret")
    assert posted == [("http://localhost:3000/api/web/public/login/", {"email": "s@x.mn", "password": "s3cret"})]
    p = ga.cfg_path()
    assert stat.S_IMODE(p.stat().st_mode) == 0o600
    on_disk = json.loads(p.read_text())
    assert on_disk["vault"] == "/v/FM" and on_disk["device"] == "Mac" and on_disk["owner_name"] == "Soyol"
    assert on_disk["workspace_id"] == 7 and on_disk["token"].count(".") == 2
    assert "s3cret" not in p.read_text() and "password" not in on_disk


def test_refresh_only_when_expiring(tmp_path, monkeypatch):
    h = home(tmp_path, monkeypatch)
    write_cfg(h, email="s@x.mn")
    boom = lambda url, body: (_ for _ in ()).throw(AssertionError("should not log in"))
    assert ga.refresh(if_expiring=True, post=boom) == 0           # 2 h left
    write_cfg(h, email="s@x.mn", token=jwt(time.time() + 60))
    monkeypatch.setenv("FM_GOOM_PASSWORD", "pw")
    new = jwt(time.time() + 99999)
    assert ga.refresh(if_expiring=True, post=lambda u, b: {"JWT": new}) == 0
    assert json.loads(ga.cfg_path().read_text())["token"] == new
    assert stat.S_IMODE(ga.cfg_path().stat().st_mode) == 0o600


def test_selfupdate_kickstarts_goom_dispatch():
    rows = [r for r in su.SERVICES if r[2] == "com.fmos.goom-dispatch"]
    assert len(rows) == 1 and rows[0][1] is None            # Mac only
    assert any("plugins/fm/scripts/fm_goom_dispatch.py".startswith(p) for p in rows[0][0])


# ---- fm_health.check_goom (subprocess with a temp HOME)
def health(h, vault):
    r = subprocess.run([sys.executable, str(REPO / "plugins/fm/scripts/fm_health.py"), "--vault", str(vault), "--json"],
                       capture_output=True, text=True, env={**os.environ, "HOME": str(h)})
    return {n: (lv, m) for lv, n, m in json.loads(r.stdout)}


def fake_sb(root, queued_age_min=None, vault=None):
    c = root / "tools/chat"; c.mkdir(parents=True)
    (c / "store.py").write_text("def list_channels(vault):\n    return ['gtd']\n")
    (c / "runs.py").write_text(
        "from types import SimpleNamespace as N\n"
        "def list_runs(vault, ch, status=None):\n"
        "    import pathlib\n"
        "    return [N(path=p.relative_to(vault).as_posix()) for p in pathlib.Path(vault).glob('run-*.md')] if status == 'queued' else []\n")
    if queued_age_min is not None:
        f = vault / "run-1.md"; f.write_text("x"); t = time.time() - queued_age_min * 60; os.utime(f, (t, t))


def test_health_goom(tmp_path):
    h, vault, sb = tmp_path / "h", tmp_path / "vault", tmp_path / "sb"
    (h / ".fmos").mkdir(parents=True); vault.mkdir()
    # no goom.json: check silently skipped
    assert "goom config" not in health(h, vault)
    fake_sb(sb, queued_age_min=9, vault=vault)
    (h / ".fmos/goom.json").write_text(json.dumps({"url": "u", "token": jwt(time.time() + 9999), "workspace_id": 1,
                                                  "vault": str(vault), "sb_repo": str(sb)}))
    r = health(h, vault)
    assert r["goom config"][0] == "✅" and r["goom sb_repo"][0] == "✅"
    assert r["goom dispatch"][0] == "⚠"                         # alive file missing = warn
    assert r["goom queue"][0] == "⚠"                            # 9 min old queued run
    if sys.platform == "darwin":
        assert r["goom launchd"][0] in ("✅", "⚠")               # launchctl is per user, not per HOME
    alive = h / ".fmos/goom-dispatch.alive"; alive.write_text("1")
    assert health(h, vault)["goom dispatch"][0] == "✅"
    t = time.time() - 120; os.utime(alive, (t, t))
    assert health(h, vault)["goom dispatch"][0] == "❌"
    (h / ".fmos/goom.json").write_text(json.dumps({"url": "u", "sb_repo": str(tmp_path / "nope")}))
    r = health(h, vault)
    assert r["goom config"][0] == "❌" and r["goom sb_repo"][0] == "❌"
