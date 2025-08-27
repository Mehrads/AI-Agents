## AI Agents: Gmail-driven Google Calendar Assistant

This project connects Gmail, an LLM, and Google Calendar to automatically create or modify calendar events based on natural language requests extracted from your unread emails. It also keeps a lightweight semantic memory of events using ChromaDB to enable event lookups and updates.

### What it does
- Parses the latest unread Gmail message into a natural language description
- Uses an LLM router to classify the request: create a new event or modify an existing one
- Extracts structured event details (title, time, duration, participants)
- Creates or updates events in Google Calendar
- Stores event records in ChromaDB plus a CSV index for simple retrieval and subsequent updates

### Repository layout
- `calendar-modifier.py`: Orchestrates the end-to-end flow (Gmail → LLM routing → Calendar create/modify → ChromaDB persistence). Entry point.
- `gmail_reader.py`: Minimal Gmail API client that reads the latest unread email and returns the body text.
- `database_retrieval.py`: ChromaDB utilities to add and update event records; maintains `eventdb/df_db.csv` for id-to-description mapping.
- `eventdb/`: Local persistent vector store and CSV index (ignored from git).
- `.env` (ignored): Holds API keys and local configuration.

### How it works (high level)
1. Gmail ingestion: `gmail_reader.readEmails()` fetches the most recent unread email body via Gmail API and returns it as the input description.
2. Routing with LLM: `route_calendar_request()` calls the OpenAI-compatible API (via OpenRouter) to classify the intent into `new_event | modify_event | other` with a confidence score and cleaned description.
3. New event creation: `handle_new_event()` asks the LLM to extract structured fields, parses time using `dateutil`, then creates a Google Calendar event and stores a textual record into ChromaDB/CSV.
4. Modify event: `handle_modify_event()` extracts update details, finds the target event by querying ChromaDB with the provided identifier, pulls the `Calendar_ID` from the stored description, and updates the Google Calendar event.
5. Persistence: `database_retrieval.add_to_db()` and `update_to_db()` manage a ChromaDB collection `eventdb` and synchronize the `eventdb/df_db.csv` index.

### Key technologies
- Google Calendar API and Gmail API via `google-api-python-client`
- OpenAI-compatible chat API via [OpenRouter](https://openrouter.ai/)
- Vector store: [ChromaDB](https://www.trychroma.com/)
- Time parsing: `python-dateutil`
- Configuration loading: `python-dotenv`

### Prerequisites
- Python 3.12+
- Google Cloud project with Calendar and Gmail APIs enabled
- OAuth client credentials (for Gmail) and service account (for Calendar)
- An OpenRouter API key (or compatible OpenAI API key)

### Setup
1. Create and activate a virtual environment (recommended):
```
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:
```
pip install openai python-dotenv google-api-python-client google-auth google-auth-oauthlib python-dateutil chromadb pandas
```

3. Prepare credentials (store locally, never commit):
- Gmail OAuth client secret JSON (Installed app) for user consent
- Google Calendar service account JSON with Calendar scope

4. Create `.env` in the project root:
```
OPENAI_API_KEY=your_openrouter_api_key
# Optional: point to local credential files if you parameterize paths below
GMAIL_CLIENT_SECRET_PATH=/absolute/path/to/client_secret.json
CALENDAR_SERVICE_ACCOUNT_PATH=/absolute/path/to/service_account.json
GOOGLE_CALENDAR_ID=you@example.com
```

5. Ensure the following are in `.gitignore` (already configured):
```
.env
.idea/
env/
__pycache__/
.DS_Store
*.json
eventdb/
```

### Configuration notes (paths and IDs)
By default, the scripts currently use absolute paths in two places:
- `calendar-modifier.py` → `SERVICE_ACCOUNT_FILE`
- `gmail_reader.py` → `SERVICE_ACCOUNT_FILE` (OAuth client secret)

For portability, update these to read from environment variables (recommended) or change to your local absolute paths:
```python
# Example change (calendar-modifier.py)
SERVICE_ACCOUNT_FILE = os.environ.get("CALENDAR_SERVICE_ACCOUNT_PATH")
CALENDAR_ID = os.environ.get("GOOGLE_CALENDAR_ID")

# Example change (gmail_reader.py)
SERVICE_ACCOUNT_FILE = os.environ.get("GMAIL_CLIENT_SECRET_PATH")
```

### Running
The primary entry point is `calendar-modifier.py`. It will:
- Read the latest unread email
- Route the request and extract structured details
- Create/modify an event in Google Calendar
- Save/update the event record in ChromaDB and `eventdb/df_db.csv`

Run:
```
python calendar-modifier.py
```

On success, you’ll see a message like:
```
Response: Created new event with the name 'Team Meeting' with Calendar_ID=... starting at 2025-06-03 14:00 with participant(s) Alice, Bob
```

### How event updates work
- When you later request a modification (e.g., “Move ‘Team Meeting’ to next Wednesday at 3pm”), the system queries ChromaDB for the most similar record to the provided identifier, extracts the `Calendar_ID` from the stored description, and then issues an update via Google Calendar API.

### Data storage
- Vector store: `eventdb/` (ChromaDB persistent store)
- CSV index: `eventdb/df_db.csv` maintains `ids -> description` entries to keep textual records synchronized with the vector store.

### Security and privacy
- Secrets and tokens must remain local only. The repo is configured to ignore `.env`, `*.json` credentials, `token.json`, local IDE and venv folders, and database artifacts.
- If you previously committed secrets, rotate them immediately and scrub history if needed. GitHub Push Protection may block pushes containing detected secrets. See: [Working with push protection](https://docs.github.com/code-security/secret-scanning/working-with-secret-scanning-and-push-protection/working-with-push-protection-from-the-command-line#resolving-a-blocked-push)

### Troubleshooting
- Gmail consent flow opens a local browser window; ensure you can complete OAuth locally. The resulting `token.json` is stored locally and ignored by git.
- If event modification fails with “No Calendar_ID found,” ensure the original creation message was saved to the database and that your query text matches closely enough to retrieve the right record.
- If you see absolute-path errors, update the credential paths or parameterize via environment variables as shown above.
- If ChromaDB complains about persistence, delete and recreate `eventdb/` locally.

### Roadmap ideas
- Parameterize all hardcoded paths and IDs via environment variables (see examples above).
- Add tests and a lightweight CLI/HTTP interface.
- Batch process multiple unread emails and deduplicate similar requests.
- Improve participant handling (invite attendees by email, etc.).

### License
MIT (or your preferred license).

