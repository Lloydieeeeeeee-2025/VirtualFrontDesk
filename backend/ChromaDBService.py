import chromadb
import numpy as np
from typing import List
from openai import OpenAI
import os
from dotenv import load_dotenv


class ChromaDBService:
    """Handles ChromaDB vector database operations and embeddings."""

    def __init__(self):
        load_dotenv()
        self.openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.chroma_path = "chroma_db"
        self.collection_name = "tlcchatmate"
        self.embedding_model = "text-embedding-3-large"
        self._initialize_client()

    def _initialize_client(self) -> None:
        """Initialize ChromaDB persistent client."""
        self.client = chromadb.PersistentClient(path=self.chroma_path)

    def reinitialize_client(self) -> None:
        """Force reinitialize the ChromaDB client for clean state."""
        self._initialize_client()

    def get_collection(self, force_refresh=False):
        """Get collection with optional force refresh to see latest data."""
        if force_refresh:
            self.reinitialize_client()
        return self.client.get_or_create_collection(name=self.collection_name)

    def get_embedding(self, text: str) -> List[float]:
        """Get embedding vector for text using OpenAI API."""
        response = self.openai_client.embeddings.create(
            model=self.embedding_model,
            input=text
        )
        return response.data[0].embedding

    @staticmethod
    def calculate_cosine_similarity(vector1: List[float], vector2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        v1 = np.array(vector1)
        v2 = np.array(vector2)
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return np.dot(v1, v2) / (norm1 * norm2)

    def is_follow_up_question(self, current_prompt: str, previous_prompt: str,
                               similarity_threshold: float = 0.7) -> bool:
        """Check if current prompt is a follow-up to previous prompt."""
        if not previous_prompt:
            return False
        current_embedding = self.get_embedding(current_prompt)
        previous_embedding = self.get_embedding(previous_prompt)
        similarity = self.calculate_cosine_similarity(current_embedding, previous_embedding)
        return similarity > similarity_threshold