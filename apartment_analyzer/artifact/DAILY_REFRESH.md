# Daily refresh of the "Paris Studio Investor" artifact

Run by a scheduled task every morning (06:37 Europe/Paris) in the
`datacamp-assignment-pandas` cloud environment. Artifact:
https://claude.ai/artifact/BwdC5p9TeWVXVhSrM6ew9M

1. Get the code:
   `git fetch origin claude/apartment-investment-analyzer-ip3j1v && git checkout claude/apartment-investment-analyzer-ip3j1v`
   then `pip install -q -r apartment_analyzer/requirements.txt`.
2. With the Artifact tool: `action: "read"` on the URL above (the page),
   then `action: "list"`, `scope: "files"` on it (so every published photo
   path is known before it is replaced or removed), then `action: "read"`
   with `path: "data.json"` and note where that file was saved. If
   data.json cannot be read, continue without it.
3. Build: `python -m apartment_analyzer.build_artifact --out build --previous <saved data.json>`
   (takes a few minutes: it downloads photos). It prints a summary.
4. Publish with the Artifact tool: `url` = the URL above,
   `file_path` = `build/index.html`, `files` = the map in
   `build/files.json` (its `null` entries delete photos no longer used).
   Do not pass `icon` or `capabilities`. If a publish sends more than
   255 files, split it into several publishes to the same `url`.
5. Reply with a short summary: listings found, new listings (title, price,
   mark), portals that failed. If nothing could be fetched, do not publish.

Do not commit or push anything.
