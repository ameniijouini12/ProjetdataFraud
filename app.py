import pandas as pd
import numpy as np
import pickle
from flask import Flask, render_template, request, jsonify, flash, redirect, url_for
from datetime import datetime
import re
from urllib.parse import urlparse
import openai
from typing import Dict
import json


app = Flask(__name__)
model = pickle.load(open('model.pkl', 'rb'))
vectorizer = pickle.load(open('vectorizer.pkl', 'rb'))
app.config['SECRET_KEY'] = "secret lol"

# Configuration OpenAI (à remplacer par votre clé API)
openai.api_key = 'your-api-key'

# Stockage en mémoire des analyses (dans un vrai projet, utilisez une base de données)
job_analyses = []

class JobAnalysis:
    def __init__(self, url, notes, is_fraudulent, analyzed_at):
        self.url = url
        self.notes = notes
        self.is_fraudulent = is_fraudulent
        self.analyzed_at = analyzed_at
        self.domain = urlparse(url).netloc
        # Extraire le titre du domaine pour l'affichage
        self.title = self.domain.split('.')[0].capitalize()

class AIJobAnalyzer:
    def analyze_job_posting(self, url: str, notes: str) -> Dict:
        prompt = f"""
        Analyze this job posting for potential fraud indicators:
        URL: {url}
        Notes: {notes}
        
        Consider the following aspects:
        1. Legitimacy of the offer
        2. Red flags in language used
        3. Suspicious requirements
        4. Unrealistic promises
        
        Provide a detailed analysis.
        """
        
        try:
            response = openai.Completion.create(
                engine="text-davinci-003",
                prompt=prompt,
                max_tokens=500
            )
            
            analysis = response.choices[0].text.strip()
            
            # Analyse de sentiment basique
            suspicious_phrases = [
                "too good to be true",
                "suspicious",
                "red flag",
                "scam",
                "unrealistic"
            ]
            
            risk_score = sum(1 for phrase in suspicious_phrases if phrase in analysis.lower())
            
            return {
                "ai_analysis": analysis,
                "risk_score": risk_score,
                "risk_level": "High" if risk_score > 2 else "Medium" if risk_score > 0 else "Low"
            }
        except Exception as e:
            return {"error": str(e)}

@app.route("/")
@app.route("/index")
def index():
    return render_template('index.html')


@app.route("/submit", methods=['POST'])
def submit():

    # The input data
    input_data = [request.form['title']+' '+ request.form['location']+' '+request.form['department']+' '+request.form['profile']+' '+request.form['req']+' '+request.form['ben']+' '+request.form['emptype']+' '+request.form['exp']+' '+request.form['edu']+' '+request.form['indu']+' '+request.form['func']+' '+request.form['des']]


    # convert text to feature vectors
    input_data_features = vectorizer.transform(input_data)

    # making prediction
    prediction = model.predict(input_data_features)
    print(prediction)

    if (prediction[0] == 1):
        flash("FRAUDULENT JOB")
        return render_template('index.html')

    else:
        flash("REAL JOB")
        return render_template('index.html')

@app.route('/job-threads')
def job_threads():
    # Passer les 5 dernières analyses à la template
    recent_analyses = list(reversed(job_analyses[-5:]))
    return render_template('job_threads.html', analyses=recent_analyses)

@app.route('/analyze-url', methods=['POST'])
def analyze_url():
    url = request.form.get('job_url')
    notes = request.form.get('notes', '').lower()
    
    if not url:
        return jsonify({
            'success': False,
            'error': 'URL is required'
        }), 400

    # Liste de mots-clés suspects dans l'URL
    suspicious_keywords = [
        'quick-money', 'easy-money', 'get-rich', 'work-from-home',
        'no-experience', 'high-salary', 'urgent', 'quick-hire',
        'earn-fast', 'free-money', 'payment-upfront', 'crypto'
    ]

    # Liste de mots-clés suspects dans les notes
    suspicious_notes_keywords = [
        'payment required', 'upfront fee', 'investment needed',
        'bank details', 'passport', 'security number',
        'guaranteed income', 'no skills', 'urgent position',
        '€/week', '€/day', 'instant money', 'quick cash'
    ]

    url_lower = url.lower()
    
    # Vérification du domaine
    domain = urlparse(url).netloc.lower()
    trusted_domains = ['linkedin.com', 'indeed.com', 'glassdoor.com', 'monster.com', 'google.com/careers']
    suspicious_tlds = ['.xyz', '.tk', '.ml', '.ga', '.cf']
    
    is_fraudulent = False

    # Vérifications pour marquer comme frauduleux
    if any(keyword in url_lower for keyword in suspicious_keywords):
        is_fraudulent = True
    elif any(tld in domain for tld in suspicious_tlds):
        is_fraudulent = True
    elif not any(trusted in domain for trusted in trusted_domains):
        # Si le domaine n'est pas de confiance, on vérifie d'autres critères
        if any(keyword in notes for keyword in suspicious_notes_keywords):
            is_fraudulent = True
        # Vérification des montants suspects dans les notes
        money_patterns = [
            r'\d+[k€]\s*(?:par|\/|\-)\s*(?:jour|semaine|week|day)',
            r'[€$]\d+[k]?\s*(?:par|\/|\-)\s*(?:jour|semaine|week|day)',
        ]
        if any(re.search(pattern, notes) for pattern in money_patterns):
            is_fraudulent = True

    # Créer et sauvegarder l'analyse
    analysis = JobAnalysis(
        url=url,
        notes=notes,
        is_fraudulent=is_fraudulent,
        analyzed_at=datetime.now()
    )
    job_analyses.append(analysis)

    # Ajouter l'analyse IA
    ai_analyzer = AIJobAnalyzer()
    ai_results = ai_analyzer.analyze_job_posting(url, notes)

    return jsonify({
        'success': True,
        'is_fraudulent': is_fraudulent,
        'analyzed_at': analysis.analyzed_at.strftime('%Y-%m-%d %H:%M:%S'),
        'domain': analysis.domain,
        'title': analysis.title,
        'ai_analysis': ai_results
    })

@app.route('/rate-analysis', methods=['POST'])
def rate_analysis():
    analysis_id = request.form.get('analysis_id')
    rating = request.form.get('rating')
    
    # Ici, vous ajouteriez la logique pour sauvegarder la note
    # Dans une vraie application, cela serait stocké dans une base de données
    
    return jsonify({'success': True})

@app.route('/analysis/<analysis_id>')
def view_analysis(analysis_id):
    # Récupérer l'analyse spécifique pour le partage
    # Dans une vraie application, cela viendrait d'une base de données
    return render_template('job_threads.html', shared_analysis_id=analysis_id)

@app.route('/start-thread')
def start_thread():
    return render_template('start_thread.html')

@app.route('/chat-predict', methods=['POST'])
def chat_predict():
    message = request.form.get('message')
    location = request.form.get('location')
    job_data = request.form.get('jobData')

    if job_data:
        job_data = json.loads(job_data)
        # Préparer les données pour le modèle
        input_text = f"{job_data.get('title', '')} {location} {job_data.get('description', '')}"
        
        # Vectorisation du texte
        input_features = vectorizer.transform([input_text])
        
        # Prédiction avec le modèle
        prediction = model.predict(input_features)[0]
        probability = model.predict_proba(input_features)[0]

        # Déterminer la langue de réponse
        lang = detect_language(message)
        responses = {
            'ar': {
                1: "تحذير! هذا العرض يبدو مشبوهاً (ثقة: {:.0f}%)",
                0: "هذا العرض يبدو شرعياً (ثقة: {:.0f}%)"
            },
            'fr': {
                1: "Attention! Cette offre semble frauduleuse (confiance: {:.0f}%)",
                0: "Cette offre semble légitime (confiance: {:.0f}%)"
            },
            'en': {
                1: "Warning! This job posting appears to be fraudulent (confidence: {:.0f}%)",
                0: "This job posting appears to be legitimate (confidence: {:.0f}%)"
            }
        }

        # Calculer le pourcentage de confiance
        confidence = probability[1] if prediction == 1 else probability[0]
        response_text = responses[lang][prediction].format(confidence * 100)

        return jsonify({
            'response': response_text,
            'is_fraudulent': bool(prediction),
            'confidence': confidence
        })

    return jsonify({
        'response': get_chatbot_response(message, detect_language(message))
    })

def get_chatbot_response(message, location):
    responses = {
        'greeting': f"Hello! I see you're in {location}. Would you like me to help predict job legitimacy in your area?",
        'help': "I can help you analyze job postings for potential fraud. Just share the job details with me!",
        'location': f"I'll focus on job postings in {location}. What kind of job are you interested in?",
        'default': "I'm here to help you identify fraudulent job postings. Would you like to analyze a specific job?"
    }

    message = message.lower()
    if any(word in message for word in ['hello', 'hi', 'hey']):
        return responses['greeting']
    elif any(word in message for word in ['help', 'how']):
        return responses['help']
    elif 'location' in message or location.lower() in message:
        return responses['location']
    return responses['default']

def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def check_url_fraudulent(url):
    # Liste de patterns suspects
    suspicious_patterns = [
        r'fake',
        r'scam',
        r'free-money',
        r'work-from-home-\d+',
        r'get-rich',
        r'earn-fast'
    ]
    
    url_lower = url.lower()
    
    # Vérification des patterns suspects
    for pattern in suspicious_patterns:
        if re.search(pattern, url_lower):
            return True
            
    # Vérification du domaine
    trusted_domains = ['linkedin.com', 'indeed.com', 'glassdoor.com', 'google.com']
    domain = urlparse(url).netloc.lower()
    
    if not any(td in domain for td in trusted_domains):
        # Si le domaine n'est pas dans la liste de confiance, vérification supplémentaire
        suspicious_tlds = ['.xyz', '.tk', '.ml', '.ga', '.cf']
        if any(tld in domain for tld in suspicious_tlds):
            return True
    
    return False

@app.route('/dashboard')
def dashboard():
    analyses = st.session_state.get('analyses', [])
    return render_template('dashboard.html', 
                         name="User",  # Remplacer par le vrai nom d'utilisateur
                         analyses=analyses)

@app.route('/analyze-job')
def analyze_job():
    return redirect(url_for('job_threads'))

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)