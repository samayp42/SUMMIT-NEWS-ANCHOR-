"""
News Service Module for Voice AI News Anchor
=============================================

This module fetches real-time news from various sources for the workshop.
Uses NewsAPI.org as primary source, with fallback to mock data for offline demos.

For the workshop, you can:
1. Use real API key for live news
2. Use mock headlines for offline demo
"""

import os
import json
import aiohttp
from datetime import datetime
from typing import Dict, Any, List, Optional
from loguru import logger

# Path to cache/mock data
NEWS_CACHE_FILE = os.path.join(os.path.dirname(__file__), "news_data.json")

# API Configuration
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")
NEWS_API_BASE = "https://newsapi.org/v2"

# Categories supported
NEWS_CATEGORIES = [
    "headlines",      # Top headlines
    "technology",     # Tech news
    "business",       # Markets, business
    "sports",         # Sports news
    "entertainment",  # Entertainment
    "science",        # Science & health
    "world"           # International news
]

# Mock headlines for offline demo
MOCK_HEADLINES = {
    "headlines": [
        {
            "title": "India AI Summit 2025 Kicks Off with Record Attendance",
            "description": "The annual India AI Summit has begun with over 10,000 attendees exploring the latest in artificial intelligence and machine learning.",
            "source": "Tech Today India",
            "published": "2 hours ago"
        },
        {
            "title": "Intel Launches New AI PC Chips Optimized for Local LLMs",
            "description": "Intel's latest Core Ultra processors enable running large language models entirely on personal computers without cloud dependency.",
            "source": "Hardware Weekly",
            "published": "4 hours ago"
        },
        {
            "title": "Renewable Energy Investments Hit All-Time High",
            "description": "Global investments in solar and wind energy have reached unprecedented levels as countries accelerate green transition.",
            "source": "Climate Monitor",
            "published": "6 hours ago"
        }
    ],
    "technology": [
        {
            "title": "Voice AI Assistants Gain Traction in Enterprise Applications",
            "description": "Companies are increasingly deploying voice-based AI agents for customer service and internal operations.",
            "source": "Enterprise Tech",
            "published": "1 hour ago"
        },
        {
            "title": "Open Source LLMs Rival Commercial Models in Latest Benchmarks",
            "description": "New open-source language models are achieving performance comparable to proprietary offerings.",
            "source": "AI Research Daily",
            "published": "3 hours ago"
        },
        {
            "title": "Edge Computing Enables Real-Time AI Processing",
            "description": "Local AI processing on edge devices reduces latency and improves privacy for sensitive applications.",
            "source": "Tech Insights",
            "published": "5 hours ago"
        }
    ],
    "business": [
        {
            "title": "Markets Rally on Strong Economic Data",
            "description": "Stock markets surged as employment figures exceeded expectations and inflation showed signs of cooling.",
            "source": "Financial Express",
            "published": "30 minutes ago"
        },
        {
            "title": "AI Startups Attract Record Venture Capital",
            "description": "Investment in artificial intelligence companies has doubled compared to the previous year.",
            "source": "Startup Weekly",
            "published": "2 hours ago"
        },
        {
            "title": "NIFTY Crosses New Milestone Amid Tech Rally",
            "description": "The benchmark index reached new highs driven by strong performance in technology and banking sectors.",
            "source": "Market Watch India",
            "published": "4 hours ago"
        }
    ],
    "sports": [
        {
            "title": "India Clinches Thrilling Victory in Test Match",
            "description": "A spectacular final day performance sealed India's win in a closely contested test match.",
            "source": "Sports Today",
            "published": "1 hour ago"
        },
        {
            "title": "IPL Auction Sets New Records for Player Valuations",
            "description": "This year's IPL auction saw unprecedented bidding wars for top cricket talents.",
            "source": "Cricket Weekly",
            "published": "3 hours ago"
        },
        {
            "title": "Olympic Preparations in Full Swing",
            "description": "Athletes across the country are intensifying training ahead of the upcoming Olympic games.",
            "source": "Sports Tribune",
            "published": "5 hours ago"
        }
    ],
    "entertainment": [
        {
            "title": "Bollywood Film Breaks Box Office Records",
            "description": "The latest blockbuster has become the highest-grossing Indian film in international markets.",
            "source": "Film Fare",
            "published": "2 hours ago"
        },
        {
            "title": "Music Streaming Hits New Peak in India",
            "description": "Digital music consumption has reached record levels with millions of new subscribers.",
            "source": "Entertainment Daily",
            "published": "4 hours ago"
        },
        {
            "title": "International Film Festival Announces Lineup",
            "description": "The prestigious festival will showcase diverse films from over 50 countries.",
            "source": "Cinema Today",
            "published": "6 hours ago"
        }
    ],
    "science": [
        {
            "title": "ISRO Announces Ambitious Space Mission",
            "description": "India's space agency reveals plans for advanced deep space exploration missions.",
            "source": "Science India",
            "published": "1 hour ago"
        },
        {
            "title": "Breakthrough in Quantum Computing Announced",
            "description": "Researchers achieve significant milestone in quantum error correction.",
            "source": "Tech Science Journal",
            "published": "3 hours ago"
        },
        {
            "title": "Climate Scientists Report Positive Developments",
            "description": "New data suggests some environmental protection measures are showing results.",
            "source": "Environment Today",
            "published": "5 hours ago"
        }
    ],
    "world": [
        {
            "title": "Global Summit Addresses Climate Action",
            "description": "World leaders convene to discuss accelerated measures for environmental protection.",
            "source": "World News Network",
            "published": "2 hours ago"
        },
        {
            "title": "International Trade Agreement Signed",
            "description": "Major economies reach consensus on new trade framework promoting digital commerce.",
            "source": "Global Tribune",
            "published": "4 hours ago"
        },
        {
            "title": "Technology Driving Economic Growth Worldwide",
            "description": "AI and automation are identified as key drivers of economic expansion across regions.",
            "source": "International Herald",
            "published": "6 hours ago"
        }
    ]
}


async def fetch_live_news(category: str = "headlines", country: str = "in") -> List[Dict[str, Any]]:
    """
    Fetch live news from NewsAPI.
    
    Args:
        category: News category (headlines, technology, business, etc.)
        country: Country code (default: in for India)
        
    Returns:
        List of news articles
    """
    if not NEWS_API_KEY:
        logger.warning("No NEWS_API_KEY set, using mock data")
        return get_mock_news(category)
    
    try:
        async with aiohttp.ClientSession() as session:
            if category == "headlines":
                url = f"{NEWS_API_BASE}/top-headlines"
                params = {"country": country, "apiKey": NEWS_API_KEY, "pageSize": 5}
            else:
                url = f"{NEWS_API_BASE}/top-headlines"
                params = {
                    "country": country, 
                    "category": category, 
                    "apiKey": NEWS_API_KEY,
                    "pageSize": 5
                }
            
            async with session.get(url, params=params, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    articles = data.get("articles", [])
                    
                    # Transform to our format
                    return [
                        {
                            "title": a.get("title", ""),
                            "description": a.get("description", ""),
                            "source": a.get("source", {}).get("name", "Unknown"),
                            "published": a.get("publishedAt", "")
                        }
                        for a in articles[:5]
                    ]
                else:
                    logger.warning(f"NewsAPI returned {response.status}, using mock data")
                    return get_mock_news(category)
                    
    except Exception as e:
        logger.error(f"Failed to fetch live news: {e}")
        return get_mock_news(category)


def get_mock_news(category: str = "headlines") -> List[Dict[str, Any]]:
    """
    Get mock news for offline demo.
    
    Args:
        category: News category
        
    Returns:
        List of mock news articles
    """
    cat = category.lower()
    if cat in MOCK_HEADLINES:
        return MOCK_HEADLINES[cat]
    return MOCK_HEADLINES["headlines"]


def get_current_news_sync(category: str = "headlines") -> List[Dict[str, Any]]:
    """
    Synchronous version - returns cached/mock news.
    For async fetching, use fetch_live_news().
    """
    # Try to read from cache first
    try:
        if os.path.exists(NEWS_CACHE_FILE):
            with open(NEWS_CACHE_FILE, 'r') as f:
                cached = json.load(f)
                if category in cached:
                    return cached[category]
    except:
        pass
    
    return get_mock_news(category)


def format_news_for_speech(articles: List[Dict[str, Any]], category: str = "headlines") -> str:
    """
    Format news articles for natural speech synthesis.
    
    Args:
        articles: List of news articles
        category: Category name for context
        
    Returns:
        Formatted string suitable for TTS
    """
    if not articles:
        return "I don't have any news updates at the moment. Please try again shortly."
    
    category_intros = {
        "headlines": "Here are today's top headlines.",
        "technology": "In technology news today.",
        "business": "Looking at business and markets.",
        "sports": "Here's the latest in sports.",
        "entertainment": "In entertainment news.",
        "science": "From the world of science.",
        "world": "Here's what's happening around the world."
    }
    
    intro = category_intros.get(category, "Here's the latest news.")
    
    speech_parts = [intro]
    
    for i, article in enumerate(articles[:3], 1):  # Limit to 3 for voice
        title = article.get("title", "")
        source = article.get("source", "")
        
        if i == 1:
            speech_parts.append(f"First, {title}.")
        elif i == 2:
            speech_parts.append(f"Also, {title}.")
        else:
            speech_parts.append(f"And, {title}.")
    
    speech_parts.append("Would you like more details on any of these stories?")
    
    return " ".join(speech_parts)


def create_news_context_prompt(category: str = "headlines") -> str:
    """
    Creates a formatted context string for injection into the LLM prompt.
    This connects live news data to AI reasoning.
    
    Args:
        category: News category to fetch
        
    Returns:
        Formatted string with current news data
    """
    articles = get_current_news_sync(category)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    news_text = ""
    for i, article in enumerate(articles, 1):
        news_text += f"""
STORY {i}:
  Title: {article.get('title', 'N/A')}
  Summary: {article.get('description', 'N/A')}
  Source: {article.get('source', 'Unknown')}
  Time: {article.get('published', 'Recent')}
"""
    
    return f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📰 REAL-TIME NEWS DATA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🕐 Last Updated: {timestamp}
📂 Category: {category.upper()}

{news_text}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Use this real-time news data when answering questions.
When reporting news, cite the source name.
Summarize headlines naturally, don't read verbatim.
Offer to provide more details on specific stories.
"""


async def update_news_cache(category: str = "headlines") -> bool:
    """
    Update the local news cache with fresh data.
    
    Args:
        category: Category to update
        
    Returns:
        True if successful
    """
    try:
        articles = await fetch_live_news(category)
        
        # Read existing cache
        cache = {}
        if os.path.exists(NEWS_CACHE_FILE):
            with open(NEWS_CACHE_FILE, 'r') as f:
                cache = json.load(f)
        
        # Update category
        cache[category] = articles
        cache["_updated"] = datetime.now().isoformat()
        
        # Write back
        with open(NEWS_CACHE_FILE, 'w') as f:
            json.dump(cache, f, indent=2)
        
        return True
    except Exception as e:
        logger.error(f"Failed to update news cache: {e}")
        return False


def print_current_news(category: str = "headlines"):
    """Print current news in a nice format (for debugging)."""
    articles = get_current_news_sync(category)
    print("\n" + "="*60)
    print(f"📰 CURRENT NEWS - {category.upper()}")
    print("="*60)
    for i, article in enumerate(articles, 1):
        print(f"\n  [{i}] {article.get('title', 'N/A')}")
        print(f"      Source: {article.get('source', 'Unknown')}")
        print(f"      Time: {article.get('published', 'Recent')}")
    print("="*60 + "\n")


if __name__ == "__main__":
    # Demo: Print current news
    print_current_news("headlines")
    print("\n📝 CONTEXT PROMPT FOR LLM:")
    print(create_news_context_prompt("headlines"))
    
    # Show formatted for speech
    articles = get_mock_news("technology")
    print("\n🎙️ SPEECH VERSION:")
    print(format_news_for_speech(articles, "technology"))
