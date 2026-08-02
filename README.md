# Daily Topic Article Pipeline

This project collects configured sources, clusters related stories, scores and votes on a daily topic, re-checks evidence, and writes a sourced article only when the configured confidence rules are met.

## Run locally

```powershell
.\auto\Scripts\python.exe -m pip install -r requirements.txt
$env:GEMINI_API_KEY = "your-key"
.\auto\Scripts\python.exe main.py --limit 20
```

Copy `.env.example` to `.env` to keep the key outside version control. Without `GEMINI_API_KEY`, collection, scoring, voting, evidence audits, and reports still run; article writing is skipped safely.

Generated files are written to `output/`:

- `YYYY-MM-DD-topic.md` — selected topic and transparent scoring.
- `YYYY-MM-DD-evidence.json` — research audit with sources and retrieval outcomes.
- `YYYY-MM-DD-article.md` — generated article and its cited sources.

Raw collected articles are exported to `storage/articles.txt`, while the SQLite database stores articles, topics, votes, evidence, and generated-article records locally. Generated articles use Medium-style Markdown: a title, subtitle, key takeaways, section headings, image slot, and source list. Set `article.cover_image_url` only to an original or properly licensed image. A code block appears only when verified research contains source code.

## Configure topic confidence

Edit `config/sources.yaml` to add sources and adjust reliability, category weights, confidence weights, source/evidence minimums, and the Gemini model. The default is the free-tier `gemini-3.5-flash-lite` model. `manual_votes` accepts a topic key or lower-case topic title with a numeric vote adjustment. The topic key is shown in each evidence audit. You can also vote for a run with `--vote topic-key=5` (repeat the option for more votes).

## GitHub Actions production setup

1. Create a GitHub repository and push this project.
2. In **Settings → Secrets and variables → Actions**, add `GEMINI_API_KEY`.
3. Ensure Actions has **Read and write permissions** for repository contents.
4. The included workflow runs daily at 06:15 UTC or on demand from the Actions tab.

The workflow commits the generated topic report, evidence audit, article, and text export back to the repository. It serializes runs so two jobs cannot select conflicting topics on the same day.
