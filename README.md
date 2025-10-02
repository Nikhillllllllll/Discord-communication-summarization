# Discord Trades MVP

AI-powered Discord message analyzer that collects trading discussions, extracts insights, and generates intelligent summaries using Google Gemini.

## Overview

This project provides an automated pipeline for:
1. **Ingesting** Discord messages from trading channels
2. **Storing** cleaned data in Google Cloud Storage
3. **Analyzing** discussions with AI to extract sentiment, themes, and insights
4. **Generating** structured summaries in multiple formats

---

## Phase 1: Message Ingestion ✅

### Setup

1. **Create Discord Bot**
   - Go to [Discord Developer Portal](https://discord.com/developers/applications)
   - Create new application and bot
   - Enable **Message Content Intent**
   - Copy bot token

2. **Configure Environment**
   Create a `.env` file in the project root with:
   ```bash
   DISCORD_BOT_TOKEN=your_bot_token_here
   CHANNEL_IDS=123456789,987654321
   SINCE_UTC_DATE=2025-09-20T00:00:00Z
   GCS_BUCKET=your-gcs-bucket-name
   ```

3. **Invite Bot to Server**
   - Bot needs: View Channel + Read Message History permissions
   - Use `scripts/print_invite_url.py` to generate invite link

4. **Install Dependencies**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

5. **Run Ingestion**
   ```bash
   ./scripts/run_local.sh
   # or
   python -m tradesbot.main
   ```

Messages are written locally under `/tmp/ingest/YYYY-MM-DD/channel_id.jsonl`. Upload them to GCS when needed:

```bash
python -c "from tradesbot.uploader import upload_all_days; upload_all_days()"
```

---

## Phase 2: AI-Powered Summarization ✅

### Setup Google Cloud

1. **Enable Vertex AI API**
   ```bash
   gcloud services enable aiplatform.googleapis.com
   ```

2. **Grant Permissions**
   ```bash
   gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
     --member="serviceAccount:YOUR_SA@YOUR_PROJECT.iam.gserviceaccount.com" \
     --role="roles/aiplatform.user"
   ```

3. **Authenticate (for local testing)**
   ```bash
   gcloud auth application-default login
   ```

### Setup Notion (Optional)

1. **Create Notion Integration**
   - Go to https://www.notion.so/my-integrations
   - Click "New integration"
   - Give it a name (e.g., "Discord Trading Bot")
   - Copy the **Internal Integration Token**

2. **Create Database**
   - Create a new Database in Notion
   - Add these properties:
     - `Name` (Title) - Auto-created
     - `Date` (Date)
     - `Total Messages` (Number)
     - `Unique Authors` (Number)
     - `Top Tickers` (Multi-select)
     - `AI Analysis` (Checkbox)
   - Click "..." → "Add connections" → Select your integration
   - Copy the **Database ID** from URL: `notion.so/workspace/DATABASE_ID?v=...`

3. **Set Environment Variables**
   ```bash
   export NOTION_API_TOKEN="secret_abc123..."
   export NOTION_DATABASE_ID="abc123def456..."
   ```

### Run Summarizer

```bash
# Set environment
export GCS_BUCKET="your-bucket-name"
export GCP_PROJECT_ID="your-project-id"

# Run with AI analysis (default)
python -m tradesbot.summarizer_io

# Or specify a date
DAY=2025-10-02 python -m tradesbot.summarizer_io

# Run without AI (basic stats only)
python -m tradesbot.summarizer_io --no-ai

# Save to Notion (in addition to GCS)
python -m tradesbot.summarizer_io --save-to-notion
```

### What the AI Analyzes

- **Sentiment Analysis**: Bullish/Bearish/Neutral per ticker
- **Key Themes**: Earnings plays, technical setups, market concerns
- **Community Conviction**: High/Medium/Low confidence levels
- **Risk Assessment**: Potential downside factors
- **Notable Insights**: Specific trade ideas and catalysts
- **Actionable Watchlist**: Top tickers to monitor

### Output Files

**GCS Storage** - Summaries saved to `gs://your-bucket/summaries/YYYY-MM-DD.*`:
- `.json` - Structured data with basic stats + AI insights
- `.md` - Markdown formatted for easy reading
- `.txt` - Plain text summary

**Notion Database** (optional with `--save-to-notion`):
- Creates a new page in your database with rich formatting
- Properties: Date, Total Messages, Authors, Top Tickers, AI Analysis flag
- Organized sections: Overview, Watchlist, Ticker Analysis, Themes, Insights
- Filterable and searchable

---

## Example Output

```
======================================================================
DISCORD TRADING SUMMARY - 2025-10-02
======================================================================

EXECUTIVE SUMMARY
----------------------------------------------------------------------
Strong bullish sentiment on $NVDA driven by datacenter revenue growth
and backlogged orders. Multiple traders debating $GOOGL's high capex
spending versus long-term cloud potential. Concerns emerging about
$TSLA's margin compression and China weakness.

OVERVIEW
----------------------------------------------------------------------
Total Messages: 50
Unique Authors: 10
Channels: 2
Time Range: 2025-10-02T08:15:23Z to 2025-10-02T17:15:22Z

TOP WATCHLIST
----------------------------------------------------------------------
  • $NVDA
  • $GOOGL
  • $TSLA
  • $MSFT
  • $PLTR

TICKER ANALYSIS
----------------------------------------------------------------------

  $NVDA - 8 mentions | BULLISH | Conviction: HIGH
    Data center revenue grew 427% YoY with strong moat via CUDA ecosystem
    B100 orders backlogged through 2026 indicating sustained demand
    Competition from hyperscaler custom chips poses margin risk

  $GOOGL - 7 mentions | MIXED | Conviction: MEDIUM
    Trading at attractive 16x forward P/E with 25% cloud growth
    Concerns about $50B+ capex spending on data centers
...
```

---

## Cost Analysis

### Storage (GCS)
- Raw JSONL: ~50 MB/day → ~1.5 GB/month ≈ $0.03 (GCS Standard at ~$0.020/GB-month)
- Summaries: ~1 MB/day → ~0.03 GB/month ≈ $0.001
- **Monthly storage total**: ≈ **$0.03**

### AI Analysis (Gemini-2.0-Flash-001)
- Pricing (us-central1, Oct 2025): $0.15 per 1M input tokens, $0.60 per 1M output tokens
- Typical run (~5K input + 1K output tokens): ≈ $0.00135 per summary (0.00075 input + 0.0006 output)
- Daily run: ≈ $0.00135
- **Monthly AI total** (30 runs): ≈ **$0.04**

**Estimated Monthly Cost: ~$0.07** (light usage)

---

## Deployment

### Deploy as Cloud Run Job

```bash
# Build container
gcloud builds submit --tag gcr.io/YOUR_PROJECT/discord-trades-mvp

# Deploy ingestion job
gcloud run jobs deploy discord-ingestion \
  --region us-central1 \
  --image gcr.io/YOUR_PROJECT/discord-trades-mvp \
  --set-env-vars="DISCORD_BOT_TOKEN=..." \
  --set-secrets="DISCORD_BOT_TOKEN=discord-token:latest"

# Deploy summarizer job
gcloud run jobs deploy discord-summarizer \
  --region us-central1 \
  --image gcr.io/YOUR_PROJECT/discord-trades-mvp \
  --set-env-vars="GCS_BUCKET=...,GCP_PROJECT_ID=..." \
  --command="python,-m,tradesbot.summarizer_io"
```

### Schedule Daily Execution

```bash
# Schedule ingestion (2 AM daily)
gcloud scheduler jobs create http ingest-discord-daily \
  --schedule="0 2 * * *" \
  --uri="https://..." \
  --http-method=POST

# Schedule summarizer (3 AM daily, after ingestion)
gcloud scheduler jobs create http summarize-discord-daily \
  --schedule="0 3 * * *" \
  --uri="https://..." \
  --http-method=POST
```

---

## Project Structure

```
discord-trades-mvp/
├── src/
│   └── tradesbot/
│       ├── __init__.py
│       ├── config.py            # Environment + settings loader
│       ├── discord_client.py    # Discord ingestion client
│       ├── gemini_analyzer.py   # Gemini prompt + analysis helpers
│       ├── logging_config.py    # Structured logging setup
│       ├── main.py              # Ingestion entry point
│       ├── notion_writer.py     # Notion database integration
│       ├── storage.py           # Local JSONL writer
│       ├── summarizer_io.py     # Summarizer workflow
│       └── uploader.py          # Pushes /tmp/ingest to GCS
├── scripts/
│   ├── print_invite_url.py      # Generate OAuth invite link
│   
├── requirements.txt             # Python dependencies
├── pyproject.toml               # Tooling configuration
├── Dockerfile                   # Container definition
└── README.md                    # Project docs
```

---

## Environment Variables

### Ingestion
```bash
DISCORD_BOT_TOKEN=your_token        # Bot authentication
CHANNEL_IDS=123,456,789             # Channels to monitor
SINCE_UTC_DATE=2025-09-20T00:00:00Z # Start date for history
GCS_BUCKET=your-bucket              # Storage bucket
PRINT_AUTHORS=true                  # Show author names in logs
```

### Summarization
```bash
GCS_BUCKET=your-bucket              # Storage bucket
GCP_PROJECT_ID=your-project-id      # GCP project
GCP_REGION=us-central1              # Vertex AI region (optional)
DAY=2025-10-02                      # Date to summarize (optional)
NOTION_API_TOKEN=secret_abc123...   # Notion integration token (optional)
NOTION_DATABASE_ID=abc123def456...  # Notion database ID (optional)
```

---

## Troubleshooting

### Ingestion Issues

**"Bot not in server"**
- Generate invite URL: `python scripts/print_invite_url.py CLIENT_ID`
- Ensure Message Content intent is enabled

**"Permission denied"**
- Bot needs: View Channel + Read Message History
- Check channel-specific permissions

### Summarization Issues

**"No module named 'vertexai'"**
```bash
pip install google-cloud-aiplatform
```

**"Vertex AI API not enabled"**
```bash
gcloud services enable aiplatform.googleapis.com
```

**"Permission denied" (GCS or Vertex AI)**
```bash
gcloud auth application-default login
```

**"Model not found"**
- Ensure Vertex AI API is enabled
- Verify service account has `aiplatform.user` role

---

## Roadmap

- ✅ Discord message ingestion
- ✅ GCS storage with JSONL format
- ✅ AI-powered summarization with Gemini
- ✅ Multi-format output (JSON, Markdown, TXT)
- 🔄 Automatic cleanup of raw files (optional)
- 🔄 Weekly rollup summaries
- 🔄 Notion integration for viewing
- 🔄 Slack/Email notifications
- 🔄 Custom watchlist alerts

---

## Contributing

This is a personal project. Feel free to fork and adapt for your needs.

## License

MIT