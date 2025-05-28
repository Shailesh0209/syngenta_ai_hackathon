import aiohttp
import time
import logging
from cachetools import TTLCache
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)

class WebSearchAgent(BaseAgent):
    def __init__(self, api_key: str, url: str, serper_api_key: str):
        super().__init__(api_key, url, serper_api_key)
        self.web_search_cache = TTLCache(maxsize=1000, ttl=7200)

    async def web_search(self, query: str) -> str:
        if query in self.web_search_cache:
            logger.info("Web search cache hit")
            return self.web_search_cache[query]

        url = "https://google.serper.dev/search"
        headers = {
            "X-API-KEY": self.serper_api_key,
            "Content-Type": "application/json"
        }
        payload = {
            "q": query,
            "num": 2
        }

        try:
            start_time = time.time()
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    response.raise_for_status()
                    result = await response.json()
            end_time = time.time()
            logger.info(f"Serper API latency: {(end_time - start_time) * 1000:.2f} ms")

            snippets = []
            if "organic" in result:
                for item in result["organic"][:2]:
                    if "snippet" in item:
                        snippets.append(item["snippet"])
            web_search_knowledge = " ".join(snippets) if snippets else "No relevant web search results found."
            self.web_search_cache[query] = web_search_knowledge
            return web_search_knowledge

        except Exception as e:
            logger.error(f"Error in Serper API request: {str(e)}")
            return "No external knowledge available due to a web search error."