import chromadb

client = chromadb.PersistentClient(path="chroma_db")
collection = client.get_collection("tlcchatmate")

print(collection.get())

"""
import time
import requests
from typing import List
from bs4 import BeautifulSoup
from ChromaDBService import ChromaDBService

class KnowledgeRepository(ChromaDBService):
    def __init__(self):
        super().__init__()
        self.urls = [
            "https://thelewiscollege.edu.ph/",
            "https://thelewiscollege.edu.ph/programs/",
            "https://thelewiscollege.edu.ph/admissions/",
            "https://thelewiscollege.edu.ph/scholarships-2/",
            "https://thelewiscollege.edu.ph/apps/",
            "https://thelewiscollege.edu.ph/career/",
            "https://thelewiscollege.edu.ph/borad-of-trustee/",
            "https://thelewiscollege.edu.ph/school-admin/",
            "https://thelewiscollege.edu.ph/contact-us/",
            "https://thelewiscollege.edu.ph/mission-vision/"
        ]

    def fetch_page_text(self, url: str) -> str:
        try:
            response = requests.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            for script in soup(["script", "style"]):
                script.extract()
            text = soup.get_text(separator=' ', strip=True)
            return text
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return None

    def chunk_text(self, text: str, max_length: int = 1000) -> List[str]:
        chunks = []
        words = text.split()
        current_chunk = []
        for word in words:
            current_chunk.append(word)
            if len(' '.join(current_chunk)) > max_length:
                chunks.append(' '.join(current_chunk[:-1]))
                current_chunk = [word]
        if current_chunk:
            chunks.append(' '.join(current_chunk))
        return chunks

    def update_knowledge(self):
        collection = self.get_collection()
        for url in self.urls:
            text = self.fetch_page_text(url)
            if text:
                chunks = self.chunk_text(text)
                for i, chunk in enumerate(chunks):
                    embedding = self.get_embedding(chunk)
                    id_str = f"{url.replace('https://', '').replace('/', '_')}_{i}"
                    collection.upsert(
                        ids=[id_str],
                        embeddings=[embedding],
                        documents=[chunk],
                        metadatas=[{"url": url, "chunk": i}]
                    )
                print(f"Updated knowledge from {url} with {len(chunks)} chunks")


if __name__ == "__main__":
    repo = KnowledgeRepository()
    while True:
        print("Starting knowledge update...")
        repo.update_knowledge()
        print("Knowledge update completed. Sleeping for 24 hours...")
        time.sleep(86400)  # 24 hours2.6s
"""
