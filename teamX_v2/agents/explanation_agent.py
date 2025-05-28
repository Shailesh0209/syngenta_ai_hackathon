import logging
from typing import List, Dict, Optional, Any
from cachetools import TTLCache
from .base_agent import BaseAgent
from .predictive_agent import PredictiveAgent

logger = logging.getLogger(__name__)

class ExplanationAgent(BaseAgent):
    def __init__(self, api_key: str, url: str, serper_api_key: str, engine):
        super().__init__(api_key, url, serper_api_key)
        self.explanation_cache = TTLCache(maxsize=1000, ttl=7200)
        self.predictive_agent = PredictiveAgent(engine)

    async def explain_sql_results(
        self,
        sql_query: str,
        sql_results: List[Dict[str, Any]],
        document_results: List[Dict[str, Any]],
        question: str,
        web_search_knowledge: str,
        prediction_results: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        cache_key = (sql_query, str(sql_results), str(document_results), question, str(prediction_results))
        if cache_key in self.explanation_cache:
            logger.info("Explanation cache hit")
            return self.explanation_cache[cache_key]

        if not sql_results and not document_results and not prediction_results:
            return "I couldn't find any results to explain. Let's try a different query!"

        sql_results_str = " ".join([str(row) for row in sql_results[:5]]) if sql_results else "No SQL results available."
        doc_results_str = " ".join([f"Document ID {res['doc_id']}, Chunk ID {res['chunk_id']} from {res['file_name']}: {res['chunk']}" for res in document_results]) if document_results else "No document retrieval results available."
        prediction_str = " ".join([f"Shipping Mode: {res['shipping_mode']}, Predicted Late Delivery Risk: {res['avg_predicted_late_risk']:.3f}" for res in prediction_results]) if prediction_results else ""

        prompt = f"""
Explain the query results for the question: "{question}"

SQL Query:
{sql_query}

SQL Results (up to 5 rows):
{sql_results_str}

Document Chunks:
{doc_results_str}

Predicted Results:
{prediction_str}

External Knowledge:
{web_search_knowledge}

Tasks:
1. Explain the SQL results: describe the data, highlight trends, and suggest business implications.
2. Analyze document results: highlight key points and actionable insights.
3. Explain predicted late delivery risks (if any) and their implications.
4. Provide 2-3 actionable business recommendations.

Return the explanation as plain text.
"""
        explanation = await self.call_llm(prompt)
        if isinstance(explanation, dict) and "error" in explanation:
            explanation = f"Failed to generate explanation: {explanation['error']}. Let's try a different approach!"
        if not explanation or "Failed" in explanation:
            explanation = "I couldn't generate an explanation due to an error with the language model. Here's the raw data instead."

        explanation = explanation.replace("\n", " ")
        self.explanation_cache[cache_key] = explanation
        return explanation