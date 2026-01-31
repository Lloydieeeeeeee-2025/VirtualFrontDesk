import chromadb
import numpy as np
from typing import List
from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

class ChromaDBService:

    def __init__(self):
        load_dotenv()
        self.openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.chroma_path = "chroma_db"
        self.collection_name = "tlcchatmate"
        self.embedding_model = "text-embedding-3-small"
        self._initialize_client()
        
    def _initialize_client(self) -> None:
        self.client = chromadb.PersistentClient(path=self.chroma_path)      
    
    def get_collection(self, force_refresh=False):
        """Get collection with optional force refresh to see latest data."""
        if force_refresh:
            # Reinitialize client to force reading from disk
            self._initialize_client()
        
        return self.client.get_or_create_collection(name=self.collection_name)
        
    def get_embedding(self, text: str) -> List[float]:
        response = self.openai_client.embeddings.create(
            model = self.embedding_model,
            input= text
        )
        return response.data[0].embedding
     
    @staticmethod    
    def calculate_cosine_similarity(vector1: List[float], vertor2: List[float]) -> float:
        vector1 = np.array(vector1)
        vector2 = np.array(vertor2)
        dot_product = np.dot(vector1, vector2)
        norm_vector1 = np.linalg.norm(vector1)
        norm_vector2 = np.linalg.norm(vector2)

        if norm_vector1 == 0 or norm_vector2 == 0:
            return 0.0
        
        return dot_product / (norm_vector1 * norm_vector2)
    
    def is_follow_up_question(self, current_prompt:str, previous_prompt:str, similarity_threshold: float = 0.7) -> bool:
        if not previous_prompt:
            return False
        
        current_embedding = self.get_embedding(current_prompt)
        previous_embedding = self.get_embedding(previous_prompt)
        similarity = self.calculate_cosine_similarity(current_embedding, previous_embedding)

        return similarity > similarity_threshold