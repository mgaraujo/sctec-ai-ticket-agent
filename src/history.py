import json
from pathlib import Path

# Path to the JSON file that stores ticket history (project-level data)
HISTORY_FILE = Path(__file__).parent / "data" / "tickets_history.json"

# Ensure the directory exists and the file is initialized
HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
if not HISTORY_FILE.exists():
    HISTORY_FILE.write_text('[]', encoding='utf-8')

def load_history() -> list:
    """Load the entire ticket history as a list of dictionaries."""
    try:
        return json.loads(HISTORY_FILE.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        return []

def append_history(record: dict) -> None:
    """Append a new ticket record to the history file.

    The function reads the current JSON array, appends *record*, and writes it back.
    For this prototype a simple file‑based approach is sufficient.
    """
    history = load_history()
    history.append(record)
    HISTORY_FILE.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding='utf-8')

def get_ticket(ticket_id: str) -> dict | None:
    """Return the ticket dict with the given *ticket_id* (or ``None`` if not found)."""
    for rec in load_history():
        if rec.get('ticket_id') == ticket_id:
            return rec
    return None
