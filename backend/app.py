from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from datetime import timedelta
import re
import subprocess
import json
import sys

app = Flask(__name__)

# Initialize Flask-CORS immediately and broadly.
# This should be one of the first things after creating the app instance.
CORS(
    app,
    origins="*",  # Allow all origins for debugging
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],  # Allow all relevant methods
    allow_headers=["*"],  # Allow all headers for debugging
    supports_credentials=True
)

# Configuration
app.config['JWT_SECRET_KEY'] = 'your-secret-key'  # Change this in production
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1)
jwt = JWTManager(app)

# Add custom JWT error handlers for better diagnostics
@jwt.invalid_token_loader
def invalid_token_callback(error_string):
    # This callback is triggered when a token is invalid (e.g., malformed, signature verification failed)
    return jsonify(msg=f"Invalid token: {error_string}"), 422

@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload):
    # This callback is triggered when a token has expired
    return jsonify(msg="Token has expired. Please log in again."), 401

@jwt.unauthorized_loader
def missing_token_callback(error_string):
    # This callback is triggered when a token is missing from a protected endpoint
    return jsonify(msg=f"Authorization required: {error_string}"), 401

# Database connection
def get_db_connection():
    conn = psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'syngenta'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', '12345')
    )
    conn.autocommit = True
    return conn

# Sample documents for demo
documents = {
    'inventory_policy': {
        'content': 'According to the Inventory Management Policy, write-offs are allowed for obsolete inventory after 180 days with approval.',
        'url': '/documents/inventory_policy.pdf',
        'required_role': 'Planning'
    },
    'financial_report': {
        'content': 'Q2 2023 financial report shows a 15% increase in revenue compared to Q1.',
        'url': '/documents/financial_report.pdf',
        'required_role': 'Finance'
    }
}

# Authentication routes
@app.route('/auth/register', methods=['POST'])
def register():
    data = request.get_json()
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')
    role = data.get('role')
    region = data.get('region')
    
    if not all([name, email, password, role, region]):
        return jsonify({'message': 'Missing required fields'}), 400
    
    hashed_password = generate_password_hash(password)
    
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            # Check if user already exists
            cur.execute('SELECT id FROM users WHERE email = %s', (email,))
            if cur.fetchone():
                return jsonify({'message': 'User already exists'}), 409
                
            # Insert new user
            cur.execute(
                'INSERT INTO users (name, email, password, role, region) VALUES (%s, %s, %s, %s, %s) RETURNING id',
                (name, email, hashed_password, role, region)
            )
            user_id = cur.fetchone()[0]
        conn.close()
        
        return jsonify({'message': 'User registered successfully', 'user_id': user_id}), 201
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'message': 'Registration failed'}), 500

@app.route('/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    
    if not email or not password:
        return jsonify({'message': 'Missing email or password'}), 400
    
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute('SELECT * FROM users WHERE email = %s', (email,))
            user = cur.fetchone()
            
            if not user or not check_password_hash(user['password'], password):
                return jsonify({'message': 'Invalid credentials'}), 401
            
            access_token = create_access_token(identity=user['id'])
            
            user_data = {
                'id': user['id'],
                'name': user['name'],
                'email': user['email'],
                'role': user['role'],
                'region': user['region']
            }
        conn.close()
        
        return jsonify({'token': access_token, 'user': user_data}), 200
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'message': 'Login failed'}), 500

# Helper to invoke main.py in API mode
def query_python_agent(query, role, region):
    agent_path = os.path.abspath(os.path.join(
        os.path.dirname(__file__),
        '..', 'teamX_v2', 'main.py'
    ))
    payload = json.dumps({'query': query, 'user_role': role, 'user_region': region})
    try:
        result = subprocess.run(
            [sys.executable, agent_path, '--api-mode'],
            input=payload,
            text=True,
            capture_output=True,
            cwd=os.path.dirname(agent_path),
            timeout=30  # kill if no response in 30s
        )
    except subprocess.TimeoutExpired as e:
        return {
            'summary': 'Agent timeout occurred.',
            'accessDenied': False,
            'documentUrl': None,
            'charts': [],
            'prediction_results': '',
            'error': f'TimeoutExpired: {e}'
        }
    except Exception as e:
        return {
            'summary': 'Agent execution error.',
            'accessDenied': False,
            'documentUrl': None,
            'charts': [],
            'prediction_results': '',
            'error': str(e)
        }
    if result.returncode != 0:
        return {
            'summary': 'Agent error occurred.',
            'accessDenied': False,
            'documentUrl': None,
            'charts': [],
            'prediction_results': '',
            'error': result.stderr.strip()
        }
    try:
        return json.loads(result.stdout)
    except Exception as e:
        return {
            'summary': 'Invalid response from agent.',
            'accessDenied': False,
            'documentUrl': None,
            'charts': [],
            'prediction_results': '',
            'error': str(e)
        }

# API routes
@app.route('/api/query', methods=['POST'])
# remove jwt_required or keep optional
def process_query():
    try:
        user_id = None  # always anonymous in dev
        data = request.get_json()
        
        if not data:
            return jsonify({'message': 'Missing request body'}), 400
            
        query = data.get('query', '')
        
        if not query:
            return jsonify({'message': 'Query is required'}), 400
        
        # For development, allow queries without authentication
        if user_id is None:
            # If no user is authenticated, use default values
            role = "planning_manager"  # Match the role used in direct agent testing
            region = "all"  # Match the region used in direct agent testing
            print("Warning: Processing query without authentication")
        else:
            # Get authenticated user information
            try:
                conn = get_db_connection()
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute('SELECT role, region FROM users WHERE id = %s', (user_id,))
                    user = cur.fetchone()
                    
                    if not user:
                        return jsonify({'message': 'User not found'}), 404
                    
                    role = user['role']
                    region = user['region']
                    
                    # Save query to history for authenticated users
                    cur.execute(
                        'INSERT INTO query_history (user_id, query) VALUES (%s, %s)',
                        (user_id, query)
                    )
                conn.close()
            except Exception as e:
                print(f"Database error: {e}")
                # Fall back to default values if database access fails
                role = "Global" 
                region = "Global"
        
        # invoke Python agent instead of local access control
        agent_resp = query_python_agent(query, role, region)
        print(f"Agent response: {agent_resp}")
        response_payload = {
            'answer':            agent_resp.get('summary', ''),
            'accessDenied':      agent_resp.get('accessDenied', False),
            'documentUrl':       agent_resp.get('documentUrl'),
            'charts':            agent_resp.get('charts', []),
            'predictionResults': agent_resp.get('prediction_results', ''),
            'proactiveSuggestions': agent_resp.get('proactive_suggestions', []),
            'leaderboardPosition': agent_resp.get('leaderboard_position'),
            'complianceScore': agent_resp.get('compliance_score'),
            'accessAttemptLogged': agent_resp.get('audit_log', ''),
            'debug': {
                'role':       role,
                'region':     region,
                'fromAgent':  True,
                'agentError': agent_resp.get('error')    # include agent stderr or parse error
            }
        }
        return jsonify(response_payload), 200
        
    except Exception as e:
        print(f"Error processing query: {str(e)}")
        return jsonify({
            'message': f'Query processing failed: {str(e)}',
            'error': str(e)
        }), 500

@app.route('/api/history', methods=['GET'])
@jwt_required()
def get_query_history():
    user_id = get_jwt_identity()
    
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                'SELECT query FROM query_history WHERE user_id = %s ORDER BY created_at DESC LIMIT 10',
                (user_id,)
            )
            history = [row[0] for row in cur.fetchall()]
        conn.close()
        
        return jsonify({'history': history}), 200
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'message': 'Failed to fetch history'}), 500

# Debugging route to test API connection
@app.route('/test', methods=['GET'])
def test_route():
    return jsonify({
        'message': 'API is working correctly',
        'status': 'success'
    }), 200

# Helper functions
def process_query_with_access_control(query, role, region):
    # For demonstration, using simple keyword matching
    query_lower = query.lower()
    
    # Check for inventory-related queries
    if 'inventory' in query_lower or 'stock' in query_lower:
        if 'write-off' in query_lower or 'write off' in query_lower:
            if role == 'Planning' or role == 'Finance':
                return documents['inventory_policy']['content'], False, documents['inventory_policy']['url']
            else:
                return "Access denied: Planning or Finance role required", True, None
                
    # Check for finance-related queries
    if 'financial' in query_lower or 'revenue' in query_lower or 'profit' in query_lower:
        if role == 'Finance':
            return documents['financial_report']['content'], False, documents['financial_report']['url']
        else:
            return "Access denied: Finance role required", True, None
    
    # Region-specific queries
    if re.search(r'\b(india|asia|europe|america|global)\b', query_lower):
        mentioned_region = None
        for r in ['india', 'asia', 'europe', 'america', 'global']:
            if r in query_lower:
                mentioned_region = r.capitalize()
                if r == 'america':
                    if 'north' in query_lower:
                        mentioned_region = 'North America'
                    elif 'latin' in query_lower:
                        mentioned_region = 'Latin America'
                    else:
                        mentioned_region = 'America'
                elif r == 'asia':
                    if 'pacific' in query_lower:
                        mentioned_region = 'Asia Pacific'
        
        if mentioned_region and region != 'Global' and mentioned_region != region:
            return f"Access denied: You don't have permission to access data for {mentioned_region}", True, None
    
    # Default response for unrecognized queries
    return "I don't have specific information on that topic. Please try another question related to inventory, logistics, or supply chain.", False, None

if __name__ == '__main__':
    # Run Flask on a different port, e.g., 5001
    app.run(debug=True, port=5001)
