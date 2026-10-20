# Ledger

A private, local money tracker. It runs on your computer, keeps everything in one SQLite file, and never sends your data anywhere.

## Start it

```bash
./ledger
```

The first run sets up a virtualenv and installs dependencies; after that it starts in about a second and opens your browser at http://localhost:5001. On a Mac you can also double-click `Ledger.command` in Finder. Press Ctrl+C in the terminal to stop it.

## What it does

- **Import bank statements**: drop in a CSV, OFX, or QFX file from any bank. Ledger finds the columns, cleans up descriptions ("SQ *BLUE BOTTLE 123-456…" becomes "Blue Bottle Coffee"), suggests categories, skips anything already imported, and leaves transfers like card autopays unticked. It remembers each bank's column layout.
- **Rules that learn**: fix a category once and Ledger files that merchant the same way from then on. Rules can be edited and re-applied to past transactions.
- **Quick add**: press ⌘K and type `12.50 lunch yesterday` (or `+2150 paycheck`) to add a transaction instantly, with Undo.
- **Overview**: balance chart, this month vs. last month, insights, spending by category, upcoming bills
- **Activity**: search and filter everything; click to edit
- **Budgets** with a pace marker that understands fixed bills, and **recurring** bills and paychecks that post themselves
- **Backups**: automatic daily copies plus one before every import or restore (last 30 kept), one-click restore, CSV export

## Keyboard

| Key | Action |
| --- | --- |
| ⌘K | Search, jump anywhere, or quick add |
| N | New transaction |
| I | Import a statement |
| / | Search activity |
| G then O / A / B / R / S | Go to Overview, Activity, Budgets, Recurring, Settings |

## Where your data lives

- macOS: `~/Library/Application Support/Ledger/`
- Linux: `~/.local/share/ledger/`
- Windows: `%APPDATA%\Ledger\`

The folder holds `ledger.db` and a `backups/` folder. Set `LEDGER_DATA_DIR` to use a different folder, or `LEDGER_PORT` to use a different port.

## Code layout

| File | What it holds |
| --- | --- |
| `run.py` | Launcher: starts the local server and opens the browser |
| `app.py` | Flask app, local-only request guards, pages, CSV export |
| `api.py` | JSON API: overview, transactions, budgets, recurring, import, rules, backups |
| `importer.py` | Statement parsing, description cleanup, categorization, de-duplication |
| `storage.py` | SQLite settings, schema top-ups, backups and restore |
| `models.py` | Transaction, Budget, Recurring, Rule, ImportProfile |
| `config.py` | Data folder, categories, starter categorization keywords |
| `demo.py` | Sample data (tagged so it can be removed in one click) |
