
import logging
import json
import hashlib
from typing import Dict
from transformers import BertTokenizer, BertForSequenceClassification
import torch
from redis.asyncio import Redis

logger = logging.getLogger(__name__)

class QueryClassifierAgent:
    def __init__(self, redis_client: Redis):
        self.redis_client = redis_client
        self.tokenizer = BertTokenizer.from_pretrained('./bert_finetuned')
        self.model = BertForSequenceClassification.from_pretrained('./bert_finetuned')
        self.model.eval()
        self.intent_map = {0: "mixed", 1: "retrieval", 2: "sql", 3: "predictive", 4: "explanation"}

    async def classify_query(self, query: str) -> Dict[str, bool]:
        """
        Classify the query to determine the required processing steps.
        Handle hybrid queries by splitting on conjunctions like 'and'.
        """
        # Hash the query to create a safe cache key
        query_hash = hashlib.md5(query.encode()).hexdigest()
        cache_key = f"query_classification:{query_hash}"

        # Check Redis cache
        cached_result = await self.redis_client.get(cache_key)
        if cached_result:
            logger.info("Query classification Redis cache hit")
            return json.loads(cached_result)  # Parse the cached JSON string

        # Split query into parts if it contains 'and' (basic hybrid query detection)
        query_parts = [part.strip() for part in query.split(" and ") if part.strip()]
        if len(query_parts) > 1:
            logger.info(f"Detected hybrid query with {len(query_parts)} parts: {query_parts}")
        else:
            query_parts = [query]

        # Initialize intent flags
        classification = {
            "requires_retrieval": False,
            "requires_sql": False,
            "requires_predictive": False,
            "requires_explanation": False
        }

        # Classify each part using BERT
        intents = set()
        for part in query_parts:
            intent = await self._classify_single_query(part)
            intents.add(intent)
            logger.info(f"BERT classification result for part '{part}': {intent}")

        # Determine the combined intents
        for intent in intents:
            if intent in ["retrieval", "mixed"]:
                classification["requires_retrieval"] = True
            if intent in ["sql", "mixed"]:
                classification["requires_sql"] = True
            if intent == "predictive":
                classification["requires_predictive"] = True
            if intent == "explanation":
                classification["requires_explanation"] = True

        # Set requires_explanation for sql or mixed intents (as in the original logic)
        if "sql" in intents or "mixed" in intents:
            classification["requires_explanation"] = True

        # Cache the result as JSON
        await self.redis_client.setex(cache_key, 7200, json.dumps(classification))
        return classification

    async def _classify_single_query(self, query: str) -> str:
        """
        Classify a single query part using BERT.
        """
        # Tokenize and classify using BERT
        inputs = self.tokenizer(query, return_tensors="pt", padding=True, truncation=True, max_length=128)
        with torch.no_grad():
            outputs = self.model(**inputs)
        logits = outputs.logits
        predicted_class = torch.argmax(logits, dim=1).item()
        intent = self.intent_map.get(predicted_class, "retrieval")  # Default to retrieval if intent not in map
        return intent