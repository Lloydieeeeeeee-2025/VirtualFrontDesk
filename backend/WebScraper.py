import time
import requests
from bs4 import BeautifulSoup
from typing import List, Dict
from datetime import datetime


class WebScraper:
    """Handles scraping and processing of website content."""

    def __init__(self):
        self.timeout = 15
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

    def get_urls_from_database(self, repo) -> List[Dict]:
        """Fetch URLs from the database URL table."""
        db = repo.get_db_connection()
        if not db:
            print("Failed to connect to database to fetch URLs")
            return []

        try:
            conn = db.cursor()
            conn.execute("SELECT link_url, description, updated_at FROM URL")
            urls = [
                {
                    "url": row[0],
                    "description": row[1],
                    "updated_at": row[2]
                }
                for row in conn.fetchall()
            ]
            db.close()
            print(f"Fetched {len(urls)} URLs from database")
            return urls
        except Exception as e:
            print(f"Error fetching URLs from database: {e}")
            if db:
                db.close()
            return []

    def scrape_website_content(self, url: str, description: str) -> Dict:
        """Scrape content from a single URL."""
        try:
            print(f"  Scraping: {url}")
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()

            content_type = response.headers.get('Content-Type', '')
            if 'text/html' not in content_type:
                print(f"  {url} is not HTML content, skipping...")
                return None

            soup = BeautifulSoup(response.content, 'html.parser')
            for element in soup(['script', 'style', 'nav', 'header', 'footer', 'iframe', 'svg', 'form']):
                element.decompose()

            main_content = soup.find('main') or soup.find('article') or \
                          soup.find('div', class_=lambda x: x and ('content' in x.lower() or 'main' in x.lower()))

            if main_content:
                content = main_content.get_text(separator='\n', strip=True)
            else:
                content = soup.get_text(separator='\n', strip=True)

            content = '\n'.join(line.strip() for line in content.split('\n') if line.strip())

            if not content:
                print(f"  No content extracted from {url}")
                return None

            full_content = f"URL: {url}\n"
            if description:
                full_content += f"Description: {description}\n\n"
            full_content += content

            return {
                'url': url,
                'content': full_content.strip()
            }

        except requests.RequestException as e:
            print(f"  Failed to scrape {url}: {e}")
            return None
        except Exception as e:
            print(f"  Error processing {url}: {e}")
            return None

    def scrape_all_websites(self, repo) -> List[Dict]:
        """Scrape content from all URLs stored in database."""
        print("Starting website scraping...")
        url_data = self.get_urls_from_database(repo)

        if not url_data:
            print("No URLs found in database to scrape")
            return []

        all_content = []
        for item in url_data:
            url = item['url']
            description = item['description']
            result = self.scrape_website_content(url, description)
            
            if result:
                all_content.append({
                    'url': url,
                    'description': description,
                    'updated_at': item['updated_at'],
                    'content': result['content'],
                    'scraped_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
            time.sleep(2)

        print(f"Scraped {len(all_content)} out of {len(url_data)} URLs")
        return all_content

    def process_scraped_content(self, scraped_data: List[Dict], documents: List[str],
                               metadata: List[Dict], ids: List[str], text_splitter) -> None:
        """Process scraped website content into chunks."""
        for item in scraped_data:
            url = item['url']
            content = item['content']
            
            if not content.strip():
                continue

            chunks = text_splitter.split_text(content)
            url_id = url.replace('https://', '').replace('http://', '').replace('/', '_').replace('.', '_')
            url_id = url_id.rstrip('_')

            for idx, chunk in enumerate(chunks):
                documents.append(chunk)
                chunk_id = f"url_{url_id}_chunk_{idx}"
                ids.append(chunk_id)
                metadata.append({
                    "source_url": url,
                    "data_type": "url",
                    "description": item.get('description', ''),
                    "scraped_at": item['scraped_at'],
                    "updated_at": item['updated_at'].strftime('%Y-%m-%d %H:%M:%S') if item['updated_at'] else '',
                    "chunk_index": idx,
                    "is_archived": False,
                    "document_version": "current"
                })

        print(f"Processed {len([id for id in ids if id.startswith('url_')])} URL chunks")