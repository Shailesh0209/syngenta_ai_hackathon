import logging
import os
from config.settings import AUDIT_LOG_FILE

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("app.log"),
            logging.StreamHandler()
        ]
    )

    audit_handler = logging.FileHandler(AUDIT_LOG_FILE)
    audit_handler.setLevel(logging.INFO)
    audit_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
    audit_logger = logging.getLogger('audit')
    audit_logger.addHandler(audit_handler)
    audit_logger.setLevel(logging.INFO)

    return audit_logger