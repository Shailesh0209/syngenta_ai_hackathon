import asyncio
import os
import logging
import sys
import json
from sqlalchemy.ext.asyncio import create_async_engine
from sentence_transformers import SentenceTransformer
from utils.logging_config import setup_logging
from utils.cache_utils import setup_redis
from config.settings import schema, few_shot_examples
from agents.master_agent import MasterAgent

logger = logging.getLogger(__name__)

async def main():
    setup_logging()

    engine = create_async_engine(
        "postgresql+asyncpg://postgres:12345@localhost:5432/supply_chain",
        echo=False,
        pool_size=5,
        max_overflow=10,
    )

    embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

    redis_client = await setup_redis()

    api_key = ""
    url = "https://quchnti6xu7yzw7hfzt5yjqtvi0kafsq.lambda-url.eu-central-1.on.aws/"
    serper_api_key = ""

    master_agent = MasterAgent(
        engine=engine,
        embedding_model=embedding_model,
        schema=schema,
        few_shot_examples=few_shot_examples,
        api_key=api_key,
        url=url,
        serper_api_key=serper_api_key,
        redis_client=redis_client,
        intent_classifier=None  # Optional: Add a BERT classifier if available
    )

    while True:
        try:
            question = input("\nEnter your supply chain query (or 'exit' to quit): ").strip()
            if question.lower() == 'exit':
                logger.info("Exiting the application.")
                break

            response = await master_agent.handle_query(
                question=question,
                user_role="planning_manager",
                user_region="all"
            )
            print("\nProcessing your query...")
            print("*********************************", response)
            print(f"\nResponse (Latency: {response['latency_ms']:.2f} ms):")
            print(response["summary"])

            if response["charts"]:
                print("\nVisualizations:")
                for chart in response["charts"]:
                    print("Chart generated (view in UI).")

        except Exception as e:
            logger.error(f"Error processing query: {str(e)}")
            print(f"An error occurred: {str(e)}")

    await engine.dispose()
    await redis_client.close()

async def api_mode():
    setup_logging()

    engine = create_async_engine(
        "postgresql+asyncpg://postgres:12345@localhost:5432/supply_chain",
        echo=False,
        pool_size=5,
        max_overflow=10,
    )
    embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    redis_client = await setup_redis()
    master_agent = MasterAgent(
        engine=engine,
        embedding_model=embedding_model,
        schema=schema,
        few_shot_examples=few_shot_examples,
        api_key="",
        url="https://quchnti6xu7yzw7hfzt5yjqtvi0kafsq.lambda-url.eu-central-1.on.aws/",
        serper_api_key="",
        redis_client=redis_client,
        intent_classifier=None
    )
    # read payload, handle single query, output JSON, and exit
    payload = sys.stdin.read()
    data = json.loads(payload)
    resp = await master_agent.handle_query(
        question=data.get("query",""),
        user_role=data.get("user_role",""),
        user_region=data.get("user_region",""),
    )
    print(json.dumps(resp))
    await engine.dispose()
    await redis_client.close()

if __name__ == "__main__":
    if "--api-mode" in sys.argv:
        asyncio.run(api_mode())
    else:
        asyncio.run(main())