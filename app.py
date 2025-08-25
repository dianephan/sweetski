from flask import Flask
from dotenv import load_dotenv
from routes import register_routes
import os

# Load environment variables
load_dotenv()

def create_app():
    """Create and configure the Flask application"""
    app = Flask(__name__)
    app.secret_key = 'your-secret-key-here'  # For flash messages

    register_routes(app)
    
    return app

if __name__ == '__main__':
    print("🌸 Starting Sweetski Python App...")
    print("🌐 Open http://localhost:5002 in your browser")
    print("-" * 60)
    
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5002)