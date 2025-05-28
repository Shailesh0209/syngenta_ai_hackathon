
import json
import aiohttp
import asyncio
import logging
from cachetools import TTLCache
import hashlib

logger = logging.getLogger(__name__)

class BaseAgent:
    def __init__(self, api_key: str, url: str, serper_api_key: str, redis_client=None):
        self.api_key = api_key
        self.url = url
        self.serper_api_key = serper_api_key
        self.redis_client = redis_client
        self.llm_cache = TTLCache(maxsize=1000, ttl=7200)

    async def call_llm(self, prompt: str, model_id: str = "claude-3-haiku") -> dict:
        """
        Call the LLM with the specified prompt and model.
        Uses Claude 3 Haiku by default for efficiency.
        """
        prompt_hash = hashlib.md5(prompt.encode()).hexdigest()
        cache_key = f"llm:{prompt_hash}:{model_id}"
        
        # Check Redis cache first
        if self.redis_client:
            cached_result = await self.redis_client.get(cache_key)
            if cached_result:
                logger.info("LLM Redis cache hit")
                return json.loads(cached_result)

        # Check in-memory cache as fallback
        if cache_key in self.llm_cache:
            logger.info("LLM in-memory cache hit")
            return self.llm_cache[cache_key]

        # Construct payload matching the API's expected format
        payload = {
            "api_key": self.api_key,
            "prompt": prompt,
            "model_id": model_id,
            "model_params": {
                "max_tokens": 1000,
                "temperature": 0.7  # Added temperature for better response control
            }
        }
        headers = {
            "Content-Type": "application/json"
        }

        max_retries = 3
        retry_delay = 1

        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            for retry in range(max_retries):
                try:
                    async with session.post(self.url, headers=headers, json=payload) as response:
                        response_text = await response.text()
                        if response.status != 200:
                            logger.error(f"API request failed with status {response.status}: {response_text}")
                            return {"error": f"Bad request: {response_text}"}
                        result = json.loads(response_text)
                        logger.info(f"Raw API response: {result}")

                        # Parse the response according to the API's format
                        if "response" not in result or "content" not in result["response"]:
                            logger.error(f"Invalid API response format with model {model_id}: {result}")
                            return {"error": "Invalid API response format."}

                        full_response = result["response"]["content"][0]["text"].strip()
                        if not full_response:
                            logger.error(f"Empty response from LLM with model {model_id}")
                            return {"error": "Empty response from LLM."}

                        # Cache the result
                        if self.redis_client:
                            await self.redis_client.setex(cache_key, 7200, json.dumps(full_response))
                        self.llm_cache[cache_key] = full_response
                        return full_response

                except aiohttp.ClientResponseError as http_err:
                    if http_err.status == 429:
                        logger.warning(f"Rate limit hit with {model_id}, retrying in {retry_delay} seconds...")
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                    elif http_err.status == 401:
                        logger.error("Unauthorized: Invalid API key")
                        return {"error": "Unauthorized: Invalid API key."}
                    elif http_err.status == 400:
                        logger.error(f"Bad request: {http_err.message}")
                        return {"error": f"Bad request: {http_err.message}"}
                    else:
                        logger.error(f"HTTP error with {model_id}: {str(http_err)}")
                        return {"error": f"HTTP error: {str(http_err)}"}
                except Exception as e:
                    logger.error(f"Error in API request or response parsing with model {model_id}: {str(e)}")
                    return {"error": f"Error in API request: {str(e)}"}

            logger.error(f"Max retries reached for model {model_id}. Unable to get response.")
            return {"error": "Failed to get response from LLM after retries."}