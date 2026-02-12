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
import xml.etree.ElementTree as ET
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
            "title": "Govt Introduces Strict AI Rules, Platforms Must Remove Deepfakes in 3 Hours",
            "description": "New IT rules mandate rapid removal of AI-generated flagged content to curb misinformation.",
            "source": "India Today",
            "published": "2 hours ago"
        },
        {
            "title": "India to Host 'India AI Impact Summit 2026' with Global Tech CEOs",
            "description": "Sundar Pichai, Jensen Huang, and Sam Altman to attend the mega summit in New Delhi this week.",
            "source": "Economic Times",
            "published": "4 hours ago"
        },
        {
            "title": "ISRO Confirms Plans for Indian Space Station by 2035",
            "description": "Chairman V. Narayanan highlights international cooperation and future milestones at Space Business Forum.",
            "source": "The Hindu",
            "published": "6 hours ago"
        }
    ],
    "technology": [
        {
            "title": "India Ranks 2nd Globally in Enterprise AI Adoption",
            "description": "Zscaler report highlights India's massive surge in AI/ML transactions, trailing only the US.",
            "source": "TechCrunch India",
            "published": "1 hour ago"
        },
        {
            "title": "Google Expands 'Results About You' Privacy Tools in India",
            "description": "Users can now easily remove search results containing sensitive personal IDs like passports.",
            "source": "Gadgets360",
            "published": "3 hours ago"
        },
        {
            "title": "Global E-Waste Study Tour Kicks Off in New Delhi",
            "description": "ITU-led initiative focuses on sustainable e-waste regulation and circular economy transition.",
            "source": "Digit.in",
            "published": "5 hours ago"
        }
    ],
    "business": [
        {
            "title": "Indian Startups See Funding Surge: Petcare & AI Lead the Way",
            "description": "SuperTails raises $30M Series C, while AI healthtech firms secure record early-stage capital.",
            "source": "VentureBeat",
            "published": "30 minutes ago"
        },
        {
            "title": "Nvidia Partner Network Expands in Indian Manufacturing Sector",
            "description": "Local manufacturers adopt Nvidia Omniverse for digital twin simulations.",
            "source": "Business Standard",
            "published": "2 hours ago"
        },
        {
            "title": "Sensex Rallies on Strong Tech Earnings and AI Optimism",
            "description": "Markets close at record high driven by IT sector performance and global cues.",
            "source": "Moneycontrol",
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
    # Try Google News RSS first (Free & Unlimited)
    try:
        articles = await fetch_rss_news(category, country)
        if articles:
            return articles
    except Exception as e:
        logger.warning(f"RSS fetch failed: {e}")

    # Fallback to NewsAPI if key exists
    if NEWS_API_KEY:
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
                        return [
                            {
                                "title": a.get("title", ""),
                                "description": a.get("description", ""),
                                "source": a.get("source", {}).get("name", "Unknown"),
                                "published": a.get("publishedAt", "")
                            }
                            for a in articles[:5]
                        ]
        except Exception as e:
            logger.error(f"NewsAPI fetch failed: {e}")

    logger.info("Using mock news data as fallback")
    return get_mock_news(category)


async def fetch_rss_news(category: str, country: str = "IN") -> List[Dict[str, Any]]:
    """Fetch news from Google News RSS using search-based queries to avoid controversial content."""
    import urllib.parse
    country_code = country.upper()
    lang = "en"
    
    # Google News RSS - use SEARCH queries for safe, constructive content
    base_url = "https://news.google.com/rss"
    query_params = f"hl={lang}-{country_code}&gl={country_code}&ceid={country_code}:{lang}"
    
    # Search-based topics to avoid political/controversial headlines
    search_queries = {
        "headlines": "technology OR innovation OR science OR startup India",
        "technology": "AI artificial intelligence technology startup India",
        "business": "startup funding investment economy growth India",
        "sports": "cricket IPL sports India performance",
        "entertainment": "entertainment Bollywood music OTT India",
        "science": "space ISRO science research discovery India",
        "world": "technology innovation climate summit global"
    }
    
    query = search_queries.get(category, search_queries["headlines"])
    url = f"{base_url}/search?q={urllib.parse.quote(query)}&{query_params}"
    
    logger.debug(f"Fetching RSS: {url}")
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=10) as response:
            if response.status == 200:
                content = await response.text()
                root = ET.fromstring(content)
                
                articles = []
                # channel -> item
                for item in root.findall(".//item")[:5]:
                    title = item.find("title").text if item.find("title") is not None else "No Title"
                    pub_date = item.find("pubDate").text if item.find("pubDate") is not None else ""
                    desc = item.find("description").text if item.find("description") is not None else ""
                    source = item.find("source").text if item.find("source") is not None else "Google News"
                    
                    # Clean up title (Google News often has '... - Source')
                    if " - " in title:
                        source = title.split(" - ")[-1]
                        title = " - ".join(title.split(" - ")[:-1])
                        
                    articles.append({
                        "title": title,
                        "description": title, # RSS desc often contains HTML, safer to use title or clean it
                        "source": source,
                        "published": pub_date
                    })
                
                logger.debug(f"Fetched {len(articles)} articles via RSS")
                return articles
            
    return []


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
    # Try to read from cache first (but only if fresh — within 30 min)
    try:
        if os.path.exists(NEWS_CACHE_FILE):
            # Check file age
            file_age = datetime.now().timestamp() - os.path.getmtime(NEWS_CACHE_FILE)
            if file_age < 1800:  # 30 minutes
                with open(NEWS_CACHE_FILE, 'r') as f:
                    cached = json.load(f)
                    if category in cached:
                        return cached[category]
            else:
                logger.info(f"🗑️ News cache is {int(file_age/60)}min old, skipping stale data")
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
    Creates a MINIMAL context string for the LLM. 
    optimized for speed and to prevent reading metadata.
    """
    articles = get_current_news_sync(category)
    
    news_text = ""
    for i, article in enumerate(articles, 1):
        # clean title - remove source suffix if present like " - Times of India"
        title = article.get('title', 'N/A').split(' - ')[0]
        source = article.get('source', 'Unknown')
        
        # Only Title and Source. No description or time to confuse the LLM.
        news_text += f"[{i}] {title} (Source: {source})\n"
    
    return f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📰 LIVE NEWS FEED - {category.upper()}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{news_text}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INSTRUCTIONS:
1. Pick 1-2 most interesting stories from above.
2. SUMMARIZE them in your own words.
3. NEVER read the dates, times, or 'URL'.
4. Keep it under 3 sentences.
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
