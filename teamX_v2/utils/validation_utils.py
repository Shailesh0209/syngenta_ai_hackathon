import re
import logging
from typing import Tuple, List

logger = logging.getLogger(__name__)

def validate_query(query: str, compliance_score: int, compliance_history: List[str]) -> Tuple[bool, str]:
    query_lower = query.lower()

    inappropriate_words = ["drop", "delete", "truncate", "insert", "update"]
    if any(word in query_lower for word in inappropriate_words):
        compliance_score -= 5
        compliance_history.append("Inappropriate query keyword detected (-5 points)")
        logger.warning(f"Inappropriate query detected: {query}")
        return False, "Query contains inappropriate keywords that could harm the database. Please revise your question."

    if len(query) < 5:
        compliance_score -= 1
        compliance_history.append("Query too short (-1 point)")
        logger.warning(f"Query too short: {query}")
        return False, "Your query is too short. Please provide a more detailed question."

    if not re.search(r'[a-zA-Z]', query):
        compliance_score -= 1
        compliance_history.append("Query lacks alphabetic characters (-1 point)")
        logger.warning(f"Query lacks alphabetic characters: {query}")
        return False, "Your query must contain alphabetic characters to be meaningful."

    return True, ""