#!/usr/bin/env python3
"""
PTT Stock Board Smart Scraper
Scrapes threads incrementally and stores directly to SQLite database.
"""

import re
import sys
import time
from datetime import datetime
from typing import Optional, Tuple
import os

import requests
from bs4 import BeautifulSoup

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.database import get_db, init_db, Post


class PTTScraper:
    """Smart scraper for PTT Stock board with incremental logic."""
    
    BASE_URL = "https://www.ptt.cc"
    BOARD_URL = f"{BASE_URL}/bbs/Stock/index.html"
    MAX_RETRIES = 3
    RETRY_DELAY = 5  # seconds
    REQUEST_DELAY = 1  # seconds between requests
    
    def __init__(self, max_pages: int = 10, backfill: bool = False, start_page: int = None):
        self.session = requests.Session()
        # Bypass age gate with over18 cookie
        self.session.cookies.set("over18", "1")
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        self.max_pages = max_pages
        self.backfill = backfill  # If True, continue past cached posts
        self.start_page = start_page  # If set, start from specific page number
        self.new_posts_count = 0
    
    def _request_with_retry(self, url: str) -> Optional[requests.Response]:
        """Make request with retry mechanism for 403/503 errors."""
        for attempt in range(self.MAX_RETRIES):
            try:
                response = self.session.get(url, timeout=15)
                
                if response.status_code == 200:
                    return response
                elif response.status_code in (403, 503):
                    print(f"  ⚠️ Got {response.status_code}, retrying in {self.RETRY_DELAY}s...")
                    time.sleep(self.RETRY_DELAY)
                else:
                    print(f"  ❌ Unexpected status: {response.status_code}")
                    return None
                    
            except requests.RequestException as e:
                print(f"  ❌ Request error: {e}")
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY)
        
        return None
    
    def _get_page(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch and parse a page."""
        response = self._request_with_retry(url)
        if response:
            return BeautifulSoup(response.text, "html.parser")
        return None
    
    def _get_prev_page_url(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract the 'Previous Page' URL from navigation."""
        paging = soup.find("div", class_="btn-group-paging")
        if paging:
            links = paging.find_all("a", class_="btn")
            for link in links:
                if "上頁" in link.text:
                    return self.BASE_URL + link["href"]
        return None
    
    def _extract_post_id(self, url: str) -> str:
        """Extract post ID from URL (e.g., /bbs/Stock/M.123456.A.123.html -> M.123456.A.123)"""
        match = re.search(r'/([^/]+)\.html$', url)
        if match:
            return match.group(1)
        return url  # fallback
    
    def _parse_push_boo_counts(self, soup: BeautifulSoup) -> Tuple[int, int]:
        """Parse push and boo counts from thread content."""
        push_count = 0
        boo_count = 0
        
        pushes = soup.find_all("div", class_="push")
        for push in pushes:
            tag = push.find("span", class_="push-tag")
            if tag:
                tag_text = tag.text.strip()
                if tag_text == "推":
                    push_count += 1
                elif tag_text == "噓":
                    boo_count += 1
        
        return push_count, boo_count
    
    def _parse_publish_time(self, soup: BeautifulSoup) -> Optional[datetime]:
        """Parse publish time from thread metadata."""
        metas = soup.find_all("div", class_="article-metaline")
        for meta in metas:
            tag = meta.find("span", class_="article-meta-tag")
            if tag and "時間" in tag.text:
                value = meta.find("span", class_="article-meta-value")
                if value:
                    try:
                        # PTT date format: "Wed Jan 28 12:34:56 2026"
                        date_str = value.text.strip()
                        return datetime.strptime(date_str, "%a %b %d %H:%M:%S %Y")
                    except ValueError:
                        pass
        return datetime.now()  # fallback
    
    def _parse_thread_content(self, soup: BeautifulSoup) -> str:
        """Extract main content from thread."""
        main_content = soup.find("div", id="main-content")
        if not main_content:
            return ""
        
        content_parts = []
        for child in main_content.children:
            if hasattr(child, 'name'):
                if child.name == 'div':
                    classes = child.get('class', [])
                    if 'push' in classes or 'article-metaline' in classes or 'article-metaline-right' in classes:
                        continue
            
            text = child.text if hasattr(child, 'text') else str(child)
            if isinstance(text, str) and text.strip():
                content_parts.append(text.strip())
        
        return "\n".join(content_parts)[:5000]  # Limit content size
    
    def _parse_thread_list(self, soup: BeautifulSoup) -> list:
        """Parse thread list from index page."""
        threads = []
        entries = soup.find_all("div", class_="r-ent")
        
        for entry in entries:
            try:
                title_elem = entry.find("div", class_="title")
                if not title_elem:
                    continue
                
                link = title_elem.find("a")
                if not link:
                    continue  # Deleted post
                
                title = link.text.strip()
                href = self.BASE_URL + link["href"]
                post_id = self._extract_post_id(link["href"])
                
                # Extract author
                author_elem = entry.find("div", class_="author")
                author = author_elem.text.strip() if author_elem else "unknown"
                
                threads.append({
                    "id": post_id,
                    "title": title,
                    "url": href,
                    "author": author
                })
                
            except Exception as e:
                print(f"  ⚠️ Error parsing entry: {e}")
                continue
        
        return threads
    
    def _post_exists(self, db, post_id: str) -> bool:
        """Check if post already exists in database."""
        return db.query(Post).filter(Post.id == post_id).first() is not None
    
    def _save_post(self, db, post_data: dict) -> bool:
        """Save post to database. Returns True if new post saved."""
        try:
            post = Post(
                id=post_data["id"],
                title=post_data["title"],
                author=post_data["author"],
                content=post_data.get("content", ""),
                publish_time=post_data.get("publish_time", datetime.now()),
                push_count=post_data.get("push_count", 0),
                boo_count=post_data.get("boo_count", 0),
                url=post_data.get("url", "")
            )
            db.add(post)
            db.commit()  # Commit each post immediately
            return True
        except Exception as e:
            db.rollback()  # Rollback this post only
            print(f"  ⚠️ Skipping post (may exist): {post_data['id']}")
            return False
    
    def run(self) -> int:
        """
        Run the scraper with incremental logic.
        Returns the number of new posts scraped.
        
        If backfill=True, continues through all pages even when cached posts are found.
        If start_page is set, begins from that specific page number.
        """
        print("=" * 60)
        mode_info = ""
        if self.backfill:
            mode_info += " (BACKFILL)"
        if self.start_page:
            mode_info += f" (START: page {self.start_page})"
        print("PTT Stock Board Smart Scraper" + mode_info)
        print("=" * 60)
        
        # Determine starting URL
        if self.start_page:
            current_url = f"{self.BASE_URL}/bbs/Stock/index{self.start_page}.html"
        else:
            current_url = self.BOARD_URL
        pages_scraped = 0
        should_stop = False
        
        with get_db() as db:
            while pages_scraped < self.max_pages and not should_stop:
                print(f"\n📄 Scraping page {pages_scraped + 1}: {current_url}")
                
                soup = self._get_page(current_url)
                if not soup:
                    print("❌ Failed to fetch page, stopping...")
                    break
                
                threads = self._parse_thread_list(soup)
                print(f"   Found {len(threads)} threads")
                
                for thread in threads:
                    # Check if post already exists
                    if self._post_exists(db, thread["id"]):
                        if self.backfill:
                            continue  # Skip but continue
                        else:
                            print(f"   ✓ Post {thread['id']} already exists - caught up!")
                            should_stop = True
                            break
                    
                    # Fetch thread content
                    print(f"   → Fetching: {thread['title'][:40]}...")
                    thread_soup = self._get_page(thread["url"])
                    
                    if thread_soup:
                        thread["content"] = self._parse_thread_content(thread_soup)
                        thread["push_count"], thread["boo_count"] = self._parse_push_boo_counts(thread_soup)
                        thread["publish_time"] = self._parse_publish_time(thread_soup)
                    
                    # Save to database
                    if self._save_post(db, thread):
                        self.new_posts_count += 1
                    
                    time.sleep(self.REQUEST_DELAY)
                
                # Get previous page
                prev_url = self._get_prev_page_url(soup)
                if not prev_url:
                    print("   No more pages available")
                    break
                
                current_url = prev_url
                pages_scraped += 1
                time.sleep(self.REQUEST_DELAY)
        
        print("\n" + "=" * 60)
        print(f"✓ Scraped {self.new_posts_count} new posts")
        print("=" * 60)
        
        return self.new_posts_count


def main():
    """Entry point for scraper."""
    os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    init_db()
    
    scraper = PTTScraper(max_pages=5)
    new_posts = scraper.run()
    return new_posts


if __name__ == "__main__":
    main()
