"""
Write summaries to Notion database.
"""
from __future__ import annotations
import logging
import os
from typing import Any

from notion_client import Client

log = logging.getLogger(__name__)


def get_notion_client() -> Client:
    """Initialize and return Notion client."""
    token = os.getenv("NOTION_API_TOKEN")
    if not token:
        raise RuntimeError("NOTION_API_TOKEN environment variable not set")
    return Client(auth=token)


def create_summary_page(
    basic_stats: dict[str, Any],
    ai_analysis: dict[str, Any],
    date: str,
    database_id: str | None = None
) -> dict[str, str]:
    """
    Create or update a Notion page in the database with summary content.
    If a page for this date already exists, it will be updated instead of creating a duplicate.
    
    Args:
        basic_stats: Basic statistics from analyze_messages()
        ai_analysis: AI-generated analysis
        date: Date string (YYYY-MM-DD)
        database_id: Notion database ID (or use env var)
        
    Returns:
        Dict with page_id and page_url
    """
    if not database_id:
        database_id = os.getenv("NOTION_DATABASE_ID")
        if not database_id:
            raise RuntimeError("NOTION_DATABASE_ID not set")
    
    try:
        client = get_notion_client()
        
        # Check if a page for this date already exists
        existing_page = _find_existing_page(client, database_id, date)
        
        # Build page properties
        properties = _build_properties(basic_stats, ai_analysis, date)
        
        # Build page content (blocks)
        blocks = _build_content_blocks(basic_stats, ai_analysis, date)
        
        if existing_page:
            # Delete existing page and create a new one (faster than updating all blocks)
            page_id = existing_page["id"]
            log.info(f"Deleting and recreating Notion page for {date}...")
            
            # Delete the old page
            client.pages.update(page_id=page_id, archived=True)
            
            # Create new page
            response = client.pages.create(
                parent={"database_id": database_id},
                properties=properties,
                children=blocks
            )
            
            page_id = response["id"]
            page_url = response["url"]
            log.info(f"Recreated Notion page: {page_url}")
        else:
            # Create new page
            log.info(f"Creating new Notion page for {date}...")
            
            response = client.pages.create(
                parent={"database_id": database_id},
                properties=properties,
                children=blocks
            )
            
            page_id = response["id"]
            page_url = response["url"]
            
            log.info(f"Created Notion page: {page_url}")
        
        return {
            "page_id": page_id,
            "page_url": page_url,
            "date": date
        }
        
    except Exception as e:
        log.error(f"Failed to create/update Notion page: {e}", exc_info=True)
        raise


def _find_existing_page(client: Client, database_id: str, date: str) -> dict[str, Any] | None:
    """
    Search for an existing page with the given date in the database.
    
    Returns:
        Page object if found, None otherwise
    """
    try:
        # Query database for pages with matching date
        response = client.databases.query(
            database_id=database_id,
            filter={
                "property": "Date",
                "date": {
                    "equals": date
                }
            }
        )
        
        results = response.get("results", [])
        if results:
            log.info(f"Found existing page for {date}")
            return results[0]  # Return first match
        
        return None
        
    except Exception as e:
        log.warning(f"Error searching for existing page: {e}")
        return None


def _build_properties(
    basic_stats: dict[str, Any],
    ai_analysis: dict[str, Any],
    date: str
) -> dict[str, Any]:
    """Build Notion page properties."""
    
    # Top tickers for tags
    top_tickers = list(basic_stats.get("top_tickers", {}).keys())[:10]
    
    properties = {
        "Name": {
            "title": [
                {
                    "text": {
                        "content": f"Discord Trading Summary - {date}"
                    }
                }
            ]
        },
        "Date": {
            "date": {
                "start": date
            }
        },
        "Total Messages": {
            "number": basic_stats.get("total_messages", 0)
        },
        "Unique Authors": {
            "number": basic_stats.get("unique_authors", 0)
        },
        "Top Tickers": {
            "multi_select": [{"name": ticker} for ticker in top_tickers[:5]]
        }
    }
    
    # Add AI sentiment if available
    if ai_analysis and ai_analysis.get("executive_summary"):
        properties["AI Analysis"] = {
            "checkbox": True
        }
    
    return properties


def _build_content_blocks(
    basic_stats: dict[str, Any],
    ai_analysis: dict[str, Any],
    date: str
) -> list[dict[str, Any]]:
    """Build Notion content blocks for the page body."""
    
    blocks = []
    
    # Executive Summary (if AI analysis available)
    if ai_analysis and ai_analysis.get("executive_summary"):
        blocks.extend([
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": "Executive Summary"}}]
                }
            },
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": ai_analysis["executive_summary"]}}]
                }
            },
            {
                "object": "block",
                "type": "divider",
                "divider": {}
            }
        ])
    
    # Overview Section
    blocks.append({
        "object": "block",
        "type": "heading_2",
        "heading_2": {
            "rich_text": [{"type": "text", "text": {"content": "Overview"}}]
        }
    })
    
    overview_items = [
        f"Total Messages: {basic_stats['total_messages']:,}",
        f"Unique Authors: {basic_stats['unique_authors']}",
        f"Channels: {len(basic_stats['channels'])}"
    ]
    
    if basic_stats.get('date_range'):
        overview_items.append(
            f"Time Range: {basic_stats['date_range']['start']} to {basic_stats['date_range']['end']}"
        )
    
    for item in overview_items:
        blocks.append({
            "object": "block",
            "type": "bulleted_list_item",
            "bulleted_list_item": {
                "rich_text": [{"type": "text", "text": {"content": item}}]
            }
        })
    
    # Watchlist (if AI analysis available)
    if ai_analysis and ai_analysis.get("watchlist"):
        blocks.extend([
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": "Top Watchlist"}}]
                }
            }
        ])
        
        for ticker in ai_analysis["watchlist"][:5]:
            blocks.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [{"type": "text", "text": {"content": f"${ticker}"}}]
                }
            })
    
    # Ticker Analysis
    if ai_analysis and ai_analysis.get("ticker_analysis"):
        blocks.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"type": "text", "text": {"content": "Ticker Analysis"}}]
            }
        })
        
        for ticker, analysis in list(ai_analysis["ticker_analysis"].items())[:5]:
            mentions = basic_stats.get("top_tickers", {}).get(ticker, 0)
            sentiment = analysis.get("sentiment", "unknown").upper()
            conviction = analysis.get("conviction", "unknown").upper()
            
            # Ticker heading
            blocks.append({
                "object": "block",
                "type": "heading_3",
                "heading_3": {
                    "rich_text": [{"type": "text", "text": {"content": f"${ticker}"}}]
                }
            })
            
            # Ticker stats
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {"type": "text", "text": {"content": f"{mentions} mentions | Sentiment: {sentiment} | Conviction: {conviction}"}}
                    ]
                }
            })
            
            # Key points
            if analysis.get("key_points"):
                blocks.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{
                            "type": "text",
                            "text": {"content": "Key Points:"},
                            "annotations": {"bold": True}
                        }]
                    }
                })
                for point in analysis["key_points"][:3]:
                    blocks.append({
                        "object": "block",
                        "type": "bulleted_list_item",
                        "bulleted_list_item": {
                            "rich_text": [{"type": "text", "text": {"content": point}}]
                        }
                    })
            
            # Risks
            if analysis.get("risks"):
                blocks.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{
                            "type": "text",
                            "text": {"content": "Risks:"},
                            "annotations": {"bold": True}
                        }]
                    }
                })
                for risk in analysis["risks"][:3]:
                    blocks.append({
                        "object": "block",
                        "type": "bulleted_list_item",
                        "bulleted_list_item": {
                            "rich_text": [{"type": "text", "text": {"content": risk}}]
                        }
                    })
    
    # Key Themes
    if ai_analysis and ai_analysis.get("key_themes"):
        blocks.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"type": "text", "text": {"content": "Key Themes"}}]
            }
        })
        
        for theme in ai_analysis["key_themes"]:
            blocks.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [{"type": "text", "text": {"content": theme}}]
                }
            })
    
    # Notable Insights
    if ai_analysis and ai_analysis.get("notable_insights"):
        blocks.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"type": "text", "text": {"content": "Notable Insights"}}]
            }
        })
        
        for insight in ai_analysis["notable_insights"]:
            # Handle both string and dict formats
            if isinstance(insight, dict):
                # Format dict as a readable string
                insight_text = f"{insight.get('ticker', 'N/A')}: {insight.get('rationale', str(insight))}"
            else:
                insight_text = str(insight)
            
            blocks.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [{"type": "text", "text": {"content": insight_text}}]
                }
            })
    
    # Channel Breakdown
    if basic_stats.get("channels"):
        blocks.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"type": "text", "text": {"content": "Channel Breakdown"}}]
            }
        })
        
        for channel, stats in basic_stats["channels"].items():
            blocks.append({
                "object": "block",
                "type": "heading_3",
                "heading_3": {
                    "rich_text": [{"type": "text", "text": {"content": channel}}]
                }
            })
            
            channel_info = [
                f"Messages: {stats['messages']:,}",
                f"Unique Authors: {stats['unique_authors']}"
            ]
            
            if stats.get("top_tickers"):
                top_3 = list(stats["top_tickers"].items())[:3]
                ticker_str = ", ".join([f"${t} ({c})" for t, c in top_3])
                channel_info.append(f"Top Tickers: {ticker_str}")
            
            for info in channel_info:
                blocks.append({
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {
                        "rich_text": [{"type": "text", "text": {"content": info}}]
                    }
                })
    
    return blocks

