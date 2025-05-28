
import re
import time
import asyncio
import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any, Tuple
from collections import deque
from sentence_transformers import SentenceTransformer, util
from tabulate import tabulate
from utils.validation_utils import validate_query
from .query_classifier_agent import QueryClassifierAgent
from .document_retrieval_agent import DocumentRetrievalAgent
from .sql_agent import SQLAgent
from .web_search_agent import WebSearchAgent
from .explanation_agent import ExplanationAgent
from .learning_module_agent import LearningModuleAgent
from .predictive_agent import PredictiveAgent

logger = logging.getLogger(__name__)

class MasterAgent:
    def __init__(self, engine, embedding_model: SentenceTransformer, schema: str, few_shot_examples: str, api_key: str, url: str, serper_api_key: str, redis_client, intent_classifier):
        self.engine = engine
        self.embedding_model = embedding_model
        self.intent_classifier = intent_classifier
        self.query_classifier = QueryClassifierAgent(redis_client)
        self.doc_retrieval = DocumentRetrievalAgent(engine, embedding_model, api_key, url, serper_api_key)
        self.sql_agent = SQLAgent(engine, schema, few_shot_examples, api_key, url, serper_api_key, redis_client)
        self.web_search = WebSearchAgent(api_key, url, serper_api_key)
        self.explanation = ExplanationAgent(api_key, url, serper_api_key, engine)
        self.learning_module = LearningModuleAgent(api_key, url, serper_api_key)
        self.predictive = PredictiveAgent(engine)
        self.redis_client = redis_client
        self.column_descriptions = {
            'segment': 'customer segment',
            'order_count': 'number of orders',
            'product_name': 'product name',
            'market': 'market (region)',
            'avg_late_risk': 'average late delivery risk',
            'order_date': 'order date',
            'running_profit': 'cumulative profit',
            'total_profit': 'total profit',
            'shipping_mode': 'shipping mode',
            'total_order_value': 'total order value',
            'customer_id': 'customer ID',
            'region': 'region',
            'total_sales': 'total sales amount',
            'on_time_delivery_rate': 'on-time delivery rate',
            'year': 'year'
        }
        self.common_questions = [
            "What is the total number of orders per customer segment?",
            "Which products had the highest late delivery risk by market?",
            "What is the total profit by customer segment in 2015?",
            "Which shipping mode has the highest average late delivery risk?",
            "Who are our top 10 customers by total order value?",
            "What is the distribution of orders by customer segment and region?",
            "Which shipping mode has the lowest rate of on-time deliveries?",
            "What are load optimization strategies in our logistics policy?",
            "What is the trend of late delivery risks over the years?"
        ]
        self.common_question_embeddings = self.embedding_model.encode(self.common_questions)
        self.conversation_memory = deque(maxlen=10)
        self.compliance_score = 100
        self.compliance_history = []
        self.badges = []
        self.query_count = 0
        self.successful_queries = 0
        self.user_id = "default_user"

    async def show_help_menu(self) -> str:
        help_text = """
Welcome to the Supply Chain Chatbot Help Menu!
Example Queries:
- What is the total number of orders per customer segment?
- What are load optimization strategies in our logistics policy?
- Predict the late delivery risk for LATAM in 2019.
Commands:
- Type 'exit' to quit.
- Type 'voice:' before your query to simulate voice input.
- Type 'help' to see this menu again.
- Type 'go back to query <number>' to revisit a past query (e.g., 'go back to query 1').
"""
        return help_text

    async def suggest_alternative_queries(self, question: str) -> List[str]:
        question_embedding = self.embedding_model.encode(question)
        similarities = util.cos_sim(question_embedding, self.common_question_embeddings)[0]
        top_indices = similarities.argsort(descending=True)[:3]
        suggestions = [self.common_questions[idx] for idx in top_indices]
        return suggestions

    async def infer_context(self, question: str) -> str:
        question_lower = question.lower()
        follow_up_keywords = ["it", "this", "that", "do we have policy", "are we following", "tell me more", "explain more"]
        if any(keyword in question_lower for keyword in follow_up_keywords) and self.conversation_memory:
            question_embedding = self.embedding_model.encode(question_lower)
            for past_entry in reversed(self.conversation_memory):
                past_question = past_entry["question"].lower()
                past_embedding = self.embedding_model.encode(past_question)
                similarity = util.cos_sim(question_embedding, past_embedding)[0].item()
                if similarity > 0.8:
                    if "sustainability" in past_question:
                        return f"Regarding sustainability practices: {question}"
                    elif "load optimization" in past_question:
                        return f"Regarding load optimization: {question}"
                    elif "cyber security" in past_question:
                        return f"Regarding cyber security measures: {question}"
                    elif "supplier" in past_question:
                        return f"Regarding supplier management: {question}"
                    elif "shipping" in past_question:
                        return f"Regarding shipping and logistics: {question}"
        return question

    async def generate_proactive_suggestions(self, user_role: str, last_question: str) -> List[str]:
        suggestions = []
        last_question_lower = last_question.lower()
        last_question_embedding = self.embedding_model.encode(last_question_lower)
        suggestion_candidates = [
            "Would you like to see the distribution of orders by customer segment and region?",
            "Would you like to know which shipping mode has the highest average late delivery risk?",
            "Would you like to explore our Transportation and Logistics policy for optimal shipping modes?",
            "Would you like to see the total profit by customer segment for a specific year?",
            "Would you like to learn more about load optimization strategies?",
            "Would you like to see the trend of late delivery risks over the years?"
        ]
        suggestion_embeddings = self.embedding_model.encode(suggestion_candidates)
        similarities = util.cos_sim(last_question_embedding, suggestion_embeddings)[0]
        filtered_indices = [i for i, sim in enumerate(similarities) if sim < 0.95]
        if filtered_indices:
            top_indices = similarities[filtered_indices].argsort(descending=True)[:2]
            suggestions = [suggestion_candidates[i] for i in top_indices]

        if "finance_manager" in user_role and "profit" not in last_question_lower:
            suggestions.append("Would you like to see the total profit by customer segment for a specific year?")
        if "logistics_specialist" in user_role and "shipping" not in last_question_lower:
            suggestions.append("Would you like to explore our Transportation and Logistics policy for optimal shipping modes?")

        return suggestions[:3]

    async def update_leaderboard(self) -> int:
        await self.redis_client.zadd("leaderboard", {self.user_id: self.compliance_score})
        rank = await self.redis_client.zrevrank("leaderboard", self.user_id)
        return rank + 1 if rank is not None else 1

    async def award_badge(self):
        self.query_count += 1
        if self.query_count == 5:
            self.badges.append("Explorer: Asked 5 questions")
            return "Congratulations! You've earned the 'Explorer' badge for asking 5 questions!"
        if self.successful_queries == 3:
            self.badges.append("Achiever: 3 successful queries in a row")
            return "Great job! You've earned the 'Achiever' badge for 3 successful queries in a row!"
        if self.query_count == 10 and "Policy Expert" not in [badge.split(":")[0] for badge in self.badges]:
            policy_queries = sum(1 for entry in self.conversation_memory if "policy" in entry["question"].lower())
            if policy_queries >= 5:
                self.badges.append("Policy Expert: Asked 5 policy-related questions")
                return "Awesome! You've earned the 'Policy Expert' badge for asking 5 policy-related questions!"
        return None

    async def handle_query(
        self,
        question: str,
        top_k: int = 5,
        filters: Optional[Dict[str, str]] = None,
        simplify: bool = False,
        user_role: str = "supply_chain_manager",
        user_region: str = "all"
    ) -> Dict[str, Any]:
        start_time = time.time()

        response = {
            "status": "success",
            "question": question,
            "document_results": [],
            "document_summary": "",
            "sql_results": [],
            "sql_query": "",
            "prediction_results": [],
            "explanation": "",
            "learning_content": "",
            "summary": "",
            "charts": [],
            "errors": [],
            "latency_ms": 0.0,
            "suggestions": [],
            "audit_log": "",
            "compliance_score": self.compliance_score,
            "proactive_suggestions": [],
            "badges": [],
            "leaderboard_position": 0
        }

        # Handle "go back to query" command
        go_back_match = re.match(r"go back to query (\d+)", question.lower())
        if go_back_match:
            query_index = int(go_back_match.group(1)) - 1
            if 0 <= query_index < len(self.conversation_memory):
                past_entry = list(self.conversation_memory)[query_index]
                response["summary"] = f"Revisiting query {query_index + 1}: {past_entry['question']}\n{past_entry['response']}"
                end_time = time.time()
                response["latency_ms"] = (end_time - start_time) * 1000
                return response
            else:
                response["errors"].append("Invalid query number. Please check your conversation history.")
                response["status"] = "error"

        # Strip "voice:" prefix but don't add to summary
        original_question = question
        if question.lower().startswith("voice:"):
            question = question[6:].strip()

        contextual_question = await self.infer_context(question)
        if contextual_question != question:
            question = contextual_question

        is_valid, error_message = validate_query(question, self.compliance_score, self.compliance_history)
        if not is_valid:
            response["errors"].append(error_message)
            response["summary"] = error_message
            response["status"] = "error"
            suggestions = await self.suggest_alternative_queries(question)
            response["suggestions"] = suggestions
            response["summary"] += f"\nSuggestions: {', '.join(suggestions)}"
            end_time = time.time()
            response["latency_ms"] = (end_time - start_time) * 1000
            return response

        query_type = await self.query_classifier.classify_query(question)
        logger.info(f"Query intent classification: {query_type}")

        # Split query into parts for hybrid queries
        query_parts = [part.strip() for part in question.split(" and ") if part.strip()]
        if len(query_parts) > 1 and (query_type["requires_sql"] and query_type["requires_retrieval"]):
            logger.info(f"Processing hybrid query with parts: {query_parts}")
            # Process SQL part
            sql_part = next((part for part in query_parts if "top" in part.lower() or "order value" in part.lower()), None)
            if sql_part and query_type["requires_sql"]:
                sql_result = await self.sql_agent.execute_sql_query(sql_part, simplify=simplify, user_role=user_role, user_region=user_region)
                if isinstance(sql_result, dict) and "error" not in sql_result:
                    response["sql_results"] = sql_result["results"]
                    response["sql_query"] = sql_result["sql_query"].replace("\n", " ")
                    response["audit_log"] = f"Access attempt logged: User role '{user_role}' executed SQL query successfully."
                    self.compliance_score += 2
                    self.compliance_history.append("Successful SQL query (+2 points)")
                    self.successful_queries += 1
                elif isinstance(sql_result, dict) and "error" in sql_result:
                    response["errors"].append(sql_result["error"])
                    response["audit_log"] = f"Access attempt logged: {sql_result['error']}"
                    self.compliance_score -= 3
                    self.compliance_history.append("SQL access violation (-3 points)")
                else:
                    response["errors"].append(f"SQL execution failed: {str(sql_result)}")

            # Process retrieval part
            retrieval_part = next((part for part in query_parts if "sustainability" in part.lower() or "policy" in part.lower()), None)
            if retrieval_part and query_type["requires_retrieval"]:
                doc_result = await self.doc_retrieval.retrieve_documents(retrieval_part, top_k, filters, min_similarity=0.2, user_role=user_role)
                if isinstance(doc_result, dict) and "error" not in doc_result:
                    response["document_results"] = doc_result
                    response["document_summary"] = await self.doc_retrieval.summarize_documents(response["document_results"], retrieval_part)
                    response["audit_log"] += f"\nAccess attempt logged: User role '{user_role}' accessed documents successfully."
                    self.compliance_score += 2
                    self.compliance_history.append("Successful document access (+2 points)")
                elif isinstance(doc_result, dict) and "error" in doc_result:
                    response["errors"].append(doc_result["error"])
                    response["audit_log"] += f"\nAccess attempt logged: {doc_result['error']}"
                    self.compliance_score -= 3
                    self.compliance_history.append("Access violation (-3 points)")
                else:
                    response["errors"].append(f"Document retrieval failed: {str(doc_result)}")
        else:
            # Handle single-intent queries
            if not query_type["requires_retrieval"] and not query_type["requires_sql"]:
                self.compliance_score -= 2
                self.compliance_history.append("Unrelated query intent (-2 points)")
                response["errors"].append("The question doesn't seem to require data retrieval or SQL querying. Please ask a supply chain-related question.")
                response["summary"] = "The question doesn't seem to require data retrieval or SQL querying. Please ask a supply chain-related question."
                response["status"] = "error"
                suggestions = await self.suggest_alternative_queries(question)
                response["suggestions"] = suggestions
                response["summary"] += f"\nSuggestions: {', '.join(suggestions)}"
                end_time = time.time()
                response["latency_ms"] = (end_time - start_time) * 1000
                return response

            learning_topic = None
            question_lower = question.lower()
            if "what is" in question_lower and ("load optimization" in question_lower or "sustainability" in question_lower):
                topic_match = re.search(r'what is (load optimization|sustainability)\?', question_lower)
                if topic_match:
                    learning_topic = topic_match.group(1)

            # Parallelize independent tasks
            doc_task = self.doc_retrieval.retrieve_documents(question, top_k, filters, min_similarity=0.2, user_role=user_role) if query_type["requires_retrieval"] else asyncio.sleep(0)
            web_task = self.web_search.web_search(f"{question} supply chain context") if query_type["requires_explanation"] else asyncio.sleep(0)
            learning_task = self.learning_module.provide_learning_content(learning_topic) if learning_topic else asyncio.sleep(0)
            doc_result, web_search_result, learning_content = await asyncio.gather(doc_task, web_task, learning_task)

            # Dependent task: SQL query
            sql_result = await self.sql_agent.execute_sql_query(question, simplify=simplify, user_role=user_role, user_region=user_region) if query_type["requires_sql"] else None

            if learning_topic:
                response["learning_content"] = learning_content
                response["summary"] += f"\nLearning Module:\n{learning_content}\n"

            web_search_knowledge = ""
            if query_type["requires_explanation"]:
                web_search_knowledge = web_search_result
                if isinstance(web_search_knowledge, Exception):
                    response["errors"].append(f"Web search failed: {str(web_search_knowledge)}")
                elif "Failed" in web_search_knowledge:
                    web_search_knowledge = "No external knowledge available due to a web search error."

            if query_type["requires_retrieval"]:
                if isinstance(doc_result, Exception):
                    response["errors"].append(f"Document retrieval failed: {str(doc_result)}")
                elif isinstance(doc_result, dict) and "error" in doc_result:
                    self.compliance_score -= 3
                    self.compliance_history.append("Access violation (-3 points)")
                    response["errors"].append(doc_result["error"])
                    response["audit_log"] = f"Access attempt logged: {doc_result['error']}"
                    response["suggestions"] = [
                        "Try querying operational data like order counts or shipping details.",
                        "Would you like to explore logistics policies instead?"
                    ]
                elif doc_result:
                    response["document_results"] = doc_result
                    doc_summary = await self.doc_retrieval.summarize_documents(doc_result, question)
                    response["document_summary"] = doc_summary
                    response["audit_log"] = f"Access attempt logged: User role '{user_role}' accessed documents successfully."
                    self.compliance_score += 2
                    self.compliance_history.append("Successful document access (+2 points)")
                else:
                    response["errors"].append("I couldn't find any relevant documents for your query.")

            prediction_results = None
            if query_type["requires_sql"]:
                if isinstance(sql_result, Exception):
                    response["errors"].append(f"SQL execution failed: {str(sql_result)}")
                elif isinstance(sql_result, dict) and "error" in sql_result:
                    if "complexity_feedback" in sql_result:
                        response["errors"].append(sql_result["error"])
                        response["summary"] = f"{sql_result['error']} Automatically simplifying the query..."
                        response["status"] = "error"
                        sql_result = await self.sql_agent.execute_sql_query(question, simplify=True, user_role=user_role, user_region=user_region)
                        if isinstance(sql_result, dict) and "error" not in sql_result:
                            response["sql_results"] = sql_result["results"]
                            response["sql_query"] = sql_result["sql_query"].replace("\n", " ")
                    elif "requires_prediction" in sql_result:
                        market_match = re.search(r'in (\w+(?:\s+\w+)*)\s+in\s+\d{4}', question)
                        year_match = re.search(r'\b(\d{4})\b', question)
                        if market_match and year_match:
                            market = market_match.group(1)
                            year = int(year_match.group(1))
                            prediction_results = await self.predictive.predict_late_delivery_risk(market, year)
                            if prediction_results:
                                response["prediction_results"] = prediction_results
                            else:
                                response["errors"].append(f"Failed to predict late delivery risk for {market} in {year}")
                        else:
                            response["errors"].append("Could not extract market or year from the question for prediction")
                    else:
                        self.compliance_score -= 3
                        self.compliance_history.append("SQL access violation (-3 points)")
                        response["errors"].append(sql_result["error"])
                        response["audit_log"] = f"Access attempt logged: {sql_result['error']}"
                        response["suggestions"] = [
                            "Try querying operational data like order counts or shipping details.",
                            "Would you like to explore logistics policies instead?"
                        ]
                else:
                    response["sql_results"] = sql_result["results"]
                    response["sql_query"] = sql_result["sql_query"].replace("\n", " ")
                    response["audit_log"] = f"Access attempt logged: User role '{user_role}' executed SQL query successfully."
                    self.compliance_score += 2
                    self.compliance_history.append("Successful SQL query (+2 points)")
                    self.successful_queries += 1

        # Chart generation for SQL results
        if response["sql_results"]:
            if "segment" in response["sql_results"][0] and "total_order_value" in response["sql_results"][0]:
                labels = [row["segment"] for row in response["sql_results"]]
                values = [row["total_order_value"] for row in response["sql_results"]]
                chart = {
                    "type": "pie",
                    "data": {
                        "labels": labels,
                        "datasets": [{
                            "label": "Total Order Value ($)",
                            "data": values,
                            "backgroundColor": ["#4CAF50", "#2196F3", "#FF9800", "#F44336", "#9C27B0"],
                            "borderColor": ["#388E3C", "#1976D2", "#F57C00", "#D32F2F", "#7B1FA2"],
                            "borderWidth": 1
                        }]
                    },
                    "options": {
                        "plugins": {
                            "legend": {
                                "display": True,
                                "position": "right"
                            },
                            "title": {
                                "display": True,
                                "text": "Total Order Value by Customer Segment"
                            }
                        }
                    }
                }
                response["charts"].append(chart)
            elif "segment" in response["sql_results"][0] and "region" in response["sql_results"][0] and "order_count" in response["sql_results"][0]:
                df = pd.DataFrame(response["sql_results"])
                segments = df["segment"].unique()
                regions = df["region"].unique()
                datasets = []
                colors = ["#4CAF50", "#2196F3", "#FF9800", "#F44336", "#9C27B0"]
                for i, segment in enumerate(segments):
                    segment_data = df[df["segment"] == segment]
                    values = []
                    for region in regions:
                        value = segment_data[segment_data["region"] == region]["order_count"].values
                        values.append(float(value[0]) if value else 0)
                    datasets.append({
                        "label": segment,
                        "data": values,
                        "backgroundColor": colors[i % len(colors)],
                        "borderColor": colors[i % len(colors)],
                        "borderWidth": 1
                    })
                chart = {
                    "type": "bar",
                    "data": {
                        "labels": list(regions),
                        "datasets": datasets
                    },
                    "options": {
                        "scales": {
                            "y": {
                                "beginAtZero": True,
                                "title": {
                                    "display": True,
                                    "text": "Number of Orders"
                                }
                            },
                            "x": {
                                "title": {
                                    "display": True,
                                    "text": "Region"
                                }
                            }
                        },
                        "plugins": {
                            "legend": {
                                "display": True,
                                "position": "top"
                            },
                            "title": {
                                "display": True,
                                "text": "Distribution of Orders by Customer Segment and Region"
                            }
                        }
                    }
                }
                response["charts"].append(chart)
            elif "customer_id" in response["sql_results"][0] and "total_order_value" in response["sql_results"][0]:
                labels = [f"Customer {row['customer_id']}" for row in response["sql_results"]]
                values = [row["total_order_value"] for row in response["sql_results"]]
                chart = {
                    "type": "bar",
                    "data": {
                        "labels": labels,
                        "datasets": [{
                            "label": "Total Order Value ($)",
                            "data": values,
                            "backgroundColor": ["#4CAF50", "#2196F3", "#FF9800", "#F44336", "#9C27B0", "#673AB7", "#FF5722", "#795548", "#607D8B", "#E91E63"],
                            "borderColor": ["#388E3C", "#1976D2", "#F57C00", "#D32F2F", "#7B1FA2", "#512DA8", "#E64A19", "#5D4037", "#455A64", "#C2185B"],
                            "borderWidth": 1
                        }]
                    },
                    "options": {
                        "scales": {
                            "y": {
                                "beginAtZero": True,
                                "title": {
                                    "display": True,
                                    "text": "Total Order Value ($)"
                                }
                            },
                            "x": {
                                "title": {
                                    "display": True,
                                    "text": "Customer"
                                }
                            }
                        },
                        "plugins": {
                            "legend": {
                                "display": False
                            },
                            "title": {
                                "display": True,
                                "text": "Top 10 Customers by Total Order Value"
                            }
                        }
                    }
                }
                response["charts"].append(chart)
            elif "year" in response["sql_results"][0] and "avg_late_risk" in response["sql_results"][0]:
                labels = [str(row["year"]) for row in response["sql_results"]]
                values = [row["avg_late_risk"] for row in response["sql_results"]]
                chart = {
                    "type": "line",
                    "data": {
                        "labels": labels,
                        "datasets": [{
                            "label": "Average Late Delivery Risk",
                            "data": values,
                            "borderColor": "#4CAF50",
                            "backgroundColor": "rgba(76, 175, 80, 0.2)",
                            "fill": True,
                            "tension": 0.3
                        }]
                    },
                    "options": {
                        "scales": {
                            "y": {
                                "beginAtZero": True,
                                "title": {
                                    "display": True,
                                    "text": "Average Late Delivery Risk"
                                }
                            },
                            "x": {
                                "title": {
                                    "display": True,
                                    "text": "Year"
                                }
                            }
                        },
                        "plugins": {
                            "legend": {
                                "display": True
                            },
                            "title": {
                                "display": True,
                                "text": "Trend of Late Delivery Risks Over Years"
                            }
                        }
                    }
                }
                response["charts"].append(chart)

        # Chart generation for prediction results
        if response["prediction_results"]:
            labels = [row["shipping_mode"] for row in response["prediction_results"]]
            values = [row["avg_predicted_late_risk"] for row in response["prediction_results"]]
            chart = {
                "type": "bar",
                "data": {
                    "labels": labels,
                    "datasets": [{
                        "label": "Predicted Late Delivery Risk",
                        "data": values,
                        "backgroundColor": ["#4CAF50", "#2196F3", "#FF9800", "#F44336"],
                        "borderColor": ["#388E3C", "#1976D2", "#F57C00", "#D32F2F"],
                        "borderWidth": 1
                    }]
                },
                "options": {
                    "scales": {
                        "y": {
                            "beginAtZero": True,
                            "title": {
                                "display": True,
                                "text": "Predicted Risk"
                            }
                        },
                        "x": {
                            "title": {
                                "display": True,
                                "text": "Shipping Mode"
                            }
                        }
                    },
                    "plugins": {
                        "title": {
                            "display": True,
                            "text": "Predicted Late Delivery Risks by Shipping Mode"
                        }
                    }
                }
            }
            response["charts"].append(chart)

        # Explanation for SQL and prediction results
        if (query_type["requires_sql"] and (response["sql_results"] or response["prediction_results"]) and query_type["requires_explanation"]) or prediction_results:
            response["explanation"] = await self.explanation.explain_sql_results(
                response["sql_query"],
                response["sql_results"],
                response["document_results"],
                question,
                web_search_knowledge,
                response["prediction_results"]
            )

        # Build the response summary
        summary_parts = []
        if response["document_summary"]:
            summary_parts.append(f"Policy Insights:\n{response['document_summary']}")
        elif response["document_results"]:
            doc_summary = []
            for res in response["document_results"]:
                chunk = res['chunk'].replace("\n", " ").strip()
                doc_summary.append(f"- From {res['file_name']} (Doc ID {res['doc_id']}, Chunk ID {res['chunk_id']}): {chunk[:200]}... (Similarity: {res['similarity']:.4f})")
            summary_parts.append("Relevant policies and documents:\n" + "\n".join(doc_summary))

        if response["sql_results"]:
            table_data = []
            headers = list(response["sql_results"][0].keys())
            for row in response["sql_results"][:5]:
                formatted_row = []
                for key, value in row.items():
                    if isinstance(value, float) and ("profit" in key.lower() or "total_order_value" in key.lower() or "total_sales" in key.lower()):
                        formatted_row.append(f"${value:,.2f}")
                    elif "avg_late_risk" in key or "on_time_delivery_rate" in key:
                        formatted_row.append(f"{float(value):.3f}")
                    else:
                        formatted_row.append(str(value))
                table_data.append(formatted_row)
            table = tabulate(table_data, headers=[self.column_descriptions.get(h, h) for h in headers], tablefmt="grid")
            summary_parts.append(f"Database results:\n{table}")
            if response["charts"]:
                summary_parts.append("Check out the chart below to visualize the results!")

        if response["prediction_results"]:
            pred_table_data = []
            for res in response["prediction_results"][:5]:
                pred_table_data.append([res["shipping_mode"], f"{res['avg_predicted_late_risk']:.3f}"])
            pred_table = tabulate(pred_table_data, headers=["Shipping Mode", "Avg Predicted Late Risk"], tablefmt="grid")
            summary_parts.append(f"Predicted late delivery risks:\n{pred_table}")

        if response["explanation"]:
            cleaned_explanation = response["explanation"].replace("\n", " ")
            summary_parts.append(f"Explanation and insights: {cleaned_explanation}")

        if response["sql_query"]:
            summary_parts.append(f"SQL query used: {response['sql_query']}")

        if summary_parts:
            response["summary"] = "\n".join(summary_parts)
        else:
            response["summary"] = "I couldn't find any relevant results. Could you try rephrasing your question?"

        # Add suggestions and metadata separately, to be filtered out by main.py
        if response["errors"]:
            response["status"] = "error"
            if response["suggestions"]:
                response["summary"] += f"\nSuggestions: {', '.join(response['suggestions'])}"

        if response["audit_log"]:
            response["summary"] += f"\n{response['audit_log']}"

        proactive_suggestions = await self.generate_proactive_suggestions(user_role, question)
        if proactive_suggestions:
            response["proactive_suggestions"] = proactive_suggestions
            response["summary"] += f"\nProactive Suggestions: {', '.join(proactive_suggestions)}"

        badge_message = await self.award_badge()
        if badge_message:
            response["badges"].append(badge_message)
            response["summary"] += f"\n{badge_message}"

        response["leaderboard_position"] = await self.update_leaderboard()
        response["summary"] += f"\nLeaderboard Position: {response['leaderboard_position']}"
        response["compliance_score"] = self.compliance_score
        response["summary"] += f"\nCompliance Score: {self.compliance_score}"

        self.conversation_memory.append({
            "question": original_question,
            "response": response["summary"]
        })

        end_time = time.time()
        response["latency_ms"] = (end_time - start_time) * 1000
        return response