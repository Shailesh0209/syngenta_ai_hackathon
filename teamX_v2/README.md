Supply Chain Chatbot
A chatbot for supply chain management, built for the Syngenta AI Agent Hackathon. It answers queries using document retrieval, SQL queries, web searches, predictions, and explanations.
Project Structure
supply_chain_chatbot/
├── agents/                          # Agent classes for different functionalities
│   ├── __init__.py
│   ├── base_agent.py
│   ├── query_classifier_agent.py
│   ├── document_retrieval_agent.py
│   ├── sql_agent.py
│   ├── web_search_agent.py
│   ├── predictive_agent.py
│   ├── explanation_agent.py
│   ├── learning_module_agent.py
│   ├── master_agent.py
├── config/                         # Configuration files
│   ├── __init__.py
│   ├── settings.py
├── utils/                         # Utility functions
│   ├── __init__.py
│   ├── logging_config.py
│   ├── cache_utils.py
│   ├── validation_utils.py
├── main.py                        # Entry point
├── requirements.txt               # Dependencies
└── README.md                      # Documentation

Prerequisites

Python 3.9+
PostgreSQL (running on localhost:5437)
Redis (running on localhost:6379)
A supply_chain database with the schema defined in config/settings.py
Pre-trained predictive model files (late_delivery_model.joblib, le_market.joblib, le_shipping_mode.joblib, le_product_name.joblib)

Setup

Clone the Repository:
git clone <repository-url>
cd supply_chain_chatbot


Install Dependencies:
pip install -r requirements.txt


Set Up Environment Variables:Create a .env file or set the following environment variables:
export API_KEY="your-api-key"
export LLM_URL="https://api.example.com/llm"
export SERPER_API_KEY="your-serper-api-key"


Set Up the Database:

Ensure PostgreSQL is running on localhost:5437.
Create a database named supply_chain.
Apply the schema and indexes from config/settings.py.


Ensure Predictive Model Files:

Place the late_delivery_model.joblib, le_market.joblib, le_shipping_mode.joblib, and le_product_name.joblib files in the project root.


Run Redis:Ensure Redis is running on localhost:6379.


Running the Application
python main.py


Enter a supply chain query when prompted.
Type exit to quit.

Example Queries

"What is the total number of orders per customer segment?"
"Which shipping mode has the highest average late delivery risk?"
"What are load optimization strategies in our logistics policy?"
"Predict the late delivery risk for LATAM in 2019."

Features

Document Retrieval: Retrieves and summarizes relevant policy documents.
SQL Querying: Generates and executes SQL queries based on the schema.
Web Search: Fetches external knowledge using the Serper API.
Prediction: Predicts late delivery risks using a pre-trained model.
Explanation: Provides insights and business recommendations.
Learning Module: Offers educational content on supply chain topics.
Role-Based Access Control (RBAC): Restricts data access based on user roles.
Visualization: Generates charts for certain query results.
Gamification: Awards badges and tracks compliance scores.

Logging

Application logs are stored in app.log.
Audit logs are stored in audit_log.txt.

Limitations

Predictive model requires historical data from 2015-2018.
Assumes a specific database schema.
Requires external API keys for LLM and web search functionalities.

License
MIT License
