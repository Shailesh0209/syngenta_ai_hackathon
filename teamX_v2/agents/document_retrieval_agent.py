import time
import logging
from typing import Dict, List, Optional, Any
from functools import lru_cache
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import text
from sentence_transformers import SentenceTransformer, util
from cachetools import TTLCache
from config.settings import USER_ROLES, ROLE_HIERARCHY
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)

class DocumentRetrievalAgent(BaseAgent):
    def __init__(self, engine, embedding_model: SentenceTransformer, api_key: str, url: str, serper_api_key: str):
        super().__init__(api_key, url, serper_api_key)
        self.engine = engine
        self.embedding_model = embedding_model
        self.retrieval_cache = TTLCache(maxsize=5000, ttl=7200)

    @lru_cache(maxsize=2000)
    async def embed_query(self, query: str) -> Optional[List[float]]:
        try:
            start_time = time.time()
            embedding = self.embedding_model.encode(query, batch_size=32).tolist()
            end_time = time.time()
            logger.info(f"Embedding latency: {(end_time - start_time) * 1000:.2f} ms")
            return embedding
        except Exception as e:
            logger.error(f"Error in embedding query: {str(e)}")
            return None

    async def retrieve_documents(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, str]] = None,
        min_similarity: float = 0.2,
        user_role: str = "supply_chain_manager"
    ) -> List[Dict[str, Any]]:
        cache_key = (query, frozenset(filters.items()) if filters else None)
        if cache_key in self.retrieval_cache:
            logger.info("Retrieval cache hit")
            return self.retrieval_cache[cache_key]

        effective_permissions = USER_ROLES.get(user_role, {}).copy()
        if user_role in ROLE_HIERARCHY:
            for sub_role in ROLE_HIERARCHY[user_role]:
                sub_permissions = USER_ROLES.get(sub_role, {})
                effective_permissions["allowed_data"] = list(set(effective_permissions.get("allowed_data", []) + sub_permissions.get("allowed_data", [])))
                effective_permissions["sensitive_data_access"] = effective_permissions.get("sensitive_data_access", False) or sub_permissions.get("sensitive_data_access", False)

        if not effective_permissions:
            return {"error": "Access restricted: Invalid user role."}

        start_time = time.time()
        query_embedding = await self.embed_query(query)
        if query_embedding is None:
            logger.error("Failed to generate query embedding")
            return {"error": "Failed to process the query for document retrieval due to an embedding error."}

        query_embedding_str = str(query_embedding)

        sql_query = """
            SELECT doc_id, chunk_id, file_name, chunk, metadata,
                (embedding <=> CAST(:query_embedding AS VECTOR)) as distance
            FROM document_embeddings_384
        """
        params = {"query_embedding": query_embedding_str, "top_k": top_k}

        if filters:
            conditions = []
            if "doc_id" in filters:
                conditions.append("doc_id = :doc_id")
                params["doc_id"] = filters["doc_id"]
            if "file_name" in filters:
                conditions.append("file_name = :file_name")
                params["file_name"] = filters["file_name"]
            if conditions:
                sql_query += " WHERE " + " AND ".join(conditions)

        sql_query += " ORDER BY embedding <=> CAST(:query_embedding AS VECTOR) LIMIT :top_k"

        try:
            db_start_time = time.time()
            async with AsyncSession(self.engine) as session:
                result = await session.execute(text(sql_query), params)
                results = []
                for row in result.mappings():
                    similarity = 1 - row['distance']
                    if similarity < min_similarity:
                        continue
                    file_name = row['file_name'].lower()
                    if "finance" in user_role.lower() and "finance" not in file_name:
                        return {"error": f"Access restricted: Finance manager can only access financial documents. Role description: {effective_permissions['description']}"}
                    elif "logistics" in user_role.lower() and "logistics" not in file_name and "shipping" not in file_name:
                        return {"error": f"Access restricted: Logistics specialist can only access logistics documents. Role description: {effective_permissions['description']}"}
                    elif "supplier" in user_role.lower() and "supplier" not in file_name:
                        return {"error": f"Access restricted: Supplier manager can only access supplier-related documents. Role description: {effective_permissions['description']}"}
                    else:
                        results.append({
                            'doc_id': row['doc_id'],
                            'chunk_id': row['chunk_id'],
                            'file_name': row['file_name'],
                            'chunk': row['chunk'],
                            'metadata': row['metadata'],
                            'similarity': similarity
                        })
            db_end_time = time.time()
            logger.info(f"Document retrieval latency: {(db_end_time - db_start_time) * 1000:.2f} ms")
        except Exception as e:
            logger.error(f"Error in document retrieval: {str(e)}")
            return {"error": f"Document retrieval failed: {str(e)}"}

        end_time = time.time()
        logger.info(f"Total retrieval latency: {(end_time - start_time) * 1000:.2f} ms")
        self.retrieval_cache[cache_key] = results
        return results

    async def summarize_documents(self, documents: List[Dict[str, Any]], query: str) -> str:
        if not documents or isinstance(documents, dict) and "error" in documents:
            return "No relevant documents found to summarize. Would you like to explore related topics?"

        doc_texts = [f"From {doc['file_name']}: {doc['chunk']}" for doc in documents]
        prompt = f"""
Given the following document chunks, summarize the information relevant to the query: "{query}".
Provide a concise natural language answer, citing the source documents where applicable.
If the documents do not directly answer the query, state that clearly and suggest related information.

Document Chunks:
{'\n'.join(doc_texts)}

Summary:
"""
        summary = await self.call_llm(prompt)
        if isinstance(summary, dict) and "error" in summary:
            return f"Failed to summarize documents: {summary['error']}"
        return summary.strip()