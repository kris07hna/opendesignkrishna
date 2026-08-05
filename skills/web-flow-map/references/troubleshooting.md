# Troubleshooting Guide — Web Flow Mapper

---

## Environment Issues

### `ModuleNotFoundError: No module named 'playwright'`

```bash
# Install Playwright in the project venv
.venv/Scripts/python -m pip install playwright        # Windows
.venv/bin/python -m pip install playwright            # macOS/Linux
```

### `BrowserType.launch: Executable doesn't exist`

```bash
# Install Chromium browser
.venv/Scripts/python -m playwright install chromium   # Windows
.venv/bin/python -m playwright install chromium       # macOS/Linux
```

### `python: command not found` / wrong Python version

```bash
# Verify Python 3.9+
python --version
python3 --version

# Use the venv Python directly
.venv/Scripts/python --version   # Windows
.venv/bin/python --version       # macOS/Linux
```

---

## Navigation Issues

### Script exits at step 1 with gate detected

**Cause**: The target website requires login to browse any page.  
**Fix**: The site is fully behind auth — cannot be mapped without credentials.  
**Action**: Inform user the site requires login to access public pages. Try the marketing/landing page URL instead of an app URL.

```bash
# Try the public marketing site, not the app
--url "https://example.com"      # ✅ marketing site
# instead of
--url "https://app.example.com"  # ❌ app (likely behind login)
```

### All screenshots are blank or show a white page

**Cause**: Aggressive bot detection (e.g. Cloudflare challenge, JS-heavy auth).  
**Fix**: Try `--no-ai` first. If still blank, the site may require a real browser session.

```bash
.venv/Scripts/python crawl_map_ai.py --url "URL" --goal "GOAL" --no-ai --full-page
```

### Navigation stops after 2-3 steps

**Cause**: Nav links lead to gated pages or the site has very few public sections.  
**Fix**: Normal behavior — the mapper stops at auth/payment walls. Check `sitemap.json` for flagged pages.

### Script hangs for more than 2 minutes

**Cause**: Site has slow loading, infinite scroll, or heavy WebGL that delays networkidle.  
**Fix**: This is expected for creative/WebGL-heavy sites. Wait it out (up to 5 min).  
If it truly hangs, cancel with `Ctrl+C` and re-run with `--no-ai` and `--max-steps 8`.

### OpenCode timeout messages in log

**Cause**: OpenCode CLI taking too long to respond (AI reasoning timeout).  
**Fix**: Normal — the script automatically falls back to heuristic navigation.  
To disable AI entirely: add `--no-ai` flag.

---

## Screenshot Issues

### Screenshots look correct but cut off content

**Cause**: Using viewport mode instead of full-page.  
**Fix**: Add `--full-page` flag.

```bash
.venv/Scripts/python crawl_map_ai.py --url "URL" --goal "GOAL" --full-page
```

### Mobile screenshots show desktop layout

**Cause**: Site doesn't respect the mobile user-agent or viewport.  
**Normal**: Some sites serve identical layouts for all viewports. This is a site limitation, not a mapper bug.

### Some screenshots are missing from the whiteboard

**Cause**: That step's screenshot failed to save (page crashed, nav error).  
**Fix**: Check console output for `[ACTION ERROR]` lines. The whiteboard shows a grey placeholder rectangle for missing screenshots.

---

## Output Issues

### `userflow.sketch.json` not generated

**Cause**: Script crashed before completing.  
**Fix**: Check the full console output for error messages. Most common cause is Playwright not installed.

### Whiteboard opens in Open Design but is empty

**Cause**: File was corrupted or truncated during write.  
**Fix**: Re-run the script. Ensure the output directory has write permissions.

### `sitemap.json` shows 0 pages

**Cause**: Initial navigation failed (network error, unreachable URL).  
**Fix**: Verify the URL is publicly accessible. Test in a browser first.

---

## Performance Tuning

| Need | Flag to add |
|---|---|
| Faster run (skip AI reasoning) | `--no-ai` |
| Fewer steps | `--max-steps 8` |
| Desktop only (skip mobile pass) | `--desktop-only` |
| Mobile only (skip desktop pass) | `--mobile-only` |
| Different output location | `--output-dir my_folder` |
| More steps for large sites | `--max-steps 24` |

---

## Windows-Specific Issues

### `Scripts\python` not found

PowerShell uses backslash. Use:
```powershell
.venv\Scripts\python crawl_map_ai.py --url "URL" --goal "GOAL"
```

### `python` opens Microsoft Store instead of running

```powershell
# Use the full venv path
.venv\Scripts\python.exe crawl_map_ai.py --url "URL" --goal "GOAL"
```

### Line continuation in PowerShell

Use backtick (`) not backslash for multi-line commands:
```powershell
.venv\Scripts\python crawl_map_ai.py `
  --url "https://example.com" `
  --goal "Map all sections" `
  --full-page
```
