import logging
from cachetools import TTLCache
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)

class LearningModuleAgent(BaseAgent):
    def __init__(self, api_key: str, url: str, serper_api_key: str):
        super().__init__(api_key, url, serper_api_key)
        self.learning_cache = TTLCache(maxsize=500, ttl=7200)

    async def provide_learning_content(self, topic: str) -> str:
        cache_key = f"learning:{topic}"
        if cache_key in self.learning_cache:
            logger.info("Learning module cache hit")
            return self.learning_cache[cache_key]

        prompt = f"""
Provide a brief educational explanation (100-150 words) on the supply chain topic: "{topic}".
Include a definition, its importance in supply chain management, and a simple example.
Format the response as plain text.

Topic: {topic}

Explanation:
"""
        content = await self.call_llm(prompt)
        if isinstance(content, dict) and "error" in content:
            content = f"Failed to generate learning content for {topic}: {content['error']}"
        self.learning_cache[cache_key] = content
        return content