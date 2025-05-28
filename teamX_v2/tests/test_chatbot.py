import sys
import os
import asyncio
import pytest

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy.ext.asyncio import create_async_engine
from sentence_transformers import SentenceTransformer
from utils.cache_utils import setup_redis
from config.settings import schema, few_shot_examples
from agents.master_agent import MasterAgent

@pytest.mark.asyncio
async def test_chatbot_sql_query():
    engine = create_async_engine(
        "postgresql+asyncpg://postgres:12345@localhost:5437/supply_chain",
        echo=False,
    )
    embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    redis_client = await setup_redis()
    api_key = "syn-9e33c9c3-2d5d-4a5b-b7fa-e74f724aead8"
    url = "https://quchnti6xu7yzw7hfzt5yjqtvi0kafsq.lambda-url.eu-central-1.on.aws/"
    serper_api_key = "51a49488ce0d6549797b2cf6ab0326828663a368"

    master_agent = MasterAgent(
        engine=engine,
        embedding_model=embedding_model,
        schema=schema,
        few_shot_examples=few_shot_examples,
        api_key=api_key,
        url=url,
        serper_api_key=serper_api_key,
        redis_client=redis_client,
        intent_classifier=None
    )

    response = await master_agent.handle_query(
        question="Who are our top 10 customers by total order value?",
        user_role="global_operations_manager",
        user_region="all"
    )

    assert response["status"] == "success"
    assert "sql_results" in response
    assert len(response["sql_results"]) > 0
    assert "charts" in response
    assert len(response["charts"]) > 0

    await engine.dispose()
    await redis_client.close()

if __name__ == "__main__":
    asyncio.run(pytest.main(["-v", "tests/test_chatbot.py"]))