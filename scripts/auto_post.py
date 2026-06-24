#!/usr/bin/env python3
"""MOMENTUM Auto-Post — fetches top news from RSS and posts to Telegram channel."""

import requests
import json
import os
import re
import time
from datetime import datetime, timezone

BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
CHANNEL_ID = os.environ.get('CHANNEL_ID', '@momentum_newss')
# Mini App URL — opens directly in Telegram (no bot dialog shown)
# Format: t.me/<bot_username>/<app_name> auto-opens the Mini App
WEB_APP_URL = os.environ.get('WEB_APP_URL', 'https://t.me/momentum_newsbot/momentum')
API = f'https://api.telegram.org/bot{BOT_TOKEN}'

# RSS sources (same as website)
SOURCES = [
    ('Lenta.ru', 'https://lenta.ru/rss', 'https://www.google.com/s2/favicons?domain=lenta.ru&sz=64'),
    ('РИА Новости', 'https://ria.ru/export/rss2/archive/index.xml', 'https://www.google.com/s2/favicons?domain=ria.ru&sz=64'),
    ('Хабр', 'https://habr.com/ru/rss/articles/top/?fl=ru', 'https://www.google.com/s2/favicons?domain=habr.com&sz=64'),
    ('Ведомости', 'https://www.vedomosti.ru/rss/news', 'https://www.google.com/s2/favicons?domain=vedomosti.ru&sz=64'),
    ('RT на русском', 'https://russian.rt.com/rss', 'https://www.google.com/s2/favicons?domain=russian.rt.com&sz=64'),
    ('Stopgame', 'https://rss.stopgame.ru/rss_news.xml', 'https://www.google.com/s2/favicons?domain=stopgame.ru&sz=64'),
    ('3DNews', 'https://3dnews.ru/news/rss/', 'https://www.google.com/s2/favicons?domain=3dnews.ru&sz=64'),
    ('VC.ru', 'https://vc.ru/rss/all', 'https://www.google.com/s2/favicons?domain=vc.ru&sz=64'),
    ('Наука.тв', 'https://naukatv.ru/rss', 'https://www.google.com/s2/favicons?domain=naukatv.ru&sz=64'),
    ('BBC Russian', 'https://feeds.bbci.co.uk/russian/rss.xml', 'https://www.google.com/s2/favicons?domain=bbc.com&sz=64'),
]

# Category emojis
CAT_EMOJI = {
    'Технологии': '📱', 'Бизнес': '💼', 'Наука': '🔬', 'Спорт': '🏃',
    'Культура': '🎨', 'Мир': '🌐', 'Общество': '🏛️', 'Происшествия': '⚠️',
    'Игры': '🕹️', 'ЧМ 2026': '🏆',
}

# Simple category mapping
CATEGORY_MAP = {
    'Технологии и Интернет': 'Технологии', 'Технологии': 'Технологии', 'Интернет': 'Технологии',
    'IT': 'Технологии', 'Наука и техника': 'Технологии', 'Наука и Техника': 'Технологии',
    'Экономика': 'Бизнес', 'Бизнес': 'Бизнес', 'Финансы': 'Бизнес', 'Биржи': 'Бизнес',
    'Наука': 'Наука', 'Космос': 'Наука',
    'Спорт': 'Спорт', 'Футбол': 'Спорт', 'Хоккей': 'Спорт',
    'Культура': 'Культура', 'Кино': 'Культура', 'Музыка': 'Культура',
    'Мир': 'Мир', 'В мире': 'Мир', 'Бывший СССР': 'Мир', 'Политика': 'Мир',
    'Общество': 'Общество', 'Россия': 'Общество',
    'Происшествия': 'Происшествия', 'Криминал': 'Происшествия',
    'Игры': 'Игры', 'Ценности': 'Культура', 'Из жизни': 'Культура',
    'Экономика и финансы': 'Бизнес', 'Силовые структуры': 'Происшествия',
    'Разработка': 'Технологии', 'Стартапы': 'Бизнес', 'Маркетинг': 'Бизнес',
    'Гаджеты': 'Технологии', 'Искусственный интеллект': 'Технологии',
}

def strip_html(text):
    """Remove HTML tags and clean up text."""
    if not text:
        return ''
    # Remove CDATA
    text = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', text, flags=re.DOTALL)
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Decode entities
    text = text.replace('&quot;', '"').replace('&amp;', '&').replace('&lt;', '<')
    text = text.replace('&gt;', '>').replace('&nbsp;', ' ').replace('&#39;', "'")
    text = text.replace('&laquo;', '«').replace('&raquo;', '»')
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def map_category(raw):
    if not raw:
        return 'Общество'
    raw = raw.strip()
    if raw in CATEGORY_MAP:
        return CATEGORY_MAP[raw]
    for k, v in CATEGORY_MAP.items():
        if k.lower() in raw.lower():
            return v
    return 'Общество'

def time_ago(iso_str):
    try:
        d = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
    except:
        return ''
    now = datetime.now(timezone.utc)
    diff = (now - d).total_seconds()
    if diff < 3600:
        return f'{int(diff / 60)} мин назад'
    if diff < 86400:
        return f'{int(diff / 3600)} ч назад'
    return f'{int(diff / 86400)} дн назад'

def fetch_rss(source_name, rss_url, favicon_url):
    """Fetch RSS feed and return list of articles."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (compatible; MOMENTUMBot/1.0)'}
        resp = requests.get(rss_url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return []

        # Parse XML manually (avoid dependencies)
        import xml.etree.ElementTree as ET
        root = ET.fromstring(resp.content)

        # Handle RSS 2.0 and Atom
        items = root.findall('.//item')
        if not items:
            items = root.findall('.//{http://www.w3.org/2005/Atom}entry')

        articles = []
        for item in items[:10]:
            def get_text(tag):
                el = item.find(tag)
                if el is None:
                    # Try with namespace
                    el = item.find(f'.//{tag}')
                return el.text if el is not None and el.text else ''

            title = strip_html(get_text('title'))
            if not title:
                continue

            link = get_text('link')
            # Atom feeds have link as attribute
            if not link:
                link_el = item.find('{http://www.w3.org/2005/Atom}link')
                if link_el is not None:
                    link = link_el.get('href', '')

            pub_date = get_text('pubDate') or get_text('published') or ''
            try:
                dt = datetime.strptime(pub_date, '%a, %d %b %Y %H:%M:%S %z')
                iso = dt.isoformat()
            except:
                try:
                    dt = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
                    iso = dt.isoformat()
                except:
                    iso = datetime.now(timezone.utc).isoformat()

            category_raw = get_text('category')
            category = map_category(category_raw)

            desc = strip_html(get_text('description'))
            excerpt = desc[:200] if desc else ''

            # Extract image
            image = ''
            enc = item.find('enclosure')
            if enc is not None:
                url = enc.get('url', '')
                mtype = enc.get('type', '')
                if url and (not mtype or mtype.startswith('image')):
                    image = url

            if not image:
                media = item.find('{http://search.yahoo.com/mrss/}content')
                if media is not None and media.get('medium') == 'image':
                    image = media.get('url', '')

            if not image:
                media_thumb = item.find('{http://search.yahoo.com/mrss/}thumbnail')
                if media_thumb is not None:
                    image = media_thumb.get('url', '')

            if not image and desc:
                m = re.search(r'<img[^>]+src="([^"]+)"', get_text('description'))
                if m:
                    image = m.group(1)

            # ЧМ 2026 keyword filter
            title_lower = title.lower()
            if re.search(r'чм[-\s]?2026|чемпионат мира 2026|мундиаль', title_lower):
                category = 'ЧМ 2026'

            articles.append({
                'title': title,
                'link': link,
                'category': category,
                'excerpt': excerpt,
                'image': image,
                'published_at': iso,
                'source_name': source_name,
                'favicon': favicon_url,
            })

        return articles
    except Exception as e:
        print(f'Error fetching {source_name}: {e}')
        return []

def load_posted():
    """Load previously posted article titles to avoid duplicates."""
    try:
        with open('scripts/posted_articles.json', 'r') as f:
            return set(json.load(f))
    except:
        return set()

def save_posted(posted):
    """Save posted article titles."""
    try:
        with open('scripts/posted_articles.json', 'w') as f:
            json.dump(list(posted)[-200:], f)
    except:
        pass

def post_article(article):
    """Post a single article to the channel with image."""
    cat_emoji = CAT_EMOJI.get(article['category'], '📰')
    time_str = time_ago(article['published_at'])

    # Truncate title if too long
    title = article['title'][:200]
    excerpt = article['excerpt'][:300] if article['excerpt'] else ''

    # Build caption
    caption = f"{cat_emoji} <b>{title}</b>\n\n"
    if excerpt:
        caption += f"{excerpt}...\n\n"
    caption += f"📡 <i>{article['source_name']}</i> · 🕒 {time_str}"

    # Inline keyboard button — opens Mini App directly in Telegram
    # Uses URL type with t.me/<bot>/<app> shortcut that auto-launches the Mini App
    reply_markup = {
        'inline_keyboard': [[
            {'text': '⚡ Открыть MOMENTUM', 'url': WEB_APP_URL}
        ]]
    }

    try:
        if article['image']:
            # Send photo with caption
            resp = requests.post(
                f'{API}/sendPhoto',
                json={
                    'chat_id': CHANNEL_ID,
                    'photo': article['image'],
                    'caption': caption,
                    'parse_mode': 'HTML',
                    'link_preview_options': {'is_disabled': True},
                    'reply_markup': reply_markup,
                },
                timeout=15
            )
        else:
            # Send text only
            resp = requests.post(
                f'{API}/sendMessage',
                json={
                    'chat_id': CHANNEL_ID,
                    'text': caption,
                    'parse_mode': 'HTML',
                    'link_preview_options': {'is_disabled': True},
                    'reply_markup': reply_markup,
                },
                timeout=15
            )

        if resp.status_code == 200 and resp.json().get('ok'):
            print(f'✅ Posted: {title[:50]}')
            return True
        else:
            print(f'❌ Failed to post: {resp.json()}')
            # If image failed, try text-only
            if article['image']:
                resp2 = requests.post(
                    f'{API}/sendMessage',
                    json={
                        'chat_id': CHANNEL_ID,
                        'text': caption,
                        'parse_mode': 'HTML',
                        'link_preview_options': {'is_disabled': True},
                        'reply_markup': reply_markup,
                    },
                    timeout=15
                )
                if resp2.status_code == 200 and resp2.json().get('ok'):
                    print(f'✅ Posted (text-only): {title[:50]}')
                    return True
            return False
    except Exception as e:
        print(f'❌ Error posting: {e}')
        return False

def main():
    if not BOT_TOKEN:
        print('❌ BOT_TOKEN not set')
        return

    print('🚀 MOMENTUM Auto-Post starting...')

    # Fetch all sources
    all_articles = []
    for name, rss, favicon in SOURCES:
        print(f'  Fetching {name}...')
        articles = fetch_rss(name, rss, favicon)
        all_articles.extend(articles)
        time.sleep(0.5)  # Be polite

    print(f'  Total articles fetched: {len(all_articles)}')

    if not all_articles:
        print('❌ No articles fetched')
        return

    # Sort by date (newest first)
    all_articles.sort(key=lambda a: a['published_at'], reverse=True)

    # Load previously posted
    posted = load_posted()

    # Filter out already posted
    new_articles = [a for a in all_articles if a['title'] not in posted]

    # Also deduplicate by similar titles
    seen_titles = []
    unique = []
    for a in new_articles:
        is_dup = False
        for seen in seen_titles:
            # Simple: if first 40 chars match
            if a['title'][:40].lower() == seen[:40].lower():
                is_dup = True
                break
        if not is_dup:
            unique.append(a)
            seen_titles.append(a['title'])

    # Prioritize articles with images
    with_images = [a for a in unique if a['image']]
    without_images = [a for a in unique if not a['image']]

    # Pick top 5 (prefer with images)
    to_post = (with_images + without_images)[:5]

    if not to_post:
        print('ℹ️ No new articles to post')
        return

    print(f'📝 Posting {len(to_post)} articles...')

    posted_count = 0
    for article in to_post:
        success = post_article(article)
        if success:
            posted.add(article['title'])
            posted_count += 1
            time.sleep(2)  # Avoid rate limiting

    # Save posted
    save_posted(posted)

    print(f'✅ Done! Posted {posted_count} articles')

if __name__ == '__main__':
    main()
