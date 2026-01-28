#!/usr/bin/env python3
"""
PTT Stock Board Scraper
Scrapes threads from PTT Stock board with age gate bypass.
"""

import json
import os
import re
import time
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup


class PTTScraper:
    """Scraper for PTT Stock board with cookie-based age gate bypass."""
    
    BASE_URL = "https://www.ptt.cc"
    BOARD_URL = f"{BASE_URL}/bbs/Stock/index.html"
    
    def __init__(self, config_path: str = "config.json"):
        self.session = requests.Session()
        # Bypass age gate by setting over18 cookie
        self.session.cookies.set("over18", "1")
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })
        
        # Load config
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)
        
        self.pages_to_scrape = self.config["ptt"]["pages_to_scrape"]
        self.threads_limit = self.config["ptt"]["threads_limit"]
        self.raw_data_path = self.config["paths"]["raw_data"]
        
        # Ensure output directory exists
        os.makedirs(self.raw_data_path, exist_ok=True)
    
    def _get_page(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch and parse a page."""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return BeautifulSoup(response.text, "html.parser")
        except requests.RequestException as e:
            print(f"Error fetching {url}: {e}")
            return None
    
    def _get_prev_page_url(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract the 'Previous Page' (上頁) URL from page navigation."""
        paging = soup.find("div", class_="btn-group-paging")
        if paging:
            links = paging.find_all("a", class_="btn")
            for link in links:
                if "上頁" in link.text:
                    return self.BASE_URL + link["href"]
        return None
    
    def _parse_thread_list(self, soup: BeautifulSoup) -> list:
        """Parse thread list from index page."""
        threads = []
        entries = soup.find_all("div", class_="r-ent")
        
        for entry in entries:
            try:
                # Extract push count
                push_elem = entry.find("div", class_="nrec")
                push_text = push_elem.text.strip() if push_elem else "0"
                
                # Convert push count to integer
                if push_text == "爆":
                    push_count = 100  # "爆" means very popular (>99 pushes)
                elif push_text.startswith("X"):
                    push_count = -int(push_text[1:]) if len(push_text) > 1 else -10
                elif push_text.isdigit():
                    push_count = int(push_text)
                else:
                    push_count = 0
                
                # Extract title and link
                title_elem = entry.find("div", class_="title")
                if title_elem:
                    link = title_elem.find("a")
                    if link:
                        title = link.text.strip()
                        href = self.BASE_URL + link["href"]
                        
                        # Extract date
                        date_elem = entry.find("div", class_="date")
                        date = date_elem.text.strip() if date_elem else ""
                        
                        # Extract author
                        author_elem = entry.find("div", class_="author")
                        author = author_elem.text.strip() if author_elem else ""
                        
                        threads.append({
                            "title": title,
                            "url": href,
                            "push_count": push_count,
                            "date": date,
                            "author": author
                        })
            except Exception as e:
                print(f"Error parsing entry: {e}")
                continue
        
        return threads
    
    def _parse_thread_content(self, url: str) -> dict:
        """Parse individual thread content and comments."""
        soup = self._get_page(url)
        if not soup:
            return {"content": "", "comments": []}
        
        result = {
            "content": "",
            "comments": []
        }
        
        try:
            # Find main content
            main_content = soup.find("div", id="main-content")
            if main_content:
                # Extract post content (before pushes)
                content_text = []
                for child in main_content.children:
                    if hasattr(child, 'name'):
                        if child.name == 'div' and child.get('class'):
                            if 'push' in child.get('class', []):
                                break
                        elif child.name == 'span' and 'article-meta-value' in str(child.get('class', [])):
                            continue
                    if hasattr(child, 'text'):
                        text = child.text if hasattr(child, 'text') else str(child)
                        if text.strip():
                            content_text.append(text.strip())
                    elif isinstance(child, str) and child.strip():
                        content_text.append(child.strip())
                
                # Clean content
                content = "\n".join(content_text)
                # Remove metadata headers
                content = re.sub(r'^作者.*?\n', '', content)
                content = re.sub(r'^看板.*?\n', '', content)
                content = re.sub(r'^標題.*?\n', '', content)
                content = re.sub(r'^時間.*?\n', '', content)
                result["content"] = content.strip()
                
                # Extract push comments
                pushes = main_content.find_all("div", class_="push")
                for push in pushes:
                    try:
                        tag = push.find("span", class_="push-tag")
                        user = push.find("span", class_="push-userid")
                        content_span = push.find("span", class_="push-content")
                        
                        if content_span:
                            push_type = tag.text.strip() if tag else ""
                            push_user = user.text.strip() if user else ""
                            push_content = content_span.text.strip()
                            if push_content.startswith(": "):
                                push_content = push_content[2:]
                            
                            result["comments"].append({
                                "type": push_type,  # 推/噓/→
                                "user": push_user,
                                "content": push_content
                            })
                    except Exception:
                        continue
        
        except Exception as e:
            print(f"Error parsing thread content: {e}")
        
        return result
    
    def scrape(self) -> list:
        """Scrape threads from PTT Stock board."""
        all_threads = []
        current_url = self.BOARD_URL
        pages_scraped = 0
        
        print(f"Starting PTT Stock board scrape...")
        print(f"Target: {self.threads_limit} threads from {self.pages_to_scrape} pages")
        
        while pages_scraped < self.pages_to_scrape and len(all_threads) < self.threads_limit:
            print(f"\nScraping page {pages_scraped + 1}: {current_url}")
            
            soup = self._get_page(current_url)
            if not soup:
                print(f"Failed to fetch page, stopping...")
                break
            
            threads = self._parse_thread_list(soup)
            print(f"Found {len(threads)} threads on this page")
            
            # Fetch content for each thread
            for i, thread in enumerate(threads):
                if len(all_threads) >= self.threads_limit:
                    break
                
                print(f"  [{len(all_threads) + 1}/{self.threads_limit}] Fetching: {thread['title'][:40]}...")
                
                content_data = self._parse_thread_content(thread["url"])
                thread["content"] = content_data["content"]
                thread["comments"] = content_data["comments"]
                
                all_threads.append(thread)
                
                # Rate limiting
                time.sleep(0.5)
            
            # Get previous page URL
            prev_url = self._get_prev_page_url(soup)
            if not prev_url:
                print("No more pages to scrape")
                break
            
            current_url = prev_url
            pages_scraped += 1
            time.sleep(1)  # Rate limiting between pages
        
        print(f"\nTotal threads scraped: {len(all_threads)}")
        return all_threads
    
    def save_data(self, threads: list) -> str:
        """Save scraped data to JSON file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"raw_ptt_data_{timestamp}.json"
        filepath = os.path.join(self.raw_data_path, filename)
        
        data = {
            "scraped_at": datetime.now().isoformat(),
            "board": "Stock",
            "total_threads": len(threads),
            "threads": threads
        }
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"Data saved to: {filepath}")
        return filepath


def main():
    """Main entry point."""
    # Change to project root directory if running from src/scraper
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(script_dir))
    os.chdir(project_root)
    
    scraper = PTTScraper()
    threads = scraper.scrape()
    
    if threads:
        filepath = scraper.save_data(threads)
        print(f"\n✓ Successfully scraped {len(threads)} threads")
        print(f"✓ Data saved to: {filepath}")
    else:
        print("No threads were scraped")


if __name__ == "__main__":
    main()
