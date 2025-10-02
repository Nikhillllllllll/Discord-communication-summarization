# src/tradesbot/summarizer_io.py
"""
Read JSONL files from GCS, analyze with AI, and save summaries back to GCS.
"""
from __future__ import annotations
import json
import logging
import re
from collections import defaultdict
from datetime import datetime
from typing import Any

from google.cloud import storage

log = logging.getLogger(__name__)

# Regex to find stock tickers like $AAPL, $GOOGL, etc.
TICKER_PATTERN = re.compile(r'\$([A-Z]{1,5})\b')


def list_available_dates(bucket_name: str) -> list[str]:
    """
    List all dates that have data in the GCS bucket.
    
    Returns:
        Sorted list of date strings (YYYY-MM-DD)
    """
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    
    dates = set()
    # List all blobs and extract date prefixes
    for blob in bucket.list_blobs():
        # Expecting format: 2025-09-20/channel_id.jsonl
        if '/' in blob.name and blob.name.endswith('.jsonl'):
            date_part = blob.name.split('/')[0]
            # Validate it looks like a date
            if re.match(r'\d{4}-\d{2}-\d{2}', date_part):
                dates.add(date_part)
    
    return sorted(dates)


def load_day_messages(bucket_name: str, date: str) -> list[dict[str, Any]]:
    """
    Load all messages for a specific date from GCS.
    
    Args:
        bucket_name: GCS bucket name
        date: Date string (YYYY-MM-DD)
        
    Returns:
        List of message dictionaries
    """
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    
    # Find all JSONL files for this date
    prefix = f"{date}/"
    blobs = list(bucket.list_blobs(prefix=prefix))
    jsonl_files = [b for b in blobs if b.name.endswith('.jsonl')]
    
    if not jsonl_files:
        log.warning(f"No JSONL files found for date {date}")
        return []
    
    log.info(f"Found {len(jsonl_files)} JSONL files for {date}")
    
    messages = []
    for blob in jsonl_files:
        content = blob.download_as_text()
        for line in content.strip().split('\n'):
            if line:
                try:
                    msg = json.loads(line)
                    messages.append(msg)
                except json.JSONDecodeError as e:
                    log.warning(f"Failed to parse line in {blob.name}: {e}")
    
    log.info(f"Loaded {len(messages)} messages for {date}")
    return messages


def extract_tickers(text: str) -> list[str]:
    """
    Extract stock tickers from text (e.g., $AAPL, $GOOGL).
    
    Returns:
        List of ticker symbols (without $)
    """
    return TICKER_PATTERN.findall(text)


def analyze_messages(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Analyze messages and extract key statistics.
    
    Returns:
        Dictionary with analysis results
    """
    if not messages:
        return {
            'total_messages': 0,
            'channels': {},
            'top_tickers': {},
            'unique_authors': 0,
            'date_range': None
        }
    
    # Collect stats
    ticker_counts = defaultdict(int)
    channel_stats = defaultdict(lambda: {
        'messages': 0,
        'authors': set(),
        'tickers': defaultdict(int)
    })
    all_authors = set()
    timestamps = []
    
    for msg in messages:
        content = msg.get('content', '')
        channel_id = msg.get('channel_id', 'unknown')
        channel_name = msg.get('channel_name', 'unknown')
        author = msg.get('author', 'unknown')
        ts = msg.get('ts')
        
        # Count messages per channel
        channel_key = f"{channel_name} ({channel_id})"
        channel_stats[channel_key]['messages'] += 1
        channel_stats[channel_key]['authors'].add(author)
        
        # Extract tickers
        tickers = extract_tickers(content)
        for ticker in tickers:
            ticker_counts[ticker] += 1
            channel_stats[channel_key]['tickers'][ticker] += 1
        
        # Track authors
        all_authors.add(author)
        
        # Track timestamps
        if ts:
            timestamps.append(ts)
    
    # Sort tickers by count
    top_tickers = dict(sorted(ticker_counts.items(), key=lambda x: x[1], reverse=True))
    
    # Convert channel stats to serializable format
    channels_summary = {}
    for channel, stats in channel_stats.items():
        channels_summary[channel] = {
            'messages': stats['messages'],
            'unique_authors': len(stats['authors']),
            'top_tickers': dict(sorted(stats['tickers'].items(), key=lambda x: x[1], reverse=True)[:10])
        }
    
    # Date range
    date_range = None
    if timestamps:
        date_range = {
            'start': min(timestamps),
            'end': max(timestamps)
        }
    
    return {
        'total_messages': len(messages),
        'channels': channels_summary,
        'top_tickers': top_tickers,
        'unique_authors': len(all_authors),
        'date_range': date_range
    }


def generate_summary_text(analysis: dict[str, Any], date: str) -> str:
    """
    Generate a human-readable text summary from analysis results.
    
    Returns:
        Formatted summary string
    """
    lines = []
    lines.append("=" * 60)
    lines.append(f"DISCORD TRADING SUMMARY - {date}")
    lines.append("=" * 60)
    lines.append("")
    
    # Overview
    lines.append(f"Total Messages: {analysis['total_messages']:,}")
    lines.append(f"Unique Authors: {analysis['unique_authors']}")
    lines.append(f"Channels: {len(analysis['channels'])}")
    
    if analysis['date_range']:
        lines.append(f"Time Range: {analysis['date_range']['start']} to {analysis['date_range']['end']}")
    
    lines.append("")
    
    # Top tickers
    if analysis['top_tickers']:
        lines.append("TOP MENTIONED TICKERS:")
        lines.append("-" * 60)
        for i, (ticker, count) in enumerate(list(analysis['top_tickers'].items())[:10], 1):
            lines.append(f"  {i:2}. ${ticker:6} - {count:3} mentions")
        lines.append("")
    
    # Channel breakdown
    if analysis['channels']:
        lines.append("CHANNEL BREAKDOWN:")
        lines.append("-" * 60)
        for channel, stats in analysis['channels'].items():
            lines.append(f"\nCHANNEL: {channel}")
            lines.append(f"   Messages: {stats['messages']:,}")
            lines.append(f"   Authors: {stats['unique_authors']}")
            if stats['top_tickers']:
                top_3 = list(stats['top_tickers'].items())[:3]
                ticker_str = ", ".join([f"${t} ({c})" for t, c in top_3])
                lines.append(f"   Top Tickers: {ticker_str}")
    
    lines.append("")
    lines.append("=" * 60)
    
    return "\n".join(lines)


def generate_markdown_summary(analysis: dict[str, Any], date: str) -> str:
    """
    Generate a Markdown-formatted summary.
    
    Returns:
        Markdown string
    """
    md = [f"# Discord Trading Summary - {date}\n"]
    
    # Overview section
    md.append("## Overview\n")
    md.append(f"- **Total Messages**: {analysis['total_messages']:,}")
    md.append(f"- **Unique Authors**: {analysis['unique_authors']}")
    md.append(f"- **Channels Monitored**: {len(analysis['channels'])}")
    
    if analysis['date_range']:
        md.append(f"- **Time Range**: {analysis['date_range']['start']} to {analysis['date_range']['end']}")
    
    md.append("")
    
    # Top tickers section
    if analysis['top_tickers']:
        md.append("## Top Mentioned Tickers\n")
        for i, (ticker, count) in enumerate(list(analysis['top_tickers'].items())[:10], 1):
            md.append(f"{i}. **${ticker}** - {count} mentions")
        md.append("")
    
    # Channel breakdown section
    if analysis['channels']:
        md.append("## Channel Activity\n")
        for channel, stats in analysis['channels'].items():
            md.append(f"### {channel}\n")
            md.append(f"- **Messages**: {stats['messages']:,}")
            md.append(f"- **Unique Authors**: {stats['unique_authors']}")
            
            if stats['top_tickers']:
                md.append("- **Top Tickers**:")
                for ticker, count in list(stats['top_tickers'].items())[:5]:
                    md.append(f"  - ${ticker}: {count} mentions")
            md.append("")
    
    # Footer
    md.append("---")
    md.append(f"*Generated at {datetime.utcnow().isoformat()}Z*")
    
    return "\n".join(md)


def save_summary_to_gcs(
    bucket_name: str,
    date: str,
    analysis: dict[str, Any],
    ai_analysis: dict[str, Any] | None = None
) -> dict[str, str]:
    """
    Save summary in multiple formats to GCS.
    
    Args:
        bucket_name: GCS bucket name
        date: Date string (YYYY-MM-DD)
        analysis: Basic analysis results dictionary
        ai_analysis: Optional AI-generated analysis
        
    Returns:
        Dictionary with GCS URLs for each saved file
    """
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    
    # Add metadata to JSON
    json_data = {
        'date': date,
        'generated_at': datetime.utcnow().isoformat() + 'Z',
        'basic_stats': analysis,
        'ai_insights': ai_analysis or {}
    }
    
    urls = {}
    
    # Save JSON
    json_blob = bucket.blob(f"summaries/{date}.json")
    json_blob.upload_from_string(
        json.dumps(json_data, indent=2, ensure_ascii=False),
        content_type='application/json'
    )
    urls['json'] = f"gs://{bucket_name}/summaries/{date}.json"
    log.info(f"Saved JSON summary: {urls['json']}")
    
    # Use enhanced summaries if AI analysis available
    if ai_analysis:
        from tradesbot.gemini_analyzer import generate_enhanced_markdown, generate_enhanced_summary_text
        md_content = generate_enhanced_markdown(analysis, ai_analysis, date)
        txt_content = generate_enhanced_summary_text(analysis, ai_analysis, date)
    else:
        md_content = generate_markdown_summary(analysis, date)
        txt_content = generate_summary_text(analysis, date)
    
    # Save Markdown
    md_blob = bucket.blob(f"summaries/{date}.md")
    md_blob.upload_from_string(md_content, content_type='text/markdown')
    urls['markdown'] = f"gs://{bucket_name}/summaries/{date}.md"
    log.info(f"Saved Markdown summary: {urls['markdown']}")
    
    # Save plain text
    txt_blob = bucket.blob(f"summaries/{date}.txt")
    txt_blob.upload_from_string(txt_content, content_type='text/plain')
    urls['text'] = f"gs://{bucket_name}/summaries/{date}.txt"
    log.info(f"Saved text summary: {urls['text']}")
    
    return urls


def process_and_save(bucket_name: str, date: str, use_ai: bool = True) -> bool:
    """
    Complete workflow: load messages, analyze, and save summaries.
    
    Args:
        bucket_name: GCS bucket name
        date: Date string (YYYY-MM-DD)
        use_ai: Whether to use Gemini AI for enhanced analysis
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Load messages
        log.info(f"Loading messages for {date}...")
        messages = load_day_messages(bucket_name, date)
        
        if not messages:
            log.warning(f"No messages found for {date}")
            return False
        
        # Basic analysis
        log.info(f"Analyzing {len(messages)} messages...")
        analysis = analyze_messages(messages)
        
        # AI analysis (if enabled)
        ai_analysis = None
        if use_ai:
            try:
                from tradesbot.gemini_analyzer import analyze_with_gemini, generate_enhanced_summary_text
                log.info("Running AI analysis with Gemini...")
                ai_analysis = analyze_with_gemini(messages, analysis)
                
                # Display enhanced summary
                summary_text = generate_enhanced_summary_text(analysis, ai_analysis, date)
                print("\n" + summary_text + "\n")
            except Exception as e:
                log.warning(f"AI analysis failed, falling back to basic summary: {e}")
                summary_text = generate_summary_text(analysis, date)
                print("\n" + summary_text + "\n")
        else:
            # Display basic summary
            summary_text = generate_summary_text(analysis, date)
            print("\n" + summary_text + "\n")
        
        # Save to GCS
        log.info(f"Saving summaries to GCS...")
        urls = save_summary_to_gcs(bucket_name, date, analysis, ai_analysis)
        
        print("Summaries saved to:")
        for format_type, url in urls.items():
            print(f"   {format_type.upper()}: {url}")
        
        if ai_analysis:
            print("\nAI-enhanced summary generated with Gemini")
        
        return True
        
    except Exception as e:
        log.error(f"Error processing {date}: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    # CLI interface
    import os
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)s | %(name)s | %(message)s'
    )
    
    bucket_name = os.getenv("GCS_BUCKET")
    if not bucket_name:
        print("Error: GCS_BUCKET environment variable not set")
        print("Usage: export GCS_BUCKET='your-bucket-name' && python -m tradesbot.summarizer_io [DATE] [--no-ai]")
        sys.exit(1)
    
    # Check for --no-ai flag
    use_ai = "--no-ai" not in sys.argv
    
    # Get date from command line or environment, or use most recent
    date_args = [arg for arg in sys.argv[1:] if not arg.startswith("--")]
    if date_args:
        date = date_args[0]
    else:
        date = os.getenv("DAY")
        if not date:
            # Find most recent date
            dates = list_available_dates(bucket_name)
            if not dates:
                print("No data found in bucket")
                sys.exit(1)
            date = dates[-1]
            print(f"No date specified, using most recent: {date}")
    
    if use_ai:
        print("AI analysis enabled (Gemini)")
    else:
        print("Basic analysis only (no AI)")
    
    # Process and save
    success = process_and_save(bucket_name, date, use_ai=use_ai)
    sys.exit(0 if success else 1)