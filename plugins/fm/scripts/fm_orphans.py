#!/usr/bin/env python3
"""fm_orphans.py - vault-ийн холбоосгүй note, ашиглагдаагүй base-ийг жагсаана (уншина л, юу ч өөрчлөхгүй).

  python fm_orphans.py <vault>

Холбоосгүй = өөр note руу ч заадаггүй, өөр рүү нь ч холбоос ирдэггүй (frontmatter-ийн [[...]] тооцогдоно).
Ашиглагдаагүй base = ямар ч note-д нэр нь гардаггүй (embed ч, холбоос ч биш).
Архив, _system, хувийн (private: true) note-ыг жагсаалтад оруулахгүй.
"""
import collections, os, re, sys

SKIP_DIRS = {'.obsidian', '_trash', '.backups', '.git', 'node_modules', '.trash'}
QUIET = ('99-Archive', '_system')
LINK = re.compile(r'\[\[([^\]|#^]+)')


def main(vault):
    notes, bases = {}, []
    for root, dirs, files in os.walk(vault):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith('.')]
        for f in files:
            p = os.path.join(root, f).replace('\\', '/')
            rel = p[len(vault.rstrip('/\\')) + 1:]
            if f.endswith('.md'):
                notes[rel] = p
            elif f.endswith('.base'):
                bases.append(rel)
    byname = collections.defaultdict(list)
    for rel in notes:
        byname[os.path.basename(rel)[:-3].lower()].append(rel)

    def resolve(t):
        t = t.strip().replace('\\', '/')
        if t.lower().endswith('.md'):
            t = t[:-3]
        if t + '.md' in notes:
            return t + '.md'
        r = byname.get(os.path.basename(t).lower())
        return r[0] if r else None

    inbound, outbound, private, texts = collections.Counter(), collections.Counter(), set(), []
    for rel, p in notes.items():
        s = open(p, encoding='utf-8', errors='ignore').read()
        texts.append(s)
        if re.search(r'^private:\s*true', s[:2000], re.M) or '/finances/private/' in rel:
            private.add(rel)
        for m in LINK.finditer(s):
            if m.group(1).endswith('.base'):
                continue
            r = resolve(m.group(1))
            if r and r != rel:
                inbound[r] += 1
                outbound[rel] += 1
    blob = '\n'.join(texts)
    orphans = sorted(r for r in notes if not inbound[r] and not outbound[r]
                     and not r.startswith(QUIET) and r not in private)
    unused = sorted(b for b in bases if os.path.basename(b) not in blob and os.path.basename(b)[:-5] not in blob)
    print(f'# Vault холбоос шалгалт · {len(notes)} note · {len(bases)} base')
    print(f'\n## Холбоосгүй note ({len(orphans)})')
    print('\n'.join(f'- [[{r[:-3]}]]' for r in orphans) or '- байхгүй ✅')
    print(f'\n## Ашиглагдаагүй base ({len(unused)})')
    print('\n'.join(f'- {b}' for b in unused) or '- байхгүй ✅')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    sys.stdout.reconfigure(encoding='utf-8')
    main(sys.argv[1])
