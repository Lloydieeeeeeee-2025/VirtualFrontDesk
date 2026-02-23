import time
import requests
from bs4 import BeautifulSoup
from typing import List, Dict
from datetime import datetime


class WebScraper:
    """Handles scraping and processing of website content."""

    # HTML elements whose content is purely presentational and never informational.
    _DISCARD_TAGS = ['script', 'style', 'nav', 'header', 'iframe', 'svg', 'form']

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
            conn.execute("SELECT link_url, description, updated_at FROM url")
            urls = [
                {"url": row[0], "description": row[1], "updated_at": row[2]}
                for row in conn.fetchall()
            ]
            db.close()
            return urls
        except Exception as e:
            print(f"Error fetching URLs from database: {e}")
            if db:
                db.close()
            return []

    def _extract_footer_text(self, soup: BeautifulSoup) -> str:
        """
        Extract meaningful text from the page footer, including link text
        and href values (emails, social media URLs, map links) that carry
        contact/location information.
        Returns an empty string when no footer is present.
        """
        footer = soup.find('footer')
        if not footer:
            return ""

        lines = []

        # Walk every element inside the footer in document order.
        for element in footer.descendants:
            # Only process tag nodes; raw NavigableStrings are handled via parent tags.
            if not hasattr(element, 'name'):
                continue

            if element.name == 'a':
                link_text = element.get_text(strip=True)
                href = element.get('href', '').strip()

                # Normalise mailto: links so the raw email address is stored.
                if href.startswith('mailto:'):
                    email = href[len('mailto:'):]
                    entry = f"{link_text} {email}".strip() if link_text else email
                    lines.append(entry)
                # Keep map/social/external URLs alongside their visible label.
                elif href and href.startswith('http'):
                    entry = f"{link_text} ({href})".strip() if link_text else href
                    lines.append(entry)
                elif link_text:
                    lines.append(link_text)

            elif element.name in ('p', 'span', 'li', 'h1', 'h2', 'h3',
                                  'h4', 'h5', 'h6', 'strong', 'em', 'td', 'th'):
                # Capture direct text nodes of this element only (not its children),
                # so we don't duplicate text already captured from child <a> tags.
                direct_text = ''.join(
                    str(child) for child in element.children
                    if not hasattr(child, 'name')  # NavigableString only
                ).strip()
                if direct_text:
                    lines.append(direct_text)

        # De-duplicate while preserving order, then drop blank entries.
        seen = set()
        unique_lines = []
        for line in lines:
            normalised = line.strip()
            if normalised and normalised not in seen:
                seen.add(normalised)
                unique_lines.append(normalised)

        return '\n'.join(unique_lines)

    def scrape_website_content(self, url: str, description: str) -> Dict:
        """Scrape content from a single URL."""
        try:
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()

            if 'text/html' not in response.headers.get('Content-Type', ''):
                return None

            soup = BeautifulSoup(response.content, 'html.parser')

            # Capture footer text before discarding the tag.
            footer_text = self._extract_footer_text(soup)

            for element in soup(self._DISCARD_TAGS + ['footer']):
                element.decompose()

            main_content = (
                soup.find('main')
                or soup.find('article')
                or soup.find('div', class_=lambda x: x and ('content' in x.lower() or 'main' in x.lower()))
            )

            body_text = (main_content or soup).get_text(separator='\n', strip=True)
            body_lines = [line.strip() for line in body_text.split('\n') if line.strip()]
            body_text = '\n'.join(body_lines)

            # Append footer text as a clearly labelled section so it is stored
            # in the vector database as its own retrievable content.
            parts = [f"URL: {url}"]
            if description:
                parts.append(f"Description: {description}\n")
            parts.append(body_text)
            if footer_text:
                parts.append(f"\n--- Footer Information ---\n{footer_text}")

            full_content = '\n'.join(parts).strip()
            if not full_content:
                return None

            return {'url': url, 'content': full_content}

        except requests.RequestException as e:
            print(f"Failed to scrape {url}: {e}")
            return None
        except Exception as e:
            print(f"Error processing {url}: {e}")
            return None

    def scrape_all_websites(self, repo) -> List[Dict]:
        """Scrape content from all URLs stored in database."""
        url_data = self.get_urls_from_database(repo)
        if not url_data:
            return []

        all_content = []
        for item in url_data:
            result = self.scrape_website_content(item['url'], item['description'])
            if result:
                all_content.append({
                    'url': item['url'],
                    'description': item['description'],
                    'updated_at': item['updated_at'],
                    'content': result['content'],
                    'scraped_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                })
            time.sleep(2)

        return all_content

    def process_scraped_content(self, scraped_data: List[Dict], documents: List[str],
                                metadata: List[Dict], ids: List[str], text_splitter) -> None:
        """Process scraped website content into chunks."""
        for item in scraped_data:
            url = item['url']
            content = item['content']
            if not content.strip():
                continue

            url_id = (
                url.replace('https://', '').replace('http://', '')
                   .replace('/', '_').replace('.', '_').rstrip('_')
            )

            for idx, chunk in enumerate(text_splitter.split_text(content)):
                documents.append(chunk)
                ids.append(f"url_{url_id}_chunk_{idx}")
                metadata.append({
                    "source_url": url,
                    "data_type": "url",
                    "description": item.get('description', ''),
                    "scraped_at": item['scraped_at'],
                    "updated_at": (
                        item['updated_at'].strftime('%Y-%m-%d %H:%M:%S')
                        if item['updated_at'] else ''
                    ),
                    "chunk_index": idx,
                    "is_archived": False,
                    "document_version": "current",
                })