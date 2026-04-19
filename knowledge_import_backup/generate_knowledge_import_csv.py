#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regenerate knowledge_articles_import.csv from article_content.py in this directory."""

import csv
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from article_content import (  # noqa: E402
    ARTICLE_SPECS,
    FOLDER_IMPORT_EXTERNAL_ID,
    FOLDER_NAME,
)

OUT = HERE / "knowledge_articles_import.csv"

COLUMNS = [
    "id",
    "name",
    "category",
    "parent_id/id",
    "body",
    "website_published",
]


def main():
    rows = [
        {
            "id": FOLDER_IMPORT_EXTERNAL_ID,
            "name": FOLDER_NAME,
            "category": "folder",
            "parent_id/id": "",
            "body": "",
            "website_published": "",
        }
    ]
    for _hook_xmlid, import_suffix, title, body in ARTICLE_SPECS:
        rows.append(
            {
                "id": f"__import__.{import_suffix}",
                "name": title,
                "category": "article",
                "parent_id/id": FOLDER_IMPORT_EXTERNAL_ID,
                "body": body.strip(),
                "website_published": "True",
            }
        )

    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, quoting=csv.QUOTE_MINIMAL)
        w.writeheader()
        w.writerows(rows)

    print(f"Wrote {len(rows)} rows to {OUT}")


if __name__ == "__main__":
    main()
