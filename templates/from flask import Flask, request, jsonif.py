from flask import Flask, request, jsonify
from openai import OpenAI
from dotenv import load_dotenv
import os
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

app = Flask(__name__)

def get_chatbot_response(message):
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are an AI assistant specialized in detecting fraudulent job postings. Your task is to help users identify potential job scams and provide safety advice."},
                {"role": "user", "content": message}
            ],
            temperature=0.7,
            max_tokens=150
        )
        return True, response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"OpenAI API error: {str(e)}")
        return False, str(e)

@app.route('/chat_predict', methods=['POST'])
def chat_predict():
    try:
        message = request.form.get('message', '').strip()
        if not message:
            return jsonify({
                'success': False,
                'error': 'No message provided'
            }), 400

        success, response = get_chatbot_response(message)
        if success:
            return jsonify({
                'success': True,
                'response': response
            })
        else:
            return jsonify({
                'success': False,
                'error': f"AI Error: {response}"
            }), 500

    except Exception as e:
        logger.error(f"Chat prediction error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500

@app.route('/')
def home():
    return "Welcome to the Job Posting Fraud Detection API!"

if __name__ == '__main__':
    app.run(debug=True)