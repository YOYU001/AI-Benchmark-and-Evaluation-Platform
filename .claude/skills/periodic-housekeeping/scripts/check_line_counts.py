"""Report line counts for CLAUDE.md, AGENTS.md, PROGRESS.md, README.md, TODO.md
against the project's 150-line guideline.

Usage:
    python check_line_counts.py [project_root]

If project_root is omitted, uses the current working directory.
"""

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

LINE_LIMIT = 150
TARGET_FILES = ["CLAUDE.md", "AGENTS.md", "PROGRESS.md", "README.md", "TODO.md"]


def count_lines(path: Path) -> int:
    with path.open("r", encoding="utf-8") as f:
        return sum(1 for _ in f)


def main() -> None:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()

    print(f"檢查目錄：{root}\n")
    any_over = False

    for name in TARGET_FILES:
        path = root / name
        if not path.exists():
            print(f"- {name}: 不存在，略過")
            continue

        lines = count_lines(path)
        status = "超過門檻" if lines > LINE_LIMIT else "OK"
        if lines > LINE_LIMIT:
            any_over = True

        print(f"- {name}: {lines} 行 / {LINE_LIMIT} 行門檻 -> {status}")

    print()
    if any_over:
        print("有檔案超過門檻，建議依 SKILL.md 的流程整理（規則型文件修剪、日誌型文件歸檔）。")
    else:
        print("目前都在門檻內，不需要處理。")


if __name__ == "__main__":
    main()
