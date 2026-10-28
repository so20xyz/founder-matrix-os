#!/usr/bin/env python3
"""fm_help: draft нь vault/home замыг нууж Inbox-д note бичнэ; send нь --yes-гүйгээр юу ч илгээхгүй,
«Issue-ийн бие»-г зөв салгаж, хариулагдсан issue-г дахин илгээхгүй."""
import importlib.util
import io
import shutil
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

S = Path(__file__).resolve().parents[1] / "plugins" / "fm" / "skills" / "help" / "scripts" / "fm_help.py"
spec = importlib.util.spec_from_file_location("fm_help", S)
fh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fh)


def cap(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = fh.main(argv)
    return code, buf.getvalue()


def main():
    tmp = Path(tempfile.mkdtemp())
    v = tmp / "vault"
    (v / "01-GTD" / "Inbox").mkdir(parents=True)
    home = str(Path.home())

    code, out = cap(["draft", str(v), "--kind", "bug", "--title", "Цаглабар хоосон",
                     "--what", "Цаглабар %s/01-GTD дээр хоосон харагдана" % v,
                     "--steps", "1. /fm:update daily\n2. Цаглабар нээх",
                     "--expected", "Өнөөдрийн task харагдах ёстой",
                     "--error", "Traceback: %s\\.fmos\\config.json" % home,
                     "--command", "/fm:update daily"])
    rel = out.strip()
    note = v / rel
    text = note.read_text(encoding="utf-8")
    issue_body = fh.split_note(text)

    code_send, out_send = cap(["send", str(note)])
    sent_text = note.read_text(encoding="utf-8")

    # хариулагдсан (issue: бөглөгдсөн) note-ийг дахин илгээхгүй
    note2 = v / "01-GTD" / "Inbox" / "already.md"
    note2.write_text(text.replace("issue:\n", "issue: https://github.com/x/y/issues/1\n"), encoding="utf-8")
    code_again, out_again = cap(["send", str(note2)])

    checks = [
        ("draft exit 0", code == 0),
        ("note Inbox-д", rel.startswith("01-GTD/Inbox/") and note.is_file()),
        ("гарчиг note-д", "# Тусламж — Цаглабар хоосон" in text),
        ("vault зам нуугдсан", "<vault>/01-GTD" in text and str(v) not in issue_body),
        ("home зам нуугдсан", "<home>" in text and home not in issue_body),
        ("алдаа code block-д", "```" in issue_body and "Traceback" in issue_body),
        ("орчны мөр", "- fm plugin:" in issue_body and "- OS:" in issue_body),
        ("команд бичигдсэн", "/fm:update daily" in issue_body),
        ("Хариу хэсэг биед ороогүй", "## Хариу" not in issue_body),
        ("kind + label frontmatter", "kind: bug" in text and "label: bug" in text),
        ("send --yes-гүй бол илгээхгүй", code_send == 0 and "ИЛГЭЭГЭЭГҮЙ" in out_send),
        ("send dry-run note-ийг хөндөөгүй", sent_text == text),
        ("dry-run-д гарчгийн угтвар", "[алдаа] Цаглабар хоосон" in out_send),
        ("илгээгдсэн note дахин явахгүй", code_again == 0 and "аль хэдийн илгээгдсэн" in out_again),
    ]
    shutil.rmtree(tmp, ignore_errors=True)
    bad = [n for n, ok in checks if not ok]
    for n, ok in checks:
        print(("PASS  " if ok else "FAIL  ") + n)
    print("\n%d/%d passed" % (len(checks) - len(bad), len(checks)))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
