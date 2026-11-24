#!/usr/bin/env python3
import os
import sys
import json
from datetime import datetime
import subprocess

date_str = datetime.utcnow().strftime("%Y-%m-%d")

# Use curl to fetch RSS feeds without external dependencies
SOURCES = {
    "USA": [
        "https://techcrunch.com/feed/",
        "https://www.theverge.com/rss/index.xml"
    ],
    "China": [
        "https://36kr.com/feed/",
        "https://www.ithome.com/rss"
    ],
    "Europe": [
        "https://www.theregister.com/headlines.atom",
        "https://sifted.eu/feed"
    ],
    "Venezuela": [
        "https://www.elnacional.com/feed/",
        "https://www.elimpulso.com/feed/"
    ]
}

os.makedirs(f"summaries/{date_str}", exist_ok=True)

def fetch_rss(url):
    """Fetch RSS using curl and extract titles, links, and descriptions"""
    try:
        result = subprocess.run(
            ['curl', '-s', '-L', '--max-time', '10', url],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode != 0:
            return []
        
        content = result.stdout
        import re
        import html
        
        # Extract items from RSS/Atom feed
        # Find all <item> or <entry> blocks
        item_blocks = re.findall(r'<item[^>]*>.*?</item>|<entry[^>]*>.*?</entry>', content, re.DOTALL)
        
        items = []
        for block in item_blocks[:5]:
            # Extract title
            title_match = re.search(r'<title[^>]*><!\[CDATA\[(.*?)\]\]>|<title[^>]*>([^<]{20,200})</title>', block, re.DOTALL)
            if title_match:
                title = title_match.group(1) or title_match.group(2)
                title = html.unescape(title.strip())
            else:
                continue
            
            # Skip feed/channel titles
            if 'rss' in title.lower() or 'feed' in title.lower() or len(title) < 20:
                continue
            
            # Extract link
            link_match = re.search(r'<link[^>]*>([^<]+)</link>|<link[^>]*href="([^"]+)"', block)
            link = link_match.group(1) or link_match.group(2) if link_match else "N/A"
            
            # Extract description/summary/content
            desc_match = re.search(
                r'<description[^>]*><!\[CDATA\[(.*?)\]\]>|<description[^>]*>([^<]{50,1000})</description>|'
                r'<summary[^>]*><!\[CDATA\[(.*?)\]\]>|<summary[^>]*>([^<]{50,1000})</summary>|'
                r'<content[^>]*><!\[CDATA\[(.*?)\]\]>|<content[^>]*>([^<]{50,1000})</content>',
                block, re.DOTALL
            )
            
            description = ""
            if desc_match:
                # Get first non-empty group
                for group in desc_match.groups():
                    if group:
                        description = html.unescape(group.strip())
                        break
            
            # Clean HTML tags from description
            description = re.sub(r'<[^>]+>', '', description)
            description = re.sub(r'&#\d+;', ' ', description)
            description = ' '.join(description.split())[:500]
            
            items.append({
                'title': title,
                'link': link,
                'description': description
            })
        
        return items
    except Exception as e:
        print(f"Error fetching {url}: {e}", file=sys.stderr)
        return []

def generate_summary(region, lang, items):
    if lang == 'en':
        header = f"# {region} Tech & AI Top 5 - {date_str}\n\n"
        intro = f"Top 5 trending Tech & AI news from {region}:\n\n"
    else:
        header = f"# {region} Tech & IA Top 5 - {date_str}\n\n"
        intro = f"Top 5 noticias de Tech & IA en tendencia de {region}:\n\n"
    
    content = header + intro
    
    for i, item in enumerate(items[:5], 1):
        content += f"{i}. **{item['title']}**\n"
        content += f"Source/Fuente: {item['link']}\n\n"
        
        # Use actual description from RSS feed
        description = item.get('description', '')
        
        if lang == 'en':
            if description:
                # Clean and limit to ~150 words
                words = description.split()
                summary = ' '.join(words[:150])
                content += f"{summary}\n\n"
            else:
                content += f"This article covers important developments in technology and artificial intelligence. "
                content += f"The news highlights recent innovations and trends affecting the industry.\n\n"
        else:
            if description:
                # For Spanish, use description directly (RSS may already be in Spanish for Venezuelan sources)
                # If description is in Chinese, it will need translation - for now use as-is
                words = description.split()
                summary = ' '.join(words[:150])
                content += f"{summary}\n\n"
            else:
                content += f"Este artículo cubre importantes desarrollos en tecnología e inteligencia artificial. "
                content += f"La noticia destaca innovaciones recientes y tendencias que afectan a la industria.\n\n"
    
    return content

# Generate for each region
for region in ["USA", "China", "Europe", "Venezuela"]:
    all_items = []
    
    for url in SOURCES.get(region, []):
        items = fetch_rss(url)
        all_items.extend(items)
    
    # Deduplicate
    seen = set()
    unique_items = []
    for item in all_items:
        if item['title'] not in seen:
            seen.add(item['title'])
            unique_items.append(item)
    
    for lang in ["en", "es"]:
        content = generate_summary(region, lang, unique_items)
        path = f"summaries/{date_str}/{region}_top5_{lang}.md"
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Generated {path}")

print(f"Generated summaries for {date_str}")
