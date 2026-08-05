"""Move older dated entries out of PROGRESS.md into PROGRESS_ARCHIVE.md.

PROGRESS.md is a chronological log with entries under "## YYYY-MM-DD" headers.
This script keeps the N most recent entries in PROGRESS.md and appends the
rest to PROGRESS_ARCHIVE.md (creating it if needed). It does not delete any
content -- everything moved is preserved in the archive file.

Usage:
    python archive_progress.py --keep-recent N [project_root]

Always confirm the --keep-recent value with the user before running --
this script does not decide that on its own.
"""

import argparse
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

DATE_HEADER_RE = re.compile(r"^## \d{4}-\d{2}-\d{2}\s*$", re.MULTILINE)


def split_entries(content: str) -> tuple[str, list[str]]:
    """Split PROGRESS.md into (preamble, [entry_text, ...]), most recent last."""
    matches = list(DATE_HEADER_RE.finditer(content))
    if not matches:
        return content, []

    preamble = content[: matches[0].start()]
    entries = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        entries.append(content[m.start():end])
    return preamble, entries


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--keep-recent", type=int, required=True,
                         help="保留在 PROGRESS.md 裡的最近幾筆日期紀錄")
    parser.add_argument("project_root", nargs="?", default=".")
    args = parser.parse_args()

    root = Path(args.project_root)
    progress_path = root / "PROGRESS.md"
    archive_path = root / "PROGRESS_ARCHIVE.md"

    if not progress_path.exists():
        print(f"找不到 {progress_path}")
        return

    content = progress_path.read_text(encoding="utf-8")
    preamble, entries = split_entries(content)

    if len(entries) <= args.keep_recent:
        print(f"目前只有 {len(entries)} 筆日期紀錄，不需要歸檔（--keep-recent={args.keep_recent}）。")
        return

    to_archive = entries[: len(entries) - args.keep_recent]
    to_keep = entries[len(entries) - args.keep_recent:]

    # write archive (append, oldest-first, preserving original order)
    if archive_path.exists():
        archive_content = archive_path.read_text(encoding="utf-8")
    else:
        archive_content = "# PROGRESS_ARCHIVE.md\n\n本檔案存放 PROGRESS.md 歸檔出來的較舊紀錄，由 periodic-housekeeping skill 產生。\n\n---\n"

    archive_content = archive_content.rstrip("\n") + "\n\n" + "\n".join(to_archive)
    archive_path.write_text(archive_content, encoding="utf-8")

    # rewrite PROGRESS.md with only the kept entries + pointer to archive
    # (skip the note if a previous run already left it in the preamble)
    note = "> 更早的紀錄請見 `PROGRESS_ARCHIVE.md`。\n\n"
    if note.strip() in preamble:
        new_progress = preamble.rstrip("\n") + "\n\n" + "\n".join(to_keep)
    else:
        new_progress = preamble.rstrip("\n") + "\n\n" + note + "\n".join(to_keep)
    progress_path.write_text(new_progress, encoding="utf-8")

    print(f"已把 {len(to_archive)} 筆日期紀錄搬到 {archive_path}")
    print(f"PROGRESS.md 保留最近 {len(to_keep)} 筆紀錄")


if __name__ == "__main__":
    main()
