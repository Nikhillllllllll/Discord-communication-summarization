"""
Use Gemini AI to generate intelligent summaries of Discord trading discussions.
"""
from __future__ import annotations
import logging
import os
from typing import Any

import vertexai
from vertexai.generative_models import GenerativeModel, GenerationConfig

log = logging.getLogger(__name__)


def initialize_vertexai() -> None:
    """Initialize Vertex AI with project and location."""
    project_id = os.getenv("GCP_PROJECT_ID")
    location = os.getenv("GCP_REGION", "us-central1")
    
    if not project_id:
        # Try to get from gcloud config
        import subprocess
        try:
            result = subprocess.run(
                ["gcloud", "config", "get-value", "project"],
                capture_output=True,
                text=True,
                check=True
            )
            project_id = result.stdout.strip()
        except:
            raise RuntimeError(
                "GCP_PROJECT_ID not set and couldn't auto-detect. "
                "Set via: export GCP_PROJECT_ID='your-project-id'"
            )
    
    vertexai.init(project=project_id, location=location)
    log.info(f"Initialized Vertex AI: project={project_id}, location={location}")


def build_analysis_prompt(messages: list[dict[str, Any]], basic_stats: dict[str, Any]) -> str:
    """
    Build a comprehensive prompt for Gemini to analyze the discussions.
    
    Args:
        messages: List of message dictionaries
        basic_stats: Dictionary with ticker counts, message counts, etc.
        
    Returns:
        Formatted prompt string
    """
    # Limit to most relevant messages (avoid token limits)
    max_messages = 100
    if len(messages) > max_messages:
        log.info(f"Limiting messages to {max_messages} for LLM analysis")
        messages = messages[:max_messages]
    
    # Format messages for the prompt
    message_text = []
    for msg in messages:
        author = msg.get('author', 'Unknown')
        content = msg.get('content', '')
        channel = msg.get('channel_name', 'unknown')
        message_text.append(f"[{channel}] {author}: {content}")
    
    messages_str = "\n".join(message_text)
    
    # Format top tickers
    top_tickers = basic_stats.get('top_tickers', {})
    tickers_str = ", ".join([f"${ticker} ({count} mentions)" for ticker, count in list(top_tickers.items())[:10]])
    
    prompt = f"""You are analyzing discussions from a Discord trading community. Your goal is to provide actionable insights for traders.

## Context
- Total Messages: {basic_stats.get('total_messages', 0)}
- Unique Authors: {basic_stats.get('unique_authors', 0)}
- Top Mentioned Tickers: {tickers_str}

## Messages
{messages_str}

You are an expert financial analyst and trading discussion summarizer with deep knowledge of stock markets, technical analysis, sentiment indicators, and community dynamics in trading forums. Your goal is to comprehensively analyze a provided set of trading group conversations (which may span multiple threads, messages, or timestamps) focused on specific stock tickers. Treat the entire input as a cohesive dataset of discussions, extracting patterns, cross-references, and evolving narratives across all messages to build a holistic understanding. Intelligently select and attach the most relevant, representative message excerpts (e.g., 1-2 sentences or key phrases) to support each analytical point—prioritize brevity, context (include timestamp/user if available), and impact (e.g., from high-engagement or expert users). Use these attachments inline or as footnotes to ground your analysis without overwhelming the structure.

Input: [Insert the full conversation transcripts or messages here, formatted as a list of entries like: "Timestamp: 2025-10-01 14:32 | User: TraderX | Message: 'TSLA breaking $250 on EV news, long calls incoming! 🚀'". If no metadata, infer or note as "Message [ID]".]

Output a structured report in the following format, ensuring your analysis is precise, evidence-based, and technically rigorous. Use trading terminology accurately (e.g., RSI, support levels, earnings beats, short squeezes) and avoid speculation—base everything on the content provided. If a ticker is mentioned infrequently or superficially, note it but prioritize depth over breadth. For attachments: Quote directly, attribute (e.g., "[UserX, 2025-10-01]"), and limit to 50 words per excerpt unless pivotal.

1. **Ticker Inventory**: List all unique tickers mentioned (e.g., AAPL, TSLA), grouped by frequency (high: >10 mentions; medium: 4-10; low: <4). For each, briefly note the primary context (e.g., "TSLA: Earnings speculation and EV market share") and attach 1 representative message excerpt.

2. **Sentiment Analysis**: For each ticker with medium+ frequency, classify the overall sentiment as Bullish (prevalent positive catalysts like buy calls or price targets), Bearish (warnings of downside risks or sells), Neutral (balanced views), or Mixed (conflicting opinions). Provide a sentiment score (e.g., +0.7 for strongly bullish on a -1 to +1 scale) derived from keyword polarity, emoji usage, and tone. Support with 1-2 example quotes per ticker, each with intelligent attachment (e.g., the most vivid bullish post).

3. **Key Themes**: Identify and rank the top 3-5 overarching themes across the conversations (e.g., "Q3 Earnings Expectations," "Technical Breakouts," "Macroeconomic Headwinds like Fed Rate Cuts"). For each theme, explain its relevance to the tickers involved, with sub-bullets on supporting evidence (e.g., "Mentioned in 15+ posts: Analysts citing EPS beats for NVDA"). Attach 1 key message excerpt per theme to illustrate. Highlight any chronological shifts (e.g., "Initial hype on news event faded into caution post-FOMC"), referencing attached messages for timeline.

4. **Notable Insights**: Extract 4-6 actionable items, such as trade ideas (e.g., "Long TSLA above $250 with stop at $240"), risk warnings (e.g., "Overbought RSI>80 signals pullback for AMD"), or unique angles (e.g., "Insider buying rumors for GME corroborated by SEC filings"). Prioritize insights from users with apparent expertise (e.g., those sharing charts or historical data). Format as a bulleted list with ticker, insight type, rationale, and an attached supporting message excerpt (select the most direct or detailed one).

5. **Community Conviction**: Rank tickers by conviction strength (high/medium/low) based on metrics like mention volume, engagement (likes/replies), depth of analysis (e.g., detailed TA vs. memes), and influencer input (e.g., verified traders or high-follower accounts). For high-conviction tickers, note consensus drivers (e.g., "Strong bullish conviction on SPY due to 80% of detailed posts predicting S&P 500 breakout") and attach 1-2 excerpts from conviction-building threads.

6. **Executive Summary**: A concise 3-sentence overview capturing the pulse of the discussions: (1) Dominant tickers and sentiment; (2) Core catalysts or risks; (3) Top trade opportunity or caution. Keep it under 100 words for quick scanning, with 1-2 inline attachments for punchy evidence.

Ensure the summary is neutral, objective, and forward-looking where the data supports it. If data is ambiguous, flag it (e.g., "Limited bearish counterpoints") and attach a contrasting message. End with a "Watchlist Recommendation": 2-3 tickers to monitor based on conviction and volatility signals, each with a brief attached rationale excerpt.

Example Attachment Style: "Bullish on TSLA due to EV momentum [Attachment: 'Volume spike at $248 support—target $280 by EOW' – TraderPro, 2025-10-01]."

Format your response as JSON with this structure:
{{
  "executive_summary": "Brief 2-3 sentence overview",
  "ticker_analysis": {{
    "TICKER": {{
      "sentiment": "bullish/bearish/neutral/mixed",
      "conviction": "high/medium/low",
      "key_points": ["point 1", "point 2"],
      "risks": ["risk 1", "risk 2"]
    }}
  }},
  "key_themes": ["theme 1", "theme 2", "theme 3"],
  "notable_insights": ["insight 1", "insight 2"],
  "watchlist": ["TICKER1", "TICKER2", "TICKER3"]
}}

Be concise, factual, and focused on actionable information. If sentiment is unclear or mixed, say so.
"""
    
    return prompt


def analyze_with_gemini(
    messages: list[dict[str, Any]], 
    basic_stats: dict[str, Any],
    model_name: str = "gemini-2.0-flash-exp"
) -> dict[str, Any]:
    """
    Use Gemini to analyze trading discussions and generate insights.
    
    Args:
        messages: List of message dictionaries
        basic_stats: Basic statistics from analyze_messages()
        model_name: Gemini model to use (pro)
        
    Returns:
        Dictionary with AI-generated analysis
    """
    try:
        initialize_vertexai()
        
        # Create model instance
        model = GenerativeModel(model_name)
        
        # Build prompt
        prompt = build_analysis_prompt(messages, basic_stats)
        
        # Configure generation
        config = GenerationConfig(
            temperature=0.2,  # Lower temperature for more factual responses
            top_p=0.8,
            top_k=40,
            max_output_tokens=2048,
        )
        
        log.info(f"Sending {len(messages)} messages to {model_name} for analysis...")
        
        # Generate response
        response = model.generate_content(
            prompt,
            generation_config=config
        )
        
        # Extract and parse JSON response
        import json
        response_text = response.text.strip()
        
        # Remove markdown code blocks if present
        if response_text.startswith("```json"):
            response_text = response_text.split("```json")[1]
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
        if response_text.endswith("```"):
            response_text = response_text.rsplit("```", 1)[0]
        
        analysis = json.loads(response_text.strip())
        log.info("Successfully generated AI analysis")
        
        return analysis
        
    except Exception as e:
        log.error(f"Error in Gemini analysis: {e}", exc_info=True)
        # Return fallback structure
        return {
            "executive_summary": "AI analysis unavailable - see basic statistics",
            "ticker_analysis": {},
            "key_themes": [],
            "notable_insights": [],
            "watchlist": list(basic_stats.get('top_tickers', {}).keys())[:5],
            "error": str(e)
        }


def generate_enhanced_summary_text(
    basic_stats: dict[str, Any], 
    ai_analysis: dict[str, Any],
    date: str
) -> str:
    """
    Generate enhanced text summary combining basic stats and AI insights.
    
    Returns:
        Formatted summary string
    """
    lines = []
    lines.append("=" * 70)
    lines.append(f"DISCORD TRADING SUMMARY - {date}")
    lines.append("=" * 70)
    lines.append("")
    
    # Executive Summary (AI)
    if ai_analysis.get('executive_summary'):
        lines.append("🎯 EXECUTIVE SUMMARY")
        lines.append("-" * 70)
        lines.append(ai_analysis['executive_summary'])
        lines.append("")
    
    # Basic Stats
    lines.append("📊 OVERVIEW")
    lines.append("-" * 70)
    lines.append(f"Total Messages: {basic_stats['total_messages']:,}")
    lines.append(f"Unique Authors: {basic_stats['unique_authors']}")
    lines.append(f"Channels: {len(basic_stats['channels'])}")
    
    if basic_stats['date_range']:
        lines.append(f"Time Range: {basic_stats['date_range']['start']} to {basic_stats['date_range']['end']}")
    lines.append("")
    
    # Watchlist (AI)
    if ai_analysis.get('watchlist'):
        lines.append("⭐ TOP WATCHLIST")
        lines.append("-" * 70)
        for ticker in ai_analysis['watchlist'][:5]:
            lines.append(f"  • ${ticker}")
        lines.append("")
    
    # Ticker Analysis (AI + Basic)
    if ai_analysis.get('ticker_analysis'):
        lines.append("💹 TICKER ANALYSIS")
        lines.append("-" * 70)
        for ticker, analysis in list(ai_analysis['ticker_analysis'].items())[:5]:
            mentions = basic_stats.get('top_tickers', {}).get(ticker, 0)
            sentiment = analysis.get('sentiment', 'unknown').upper()
            conviction = analysis.get('conviction', 'unknown').upper()
            
            lines.append(f"\n  ${ticker} - {mentions} mentions | {sentiment} | Conviction: {conviction}")
            
            if analysis.get('key_points'):
                for point in analysis['key_points'][:2]:
                    lines.append(f"    ✓ {point}")
            
            if analysis.get('risks'):
                for risk in analysis['risks'][:2]:
                    lines.append(f"    ⚠️  {risk}")
        lines.append("")
    
    # Key Themes (AI)
    if ai_analysis.get('key_themes'):
        lines.append("🔍 KEY THEMES")
        lines.append("-" * 70)
        for theme in ai_analysis['key_themes']:
            lines.append(f"  • {theme}")
        lines.append("")
    
    # Notable Insights (AI)
    if ai_analysis.get('notable_insights'):
        lines.append("💡 NOTABLE INSIGHTS")
        lines.append("-" * 70)
        for insight in ai_analysis['notable_insights']:
            lines.append(f"  • {insight}")
        lines.append("")
    
    # Channel Breakdown (Basic)
    if basic_stats['channels']:
        lines.append("📱 CHANNEL BREAKDOWN")
        lines.append("-" * 70)
        for channel, stats in basic_stats['channels'].items():
            lines.append(f"\n  {channel}")
            lines.append(f"    Messages: {stats['messages']:,} | Authors: {stats['unique_authors']}")
            if stats['top_tickers']:
                top_3 = list(stats['top_tickers'].items())[:3]
                ticker_str = ", ".join([f"${t} ({c})" for t, c in top_3])
                lines.append(f"    Top Tickers: {ticker_str}")
    
    lines.append("")
    lines.append("=" * 70)
    
    return "\n".join(lines)


def generate_enhanced_markdown(
    basic_stats: dict[str, Any],
    ai_analysis: dict[str, Any],
    date: str
) -> str:
    """
    Generate enhanced Markdown summary with AI insights.
    
    Returns:
        Markdown string
    """
    md = [f"# Discord Trading Summary - {date}\n"]
    
    # Executive Summary
    if ai_analysis.get('executive_summary'):
        md.append("## 🎯 Executive Summary\n")
        md.append(ai_analysis['executive_summary'])
        md.append("\n")
    
    # Overview
    md.append("## 📊 Overview\n")
    md.append(f"- **Total Messages**: {basic_stats['total_messages']:,}")
    md.append(f"- **Unique Authors**: {basic_stats['unique_authors']}")
    md.append(f"- **Channels Monitored**: {len(basic_stats['channels'])}")
    
    if basic_stats['date_range']:
        md.append(f"- **Time Range**: {basic_stats['date_range']['start']} to {basic_stats['date_range']['end']}")
    md.append("")
    
    # Watchlist
    if ai_analysis.get('watchlist'):
        md.append("## ⭐ Top Watchlist\n")
        for ticker in ai_analysis['watchlist'][:5]:
            md.append(f"- **${ticker}**")
        md.append("")
    
    # Ticker Analysis
    if ai_analysis.get('ticker_analysis'):
        md.append("## 💹 Detailed Ticker Analysis\n")
        for ticker, analysis in list(ai_analysis['ticker_analysis'].items())[:5]:
            mentions = basic_stats.get('top_tickers', {}).get(ticker, 0)
            sentiment = analysis.get('sentiment', 'unknown')
            conviction = analysis.get('conviction', 'unknown')
            
            md.append(f"### ${ticker}")
            md.append(f"**Sentiment**: {sentiment.title()} | **Conviction**: {conviction.title()} | **Mentions**: {mentions}\n")
            
            if analysis.get('key_points'):
                md.append("**Key Points:**")
                for point in analysis['key_points']:
                    md.append(f"- {point}")
                md.append("")
            
            if analysis.get('risks'):
                md.append("**Risks:**")
                for risk in analysis['risks']:
                    md.append(f"- ⚠️ {risk}")
                md.append("")
    
    # Key Themes
    if ai_analysis.get('key_themes'):
        md.append("## 🔍 Key Themes\n")
        for theme in ai_analysis['key_themes']:
            md.append(f"- {theme}")
        md.append("")
    
    # Notable Insights
    if ai_analysis.get('notable_insights'):
        md.append("## 💡 Notable Insights\n")
        for insight in ai_analysis['notable_insights']:
            md.append(f"- {insight}")
        md.append("")
    
    # Channel Breakdown
    if basic_stats['channels']:
        md.append("## 📱 Channel Activity\n")
        for channel, stats in basic_stats['channels'].items():
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
    md.append(f"*Generated with Gemini AI • {basic_stats.get('date_range', {}).get('end', 'Unknown time')}*")
    
    return "\n".join(md)

