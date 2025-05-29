import pandas as pd
import numpy as np
import pickle
from flask import Flask, render_template, request, jsonify, flash, redirect, url_for, session
from datetime import datetime
import re
from urllib.parse import urlparse
import openai
from typing import Dict
import json
from functools import wraps


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

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route("/")
@app.route("/index")
@login_required
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
@login_required
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
@app.route('/start_thread')
@login_required  # Ajout du décorateur login_required
def start_thread():
    return render_template('start_thread.html', active_page='new_thread')

def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

@app.route('/chat-predict', methods=['POST'])
def chat_predict():
    message = request.form.get('message', '').strip()
    
    # Process the message
    try:
        input_features = vectorizer.transform([message])
        prediction = model.predict(input_features)[0]
        probability = model.predict_proba(input_features)[0]
        confidence = probability[1] if prediction == 1 else probability[0]
        
        details = []
        if prediction == 1:
            details = [
                "Contains suspicious patterns or keywords",
                "High risk indicators detected in the text",
                "Please verify the source carefully"
            ]
        else:
            details = [
                "Standard job posting format detected",
                "Professional language used",
                "Common industry terms present"
            ]

        response = {
            'is_fraudulent': bool(prediction),
            'confidence': float(confidence),
            'response': "This job posting appears to be fraudulent!" if prediction == 1 
                       else "This job posting appears to be legitimate.",
            'details': details
        }
        
        return jsonify(response)
        
    except Exception as e:
        print(f"Error in chat_predict: {str(e)}")
        return jsonify({
            'error': 'Analysis failed',
            'message': 'Unable to process the request'
        }), 500

def analyze_text_content(text):
    details = []
    suspicious_keywords = [
        'urgent', 'quick', 'easy money', 'investment required',
        'work from home', 'no experience needed', 'guaranteed income',
        'immediate start', 'unlimited earnings', 'be your own boss'
    ]
    
    professional_keywords = [
        'qualifications', 'experience', 'skills required', 'degree',
        'responsibilities', 'requirements', 'benefits package'
    ]
    
    # Check suspicious keywords
    found_suspicious = [word for word in suspicious_keywords if word in text.lower()]
    if found_suspicious:
        details.append(f"Suspicious terms detected: {', '.join(found_suspicious)}")
    
    # Check professional keywords
    found_professional = [word for word in professional_keywords if word in text.lower()]
    if found_professional:
        details.append(f"Professional terms found: {', '.join(found_professional)}")
    
    # Check for salary patterns
    salary_pattern = r'\$\d+[k]?(?:\s*-\s*\$\d+[k]?)?(?:\s*(?:per|\/)\s*(?:hour|month|year|annum))?'
    if re.search(salary_pattern, text, re.IGNORECASE):
        details.append("Salary information included")
    
    return details

def generate_text_response(is_fraudulent, confidence, details):
    confidence_pct = int(confidence * 100)
    
    if is_fraudulent:
        if confidence_pct > 80:
            response = f"⚠️ High Risk Alert! This job posting appears to be fraudulent (Confidence: {confidence_pct}%)"
        else:
            response = f"🚨 Warning! This job posting contains suspicious elements (Confidence: {confidence_pct}%)"
    else:
        if confidence_pct > 80:
            response = f"✅ This appears to be a legitimate job posting (Confidence: {confidence_pct}%)"
        else:
            response = f"👍 This job posting seems legitimate, but please verify independently (Confidence: {confidence_pct}%)"
    
    if details:
        response += "\n\nAnalysis Details:"
        for detail in details:
            response += f"\n• {detail}"
    
    return response

def generate_url_response(is_fraudulent, details):
    if is_fraudulent:
        response = "⚠️ Warning! This URL shows potential signs of fraud:"
    else:
        response = "✅ This URL appears to be from a legitimate job site:"
    
    if details:
        response += "\n\nFindings:"
        for detail in details:
            response += f"\n• {detail}"
    
    response += "\n\nRecommendation: "
    response += "Please exercise caution and verify independently." if is_fraudulent else "Proceed with standard due diligence."
    
    return response

def analyze_url_details(url):
    details = []
    domain = urlparse(url).netloc.lower()
    
    if not any(td in domain for td in ['linkedin.com', 'indeed.com', 'glassdoor.com']):
        details.append("Website is not a recognized job platform")
    
    return details

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Authentication logic
        if username == 'Ameni' and password == '1234':
            session['logged_in'] = True
            session['username'] = username
            flash('You were successfully logged in')
            return redirect(url_for('index'))
        else:
            error = 'Invalid credentials. Please try again.'
    
    return render_template('login.html', error=error)

# Logout route
@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('username', None)
    flash('You were logged out')
    return redirect(url_for('login'))

@app.route('/analyze-job')
def analyze_job():
    return redirect(url_for('job_threads'))

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)