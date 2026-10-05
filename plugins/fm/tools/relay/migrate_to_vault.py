#!/usr/bin/env python3
"""Move the relay engine's data from the legacy repo layout into the member's vault (one time per member).

  legacy  <repo>/relay/{registry,channels,discord,notion_links}.json   →  <vault>/_system/fm/
          <repo>/state/<project>.md (batons)                           →  <vault>/_system/fm/state/
  config  ~/.fmos/config.json {"vault", "device", "member"}            (written only if it does not exist)

Never copied: finance/tax/gold (+ any registry "private" project) batons, *.tsv manifests, state/pc-merge/,
state/vault-diff.md. Existing files in the vault are never overwritten unless --force.
Default is a DRY RUN that prints the plan; add --apply to execute. No git, no network.

Usage:
  python migrate_to_vault.py --vault "<abs vault path>" [--device Mac|PC|...] [--member <name>] [--repo <repo>]
                             [--apply] [--force]
  (--vault may be omitted when FM_VAULT or ~/.fmos/config.json already names the vault)
"""
import argparse
import getpass
import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fmconfig  # noqa: E402

DATA_FILES = ("registry.json", "channels.json", "discord.json", "notion_links.json")
SKIP_STATE_FILES = {"vault-diff.md"}          # generated manifest report, not a baton
SKIP_STATE_DIRS = {"pc-merge"}


def _private_projects(registry_path):
    priv = set(fmconfig.PRIVATE_PROJECTS)
    try:
        sessions = json.loads(Path(registry_path).read_text(encoding="utf-8")).get("sessions", {})
    except Exception:
        sessions = {}
    for v in sessions.values():
        if isinstance(v, dict) and v.get("project") and fmconfig.is_private(v):
            priv.add(v["project"])
    return priv


def plan(repo, vault, device, member, force=False):
    """Return (actions, config_action). action = (kind, src, dst, reason); kind ∈ copy|skip."""
    repo, vault = Path(repo), Path(vault)
    data = vault / "_system" / "fm"
    acts = []

    def add(src, dst):
        if dst.exists() and not force:
            acts.append(("skip", src, dst, "exists in vault (use --force to overwrite)"))
        else:
            acts.append(("copy", src, dst, "overwrite" if dst.exists() else "new"))

    for name in DATA_FILES:
        src = repo / "relay" / name
        if src.is_file():
            add(src, data / name)

    priv = _private_projects(repo / "relay" / "registry.json")
    st = repo / "state"
    if st.is_dir():
        for src in sorted(st.iterdir(), key=lambda p: p.name.lower()):
            if src.is_dir():
                if src.name in SKIP_STATE_DIRS:
                    acts.append(("skip", src, None, "pc-merge snapshot (not a baton)"))
                continue
            if src.suffix.lower() == ".tsv":
                acts.append(("skip", src, None, "manifest (.tsv)"))
            elif src.suffix.lower() != ".md" or src.name in SKIP_STATE_FILES:
                acts.append(("skip", src, None, "not a baton"))
            elif src.stem in priv:
                acts.append(("skip", src, None, "PRIVATE — never copied"))
            else:
                add(src, data / "state" / src.name)

    cfg_file = fmconfig.CONFIG_FILE
    cfg = {"vault": str(vault), "device": device, "member": member}
    cfg_action = ("skip", cfg_file, cfg, "exists — left unchanged") if cfg_file.exists() else ("write", cfg_file, cfg, "new")
    return acts, cfg_action


def apply(acts, cfg_action):
    n = 0
    for kind, src, dst, _ in acts:
        if kind != "copy":
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src), str(dst))      # byte copy: keeps encoding + line endings
        n += 1
    kind, cfg_file, cfg, _ = cfg_action
    if kind == "write":
        cfg_file.parent.mkdir(parents=True, exist_ok=True)
        cfg_file.write_text(json.dumps(cfg, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return n


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Copy legacy relay data into <vault>/_system/fm (dry run by default).")
    ap.add_argument("--vault", default=str(fmconfig.VAULT) if fmconfig.VAULT else None)
    ap.add_argument("--device", default=fmconfig.DEVICE)
    ap.add_argument("--member", default=fmconfig.MEMBER or getpass.getuser())
    ap.add_argument("--repo", default=str(fmconfig.REPO))
    ap.add_argument("--apply", action="store_true", help="execute the plan (default: dry run)")
    ap.add_argument("--force", action="store_true", help="overwrite files that already exist in the vault")
    a = ap.parse_args(argv)
    if not a.vault:
        ap.error("vault алга: --vault \"<vault зам>\" өгнө үү (эсвэл FM_VAULT / ~/.fmos/config.json)")
    vault = Path(os.path.expanduser(a.vault))
    if not vault.is_dir():
        ap.error(f"vault хавтас олдсонгүй: {vault}")

    acts, cfg_action = plan(a.repo, vault, a.device, a.member, a.force)
    mode = "APPLY" if a.apply else "DRY-RUN"
    print(f"[{mode}] repo {a.repo} → vault {vault / '_system' / 'fm'}")
    for kind, src, dst, why in acts:
        if kind == "copy":
            print(f"  COPY  {Path(src).relative_to(a.repo)} → {Path(dst).relative_to(vault)}  ({why})")
        else:
            print(f"  SKIP  {Path(src).relative_to(a.repo)}  ({why})")
    kind, cfg_file, cfg, why = cfg_action
    print(f"  {'CONFIG' if kind == 'write' else 'SKIP '}  {cfg_file}  {json.dumps(cfg, ensure_ascii=False)}  ({why})")
    if not a.apply:
        print("Dry run — nothing written. Re-run with --apply to execute.")
        return 0
    n = apply(acts, cfg_action)
    print(f"done: {n} file(s) copied" + (", config written" if kind == "write" else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
