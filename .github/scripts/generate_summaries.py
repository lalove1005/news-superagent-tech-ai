#!/usr/bin/env python3
import os
import sys
import json
import re
import html
from datetime import datetime, timezone
import subprocess
import requests

date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

SOURCES = {
    "USA": [
        "https://techcrunch.com/feed/",
        "https://www.theverge.com/rss/index.xml"
    ],
    "China": [
        "https://www.ithome.com/rss",
        "https://www.cnbeta.com/backend.php",
        "https://www.gamersky.com/ent/rss.xml"
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

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:14b-instruct-q4_K_M"

def translate_title(title, target_lang='es'):
    """Translate title using Ollama LLM"""
    if target_lang == 'en':
        if not any('\u4e00' <= c <= '\u9fff' for c in title):
            return title
        prompt = f"""You are a translator. Translate this Chinese tech/news title to natural English. Keep proper names, company names, numbers, and technical terms as-is. Output ONLY the translation with no explanations, no formatting, no quotes.

Title: {title}

English translation:"""
    else:
        prompt = f"""You are a translator. Translate this tech/news title to natural Spanish. Keep proper names, company names, numbers, and technical terms as-is. Output ONLY the translation with no explanations, no formatting, no quotes.

Title: {title}

Spanish translation:"""
    
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.2, "top_p": 0.9, "num_predict": 100}
            },
            timeout=60
        )
        if response.status_code == 200:
            result = response.json()['response'].strip()
            result = result.strip('"\'')
            return result
    except Exception as e:
        print(f"Translation failed for '{title}': {e}", file=sys.stderr)
    
    return title

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
        
        # Detect WAF/challenge pages (like 36kr.com returns)
        if 'waf_verification' in content or '安全检测' in content or 'security check' in content.lower():
            print(f"  WARNING: {url} returned a WAF/challenge page, skipping", file=sys.stderr)
            return []
        
        item_blocks = re.findall(r'<item[^>]*>.*?</item>|<entry[^>]*>.*?</entry>', content, re.DOTALL)
        
        items = []
        for block in item_blocks[:8]:
            title_match = re.search(r'<title[^>]*><!\[CDATA\[(.*?)\]\]>|<title[^>]*>([^<]{20,200})</title>', block, re.DOTALL)
            if title_match:
                title = title_match.group(1) or title_match.group(2)
                title = html.unescape(title.strip())
            else:
                continue
            
            if 'rss' in title.lower() or 'feed' in title.lower() or len(title) < 20:
                continue
            
            link_match = re.search(r'<link[^>]*>([^<]+)</link>|<link[^>]*href="([^"]+)"', block)
            link = link_match.group(1) or link_match.group(2) if link_match else "N/A"
            
            desc_match = re.search(
                r'<description[^>]*><!\[CDATA\[(.*?)\]\]>|<description[^>]*>([^<]{50,1000})</description>|'
                r'<summary[^>]*><!\[CDATA\[(.*?)\]\]>|<summary[^>]*>([^<]{50,1000})</summary>|'
                r'<content[^>]*><!\[CDATA\[(.*?)\]\]>|<content[^>]*>([^<]{50,1000})</content>',
                block, re.DOTALL
            )
            
            description = ""
            if desc_match:
                for group in desc_match.groups():
                    if group:
                        description = html.unescape(group.strip())
                        break
            
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

def fetch_full_article(url):
    """Fetch and extract full article text from URL"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            return ""
        
        content = response.text
        
        # Try multiple content selectors for different sites
        patterns = [
            r'<article[^>]*>(.*?)</article>',
            r'<div[^>]*class="[^"]*article-body[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*post-content[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*entry-content[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*content[^"]*"[^>]*>(.*?)</div>',
            r'<main[^>]*>(.*?)</main>',
        ]
        
        article_text = ""
        for pattern in patterns:
            matches = re.findall(pattern, content, re.DOTALL)
            if matches:
                article_text = ' '.join(matches)
                break
        
        if not article_text:
            # Fallback: get all paragraph text
            paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', content, re.DOTALL)
            article_text = ' '.join(paragraphs)
        
        # Clean HTML
        article_text = re.sub(r'<script[^>]*>.*?</script>', '', article_text, flags=re.DOTALL)
        article_text = re.sub(r'<style[^>]*>.*?</style>', '', article_text, flags=re.DOTALL)
        article_text = re.sub(r'<[^>]+>', ' ', article_text)
        article_text = re.sub(r'&#\d+;', ' ', article_text)
        article_text = re.sub(r'\s+', ' ', article_text).strip()
        
        return article_text[:8000]  # Limit length
    except Exception as e:
        print(f"Error fetching article {url}: {e}", file=sys.stderr)
        return ""

def summarize_with_llm(title, article_text, lang='en'):
    """Use LLM to create ~150 word summary"""
    if not article_text or len(article_text) < 200:
        return ""
    
    if lang == 'en':
        prompt = f"""You are a tech news editor. Write a ~150 word summary of this article for a daily tech news broadcast. Focus on key facts, announcements, and implications. Be specific and informative. No fluff. No "this article covers" filler. Write in third person, broadcast style.

Title: {title}

Article text:
{article_text[:6000]}

Summary (~150 words):"""
    else:
        prompt = f"""Eres un editor de noticias tecnológicas. Escribe un resumen de ~150 palabras de este artículo para un boletín diario de noticias tech. Enfócate en hechos clave, anuncios e implicaciones. Sé específico e informativo. Sin relleno. No uses "este artículo aborda" ni frases genéricas. Escribe en tercera persona, estilo locución.

Título: {title}

Texto del artículo:
{article_text[:6000]}

Resumen (~150 palabras):"""
    
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.3, "top_p": 0.9, "num_predict": 250}
            },
            timeout=120
        )
        if response.status_code == 200:
            result = response.json()['response'].strip()
            # Clean up any chain-of-thought leakage
            result = re.sub(r'^(.*?)(?:Summary|Resumen|Aquí está|Here is)[:：]\s*', '', result, flags=re.IGNORECASE)
            result = result.strip('"\'').strip()
            # Remove common LLM prefixes
            for prefix in ['Summary:', 'Resumen:', 'Summary：', 'Resumen：', 'Aquí está el resumen:', 'Here is the summary:']:
                if result.startswith(prefix):
                    result = result[len(prefix):].strip()
            return result
    except Exception as e:
        print(f"Summarization failed for '{title}': {e}", file=sys.stderr)
    
    return ""

def translate_text(text, target_lang='es'):
    """Translate text to target language"""
    if target_lang == 'es':
        prompt = f"""Translate this tech news summary to natural Spanish for a news broadcast. Keep all names, numbers, companies, dates intact. Output ONLY the translation with no explanations, no formatting, no quotes.

Text: {text}

Spanish translation:"""
    else:
        prompt = f"""Translate this tech news summary to natural English for a news broadcast. Keep all names, numbers, companies, dates intact. Output ONLY the translation with no explanations, no formatting, no quotes.

Text: {text}

English translation:"""
    
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.2, "top_p": 0.9, "num_predict": 300}
            },
            timeout=90
        )
        if response.status_code == 200:
            result = response.json()['response'].strip()
            result = re.sub(r'^(.*?)(?:Translation|Traducción|Translation:|Traducción:)[:：]\s*', '', result, flags=re.IGNORECASE)
            result = result.strip('"\'').strip()
            return result
    except Exception as e:
        print(f"Translation failed: {e}", file=sys.stderr)
    
    return text

def generate_summary(region, lang, items):
    if lang == 'en':
        header = f"## {region} Tech & AI Top 5\n\n"
    else:
        header = f"## {region} Tech & IA Top 5\n\n"
    
    content = header
    
    for i, item in enumerate(items[:5], 1):
        title = item['title']
        link = item['link']
        
        # Translate title
        if lang == 'es':
            print(f"  Translating title {i}/{min(5, len(items))}: {title[:50]}...")
            title = translate_title(title, 'es')
        elif lang == 'en' and any('\u4e00' <= c <= '\u9fff' for c in title):
            print(f"  Translating Chinese title {i}/{min(5, len(items))}: {title[:50]}...")
            title = translate_title(title, 'en')
        
        content += f"{i}. **{title}**\n"
        content += f"Source/Fuente: {link}\n\n"
        
        # Fetch full article and summarize
        print(f"  Fetching full article for item {i}...")
        article_text = fetch_full_article(link)
        
        if article_text:
            print(f"  Summarizing with LLM...")
            summary = summarize_with_llm(title, article_text, lang)
            
            if not summary and lang == 'es' and item.get('description'):
                # Fallback: translate RSS description
                summary = translate_text(item['description'][:1000], 'es')
            elif not summary and item.get('description'):
                summary = item['description'][:500]
        else:
            # Fallback to RSS description
            if lang == 'es' and item.get('description'):
                summary = translate_text(item['description'][:1000], 'es')
            elif item.get('description'):
                summary = item['description'][:500]
            else:
                summary = ""
        
        if summary:
            content += f"{summary}\n\n"
        else:
            if lang == 'en':
                content += "Full article content could not be retrieved.\n\n"
            else:
                content += "No se pudo recuperar el contenido completo del artículo.\n\n"
    
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

print("Generated summaries")