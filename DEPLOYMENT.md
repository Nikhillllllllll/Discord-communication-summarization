# Deployment Guide - Google Cloud Automation

This guide shows how to automate the Discord trading summarization pipeline on Google Cloud.

## Architecture

```
Cloud Scheduler (2 AM)
    ↓
Discord Ingestion Job (5-10 min)
    ↓
GCS Storage (JSONL files)
    ↓
Cloud Scheduler (2:30 AM)
    ↓
Summarizer Job (2-3 min)
    ↓
Outputs:
  - GCS: JSON/Markdown/TXT summaries
  - Notion: Database page
```

**Why This Approach?**
- ✅ No 24/7 service needed (saves ~$15/month)
- ✅ Total runtime: ~15 minutes/day
- ✅ Discord bot fetches all messages since last run
- ✅ Same container for both jobs
- ✅ Total cost: ~$0.10/month

---

## Prerequisites

1. **GCP Project** with billing enabled
2. **Service Account** with proper permissions
3. **GCS Bucket** for storing summaries
4. **Notion Integration** (optional)

---

## Step 1: Build and Push Container

```bash
# Set your project ID
export PROJECT_ID="discord-message-summarization"
export REGION="us-central1"

# Build the container
gcloud builds submit --tag gcr.io/$PROJECT_ID/discord-trades-mvp

# Verify image
gcloud container images list --repository=gcr.io/$PROJECT_ID
```

---

## Step 2: Create Service Account & Grant Permissions

```bash
# Create service account (if not exists)
gcloud iam service-accounts create discord-summarizer \
    --display-name="Discord Summarizer Bot"

export SA_EMAIL="discord-summarizer@${PROJECT_ID}.iam.gserviceaccount.com"

# Grant permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/storage.objectAdmin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/aiplatform.user"
```

---

## Step 3: Create Secrets

```bash
# Create Discord bot token secret
echo -n "your_discord_bot_token" | gcloud secrets create discord-bot-token \
    --data-file=- \
    --replication-policy="automatic"

# Create Notion API token secret
echo -n "secret_your_notion_token" | gcloud secrets create notion-api-token \
    --data-file=- \
    --replication-policy="automatic"

# Create Notion database ID secret
echo -n "your_database_id" | gcloud secrets create notion-database-id \
    --data-file=- \
    --replication-policy="automatic"

# Grant service account access to secrets
gcloud secrets add-iam-policy-binding discord-bot-token \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding notion-api-token \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding notion-database-id \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/secretmanager.secretAccessor"
```

---

## Step 4: Deploy Cloud Run Jobs

### Job 1: Discord Ingestion

```bash
gcloud run jobs create discord-ingestion \
    --region=$REGION \
    --image=gcr.io/$PROJECT_ID/discord-trades-mvp \
    --service-account=$SA_EMAIL \
    --set-env-vars="GCS_BUCKET=discord-trades-ingest-${PROJECT_ID},CHANNEL_IDS=your_channel_ids" \
    --set-secrets="DISCORD_BOT_TOKEN=discord-bot-token:latest" \
    --task-timeout=15m \
    --max-retries=2 \
    --command="python" \
    --args="-m,tradesbot.main"
```

**Note:** Replace `your_channel_ids` with your Discord channel IDs (comma-separated).

### Job 2: Summarizer

```bash
gcloud run jobs create discord-summarizer \
    --region=$REGION \
    --image=gcr.io/$PROJECT_ID/discord-trades-mvp \
    --service-account=$SA_EMAIL \
    --set-env-vars="GCS_BUCKET=discord-trades-ingest-${PROJECT_ID},GCP_PROJECT_ID=${PROJECT_ID},GCP_REGION=${REGION}" \
    --set-secrets="NOTION_API_TOKEN=notion-api-token:latest,NOTION_DATABASE_ID=notion-database-id:latest" \
    --task-timeout=10m \
    --max-retries=2 \
    --command="python" \
    --args="-m,tradesbot.summarizer_io,--save-to-notion"
```

### Test Both Jobs Manually

```bash
# Test ingestion
gcloud run jobs execute discord-ingestion --region=$REGION

# Wait for ingestion to complete, then test summarizer
gcloud run jobs execute discord-summarizer --region=$REGION

# Check logs
gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=discord-ingestion" \
    --limit=50 \
    --format="table(timestamp,textPayload)"

gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=discord-summarizer" \
    --limit=50 \
    --format="table(timestamp,textPayload)"
```

---

## Step 5: Schedule Daily Execution

```bash
# Schedule 1: Ingestion runs at 2:00 AM daily
gcloud scheduler jobs create http ingest-discord-daily \
    --location=$REGION \
    --schedule="0 2 * * *" \
    --time-zone="America/New_York" \
    --uri="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/discord-ingestion:run" \
    --http-method=POST \
    --oauth-service-account-email=$SA_EMAIL \
    --description="Daily Discord message ingestion"

# Schedule 2: Summarizer runs at 2:30 AM (30 min after ingestion)
gcloud scheduler jobs create http summarize-discord-daily \
    --location=$REGION \
    --schedule="30 2 * * *" \
    --time-zone="America/New_York" \
    --uri="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/discord-summarizer:run" \
    --http-method=POST \
    --oauth-service-account-email=$SA_EMAIL \
    --description="Daily Discord trading summary generation"

# Test both schedulers
gcloud scheduler jobs run ingest-discord-daily --location=$REGION
sleep 60  # Wait for ingestion to complete
gcloud scheduler jobs run summarize-discord-daily --location=$REGION
```

**Note:** The 30-minute gap ensures ingestion completes before summarization starts.

---

## Step 6: Monitor & Logs

### View Job Executions

```bash
# List recent executions
gcloud run jobs executions list \
    --job=discord-summarizer \
    --region=$REGION \
    --limit=10

# View logs for a specific execution
gcloud logging read "resource.type=cloud_run_job" \
    --limit=100 \
    --format=json
```

### Set Up Alerts (Optional)

```bash
# Create alert for job failures
gcloud alpha monitoring policies create \
    --notification-channels=YOUR_CHANNEL_ID \
    --display-name="Discord Summarizer Failed" \
    --condition-display-name="Job execution failed" \
    --condition-threshold-value=1 \
    --condition-threshold-duration=60s
```

---

## Configuration Options

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GCS_BUCKET` | Yes | GCS bucket name for summaries |
| `GCP_PROJECT_ID` | Yes | Your GCP project ID |
| `GCP_REGION` | No | Vertex AI region (default: us-central1) |
| `NOTION_API_TOKEN` | No | Notion integration token (for `--save-to-notion`) |
| `NOTION_DATABASE_ID` | No | Notion database ID (for `--save-to-notion`) |
| `DAY` | No | Specific date to summarize (YYYY-MM-DD), defaults to most recent |

### Command Flags

```bash
# Run without AI (basic stats only)
--args="-m,tradesbot.summarizer_io,--no-ai"

# Run with AI but without Notion
--args="-m,tradesbot.summarizer_io"

# Run with AI and Notion
--args="-m,tradesbot.summarizer_io,--save-to-notion"

# Summarize specific date
--set-env-vars="DAY=2025-10-03"
```

---

## Cost Optimization

### Reduce Costs

1. **Use smaller machine type:**
   ```bash
   gcloud run jobs update discord-summarizer \
       --region=$REGION \
       --cpu=1 \
       --memory=512Mi
   ```

2. **Run less frequently:**
   ```bash
   # Weekly instead of daily
   --schedule="0 3 * * 1"  # Every Monday at 3 AM
   ```

3. **Skip Notion integration** if not needed:
   ```bash
   --args="-m,tradesbot.summarizer_io"  # No --save-to-notion
   ```

### Expected Costs

- **Cloud Run Jobs**: 
  - Ingestion: ~10 min/day × 30 days = $0.01/month
  - Summarizer: ~3 min/day × 30 days = $0.003/month
- **Cloud Scheduler**: $0.10/month × 2 jobs = $0.20/month
- **Vertex AI (Gemini)**: ~$0.04/month (30 runs)
- **GCS Storage**: ~$0.03/month
- **Total**: ~$0.28/month

**Compare to 24/7 Service:** Running Discord bot 24/7 would cost ~$15/month. This approach saves **98%**!

---

## Troubleshooting

### Job Fails with "Permission Denied"

```bash
# Verify service account has correct roles
gcloud projects get-iam-policy $PROJECT_ID \
    --flatten="bindings[].members" \
    --filter="bindings.members:${SA_EMAIL}"
```

### Secrets Not Found

```bash
# List secrets
gcloud secrets list

# Verify IAM binding
gcloud secrets get-iam-policy notion-api-token
```

### Job Times Out

```bash
# Increase timeout
gcloud run jobs update discord-summarizer \
    --region=$REGION \
    --task-timeout=20m
```

### View Detailed Logs

```bash
gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=discord-summarizer" \
    --limit=200 \
    --format=json > job-logs.json
```

---

## Update Deployment

When you make code changes:

```bash
# 1. Rebuild image
gcloud builds submit --tag gcr.io/$PROJECT_ID/discord-trades-mvp

# 2. Update job to use new image
gcloud run jobs update discord-summarizer \
    --region=$REGION \
    --image=gcr.io/$PROJECT_ID/discord-trades-mvp

# 3. Test manually
gcloud run jobs execute discord-summarizer --region=$REGION
```

---

## Clean Up

To remove all resources:

```bash
# Delete scheduler
gcloud scheduler jobs delete summarize-discord-daily --location=$REGION

# Delete Cloud Run job
gcloud run jobs delete discord-summarizer --region=$REGION

# Delete secrets
gcloud secrets delete notion-api-token
gcloud secrets delete notion-database-id

# Delete service account
gcloud iam service-accounts delete $SA_EMAIL
```
