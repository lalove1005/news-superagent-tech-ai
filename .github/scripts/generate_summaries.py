#!/usr/bin/env python3
import os
from datetime import datetime
import json

date_str = datetime.utcnow().strftime("%Y-%m-%d")
regions = ["USA", "China", "Europe", "Venezuela"]
langs = ["en", "es"]

os.makedirs(f"summaries/{date_str}", exist_ok=True)

for region in regions:
    for lang in langs:
        path = f"summaries/{date_str}/{region}_top5_{lang}.md"
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"# {region} Tech & AI Top 5 - {date_str}\n\n")
            for i in range(1, 6):
                f.write(f"{i}. **Headline {i}** - 150 word summary placeholder for {region} in {lang}.\n\n")
print(f"Generated summaries for {date_str}")
