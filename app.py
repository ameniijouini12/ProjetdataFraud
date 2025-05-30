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
    def __init__(self, url, notes, is_fraudulent, analyzed_at, model_prediction=None, confidence_score=None, important_features=None):
        self.url = url
        self.notes = notes
        self.is_fraudulent = is_fraudulent
        self.analyzed_at = analyzed_at
        self.domain = urlparse(url).netloc
        # Extraire le titre du domaine pour l'affichage
        self.title = self.domain.split('.')[0].capitalize()
        self.model_prediction = model_prediction
        self.confidence_score = confidence_score
        self.important_features = important_features

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
    try:
        # Get form data
        form_fields = ['title', 'location', 'department', 'profile', 'req', 
                      'ben', 'emptype', 'exp', 'edu', 'indu', 'func', 'des']
        
        form_data = ' '.join(request.form.get(field, '') for field in form_fields)
        input_data = [form_data]

        # Feature extraction
        print("\n=== Model Analysis Started ===")
        print("1. Text Vectorization Process:")
        input_data_features = vectorizer.transform(input_data)
        print(f"→ Input text vectorized to {input_data_features.shape[1]} features")

        # Prediction with probability
        prediction = model.predict(input_data_features)
        probabilities = model.predict_proba(input_data_features)[0]
        confidence_score = max(probabilities) * 100

        print("\n2. Model Prediction Details:")
        print(f"→ Prediction: {'FRAUDULENT' if prediction[0] == 1 else 'LEGITIMATE'}")
        print(f"→ Confidence Score: {confidence_score:.2f}%")
        print(f"→ Probability Distribution: Fraudulent: {probabilities[1]:.2f}, Legitimate: {probabilities[0]:.2f}")

        # Feature importance analysis
        feature_names = vectorizer.get_feature_names_out()
        important_features = extract_important_features(input_data_features, feature_names)
        
        print("\n3. Key Indicators Detected:")
        for feature, importance in important_features[:5]:
            print(f"→ '{feature}' (importance: {importance:.3f})")

        print("\n=== Analysis Complete ===\n")

        if prediction[0] == 1:
            flash(f"⚠️ FRAUDULENT JOB POSTING DETECTED (Confidence: {confidence_score:.1f}%)")
        else:
            flash(f"✅ LEGITIMATE JOB POSTING (Confidence: {confidence_score:.1f}%)")
        
        return render_template('index.html', 
                             prediction=prediction[0],
                             confidence=confidence_score,
                             important_features=important_features[:5])
            
    except Exception as e:
        print(f"Error in model analysis: {str(e)}")
        flash("An error occurred during analysis. Please try again.")
        return render_template('index.html')

def extract_important_features(features, feature_names, top_n=5):
    """Extract most influential features for the prediction."""
    feature_importance = []
    
    # Get non-zero features
    non_zero = features.nonzero()[1]
    
    # Create feature importance pairs
    for index in non_zero:
        feature_importance.append(
            (feature_names[index], features[0, index])
        )
    
    # Sort by absolute importance
    return sorted(feature_importance, key=lambda x: abs(x[1]), reverse=True)[:top_n]

@app.route('/job-threads')
@login_required
def job_threads():
    print("\n=== Job Threads Analysis Summary ===")
    recent_analyses = list(reversed(job_analyses[-5:]))
    
    # Add enhanced model statistics
    total = len(job_analyses)
    fraudulent = sum(1 for a in job_analyses if a.is_fraudulent)
    legitimate = total - fraudulent
    
    print("\n1. Overall Statistics:")
    print(f"→ Total Jobs Analyzed: {total}")
    print(f"→ Fraudulent Detected: {fraudulent}")
    print(f"→ Legitimate Jobs: {legitimate}")
    
    if total > 0:
        fraud_percentage = (fraudulent / total) * 100
        print(f"→ Fraud Rate: {fraud_percentage:.1f}%")
        
        # Calculate average confidence
        avg_confidence = sum(a.confidence_score for a in job_analyses if a.confidence_score)/total
        print(f"→ Average Model Confidence: {avg_confidence:.1f}%")
        
        print("\n2. Recent Analysis Details:")
        for idx, analysis in enumerate(recent_analyses, 1):
            print(f"\nAnalysis #{idx}:")
            print(f"→ Status: {'FRAUDULENT' if analysis.is_fraudulent else 'LEGITIMATE'}")
            print(f"→ Confidence: {analysis.confidence_score:.1f}%")
            if analysis.important_features:
                print("→ Key Indicators:", ', '.join(f"'{f}'" for f, _ in analysis.important_features[:3]))
    
    print("\n=== Analysis Summary Complete ===\n")
    
    stats = {
        'total_analyzed': total,
        'fraudulent_count': fraudulent,
        'legitimate_count': legitimate,
        'fraud_rate': fraud_percentage if total > 0 else 0,
        'avg_confidence': avg_confidence if total > 0 else 0
    }
    
    return render_template('job_threads.html', 
                         analyses=recent_analyses,
                         stats=stats)

@app.route('/analyze-url', methods=['POST'])
def analyze_url():
    url = request.form.get('job_url')
    notes = request.form.get('notes', '').lower()
    details = []  # Initialize details list
    
    if not url:
        return jsonify({
            'success': False,
            'error': 'URL is required'
        }, 400)

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
    
    # Extraction des détails de l'URL Indeed
    is_indeed = 'indeed.com' in domain
    if is_indeed:
        try:
            job_id = url.split('vjk=')[1] if 'vjk=' in url else None
            if job_id:
                details.append(f"Indeed Job ID: {job_id}")
        except Exception as e:
            print(f"Error parsing Indeed URL: {str(e)}")
    
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
@app.route('/start_thread', methods=['GET', 'POST'])
@login_required  # Ajout du décorateur login_required
def start_thread():
    if request.method == 'POST':
        job_description = request.form.get('job_description', '')
        url = request.form.get('job_url', '')
        notes = request.form.get('notes', '')

        # Model Analysis
        input_data = [job_description]
        input_features = vectorizer.transform(input_data)
        prediction = model.predict(input_features)[0]
        probabilities = model.predict_proba(input_features)[0]
        confidence_score = max(probabilities) * 100
        
        # Extract important features
        feature_names = vectorizer.get_feature_names_out()
        important_features = extract_important_features(input_features, feature_names)

        # Create and save analysis
        analysis = JobAnalysis(
            url=url,
            notes=notes,
            is_fraudulent=(prediction == 1),
            analyzed_at=datetime.now(),
            model_prediction=prediction,
            confidence_score=confidence_score,
            important_features=important_features[:5]
        )
        job_analyses.append(analysis)

        print("\n=== Thread Analysis Results ===")
        print(f"Prediction: {'FRAUDULENT' if prediction == 1 else 'LEGITIMATE'}")
        print(f"Confidence Score: {confidence_score:.2f}%")
        print("Important Features:", important_features[:5])
        print("==========================\n")

        return redirect(url_for('job_threads'))

    return render_template('start_thread.html', active_page='new_thread')

def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def handle_chat_message(message: str):
    """Smart message handler for different types of inputs"""
    message = message.lower().strip()
    
    # Greeting patterns
    greetings = ['hello', 'hi', 'hey', 'greetings', 'bonjour']
    if any(message.startswith(g) for g in greetings):
        return {
            'type': 'greeting',
            'response': "Hello! I'm your Job Fraud Detection Assistant. How can I help you today? You can share:\n" +
                       "• A job description for analysis\n" +
                       "• A job posting URL\n" +
                       "• An Indeed job listing\n" +
                       "I'll analyze it for potential fraud indicators."
        }

    # URL detection
    if 'http' in message or 'www.' in message:
        # Extract URL
        url_pattern = r'https?://\S+|www\.\S+'
        urls = re.findall(url_pattern, message)
        if urls:
            url = urls[0]
            domain = urlparse(url).netloc.lower()
            
            # Indeed URL handling
            if 'indeed.com' in domain:
                indeed_details = analyze_indeed_url(url)
                return analyze_job_url_detailed(url, indeed_details)
            
            # General URL handling
            return analyze_job_url_detailed(url)

    # Default case: Analyze as job description
    return analyze_job_description(message)

def analyze_job_description(text):
    """Detailed analysis of job description text"""
    try:
        print("\n=== ML Model Analysis Started ===")
        print("Input text:", text[:200] + "..." if len(text) > 200 else text)
        
        # Transform and vectorize input
        input_features = vectorizer.transform([text])
        print(f"\n1. Vectorization Complete:")
        print(f"→ Text transformed into {input_features.shape[1]} features")

        # Get predictions and probabilities
        prediction = model.predict(input_features)[0]
        probabilities = model.predict_proba(input_features)[0]
        
        print("\n2. Model Prediction Results:")
        print(f"→ Prediction: {'FRAUDULENT' if prediction else 'LEGITIMATE'}")
        print(f"→ Confidence: {max(probabilities)*100:.2f}%")
        print(f"→ Fraud Probability: {probabilities[1]:.3f}")
        print(f"→ Legitimate Probability: {probabilities[0]:.3f}")
        
        # Extract important features
        feature_names = vectorizer.get_feature_names_out()
        important_features = extract_important_features(input_features, feature_names)
        
        print("\n3. Key Indicators Detected:")
        for feature, importance in important_features[:5]:
            print(f"→ '{feature}' (importance: {importance:.3f})")
        
        # Additional text analysis
        text_details = analyze_text_content(text)
        
        print("\n4. Content Analysis:")
        for detail in text_details:
            print(f"→ {detail}")
        
        print("\n=== Analysis Complete ===\n")
        
        return {
            'type': 'analysis',
            'is_fraudulent': bool(prediction),
            'confidence': float(max(probabilities)),
            'important_features': important_features[:5],
            'details': text_details,
            'response': generate_analysis_response(prediction, max(probabilities), important_features)
        }
    except Exception as e:
        print(f"Error in analyze_job_description: {str(e)}")
        return {'type': 'error', 'response': "I couldn't analyze this text. Please try again."}

def analyze_indeed_url(url):
    """Analyze an Indeed job posting URL and extract relevant information."""
    result = {
        'type': 'indeed',
        'job_id': None,
        'platform': 'Indeed',
        'is_trusted': True,
        'location': None,
        'query': None
    }
    
    try:
        if 'indeed.com' in url.lower():
            # Extract job ID
            if 'vjk=' in url:
                result['job_id'] = url.split('vjk=')[1].split('&')[0]
            
            # Extract search query if present
            if 'q=' in url:
                result['query'] = url.split('q=')[1].split('&')[0].replace('+', ' ')
            
            # Extract location if present
            if 'l=' in url:
                result['location'] = url.split('l=')[1].split('&')[0].replace('+', ' ')
    except Exception as e:
        print(f"Error analyzing Indeed URL: {str(e)}")
    
    return result

def analyze_job_url_detailed(url, indeed_details=None):
    """Enhanced URL analysis with Indeed special handling"""
    print("\n=== URL Analysis Started ===")
    print(f"Analyzing URL: {url}")
    
    domain = urlparse(url).netloc.lower()
    is_trusted = any(td in domain for td in ['linkedin.com', 'indeed.com', 'glassdoor.com'])
    
    print(f"\n1. Domain Analysis:")
    print(f"→ Domain: {domain}")
    print(f"→ Trusted Platform: {'Yes' if is_trusted else 'No'}")
    
    response_details = []
    if indeed_details and isinstance(indeed_details, dict):
        print("\n2. Indeed Job Details:")
        if indeed_details.get('job_id'):
            detail = f"Indeed Job ID: {indeed_details['job_id']}"
            response_details.append(detail)
            print(f"→ {detail}")
        if indeed_details.get('location'):
            detail = f"Location: {indeed_details['location']}"
            response_details.append(detail)
            print(f"→ {detail}")
    
    suspicious = analyze_url_details(url)
    if suspicious:
        print("\n3. Suspicious Indicators:")
        for detail in suspicious:
            print(f"→ {detail}")
    
    print("\n=== Analysis Complete ===\n")
    
    return {
        'type': 'url_analysis',
        'is_trusted_domain': is_trusted,
        'details': response_details + suspicious,
        'response': generate_url_response(not is_trusted, suspicious)
    }

def generate_analysis_response(prediction, confidence, important_features):
    """Generate a detailed analysis response without follow-up question"""
    confidence_pct = confidence * 100
    
    if prediction == 1:
        response = f"⚠️ This job posting appears to be fraudulent (Confidence: {confidence_pct:.1f}%)"
    else:
        response = f"✅ This appears to be a legitimate job posting (Confidence: {confidence_pct:.1f}%)"
    
    return response

@app.route('/chat-predict', methods=['POST'])
def chat_predict():
    message = request.form.get('message', '').strip()
    
    if not message:
        return jsonify({
            'error': 'Empty message',
            'message': 'Please provide some text to analyze.'
        }, 400)

    try:
        # Handle message using smart handler
        result = handle_chat_message(message)
        
        if not isinstance(result, dict):
            raise ValueError("Invalid analysis result format")
            
        if result.get('type') == 'greeting':
            return jsonify({
                'is_greeting': True,
                'response': result.get('response', 'Hello! How can I help you?'),
                'details': [],
                'should_follow_up': False  # Don't add follow-up for greetings
            })
        
        elif result.get('type') == 'url_analysis':
            return jsonify({
                'is_url': True,
                'is_trusted': result.get('is_trusted_domain', False),
                'response': result.get('response', 'URL analysis completed.'),
                'details': result.get('details', []),
                'should_follow_up': False  # Don't add follow-up for URL analysis
            })
        
        else:  # Normal analysis
            return jsonify({
                'is_fraudulent': result.get('is_fraudulent', False),
                'confidence': result.get('confidence', 0.0),
                'response': result.get('response', 'Analysis completed.'),
                'details': result.get('details', []),
                'important_features': result.get('important_features', []),
                'should_follow_up': False  # Don't add follow-up for normal analysis
            })

    except Exception as e:
        print(f"Error in chat_predict: {str(e)}")
        return jsonify({
            'error': 'Analysis failed',
            'message': 'Unable to process the request. Please try again.'
        }, 500)

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
    
    response += "\n\nRecommendation: f"
    response += "Please exercise caution and verify independently." if is_fraudulent else "Proceed with standard due diligence."
    
    return response

def analyze_url_details(url):
    details = []
    domain = urlparse(url).netloc.lower()
    
    if not any(td in domain for td in ['linkedin.com', 'indeed.com', 'glassdoor.com']):
        details.append("Website is not a recognized job platform")
    
    return details

def analyze_indeed_url(url):
    """Analyze an Indeed job posting URL and extract relevant information."""
    result = {
        'type': 'indeed',
        'job_id': None,
        'platform': 'Indeed',
        'is_trusted': True,
        'location': None,
        'query': None
    }
    
    try:
        if 'indeed.com' in url.lower():
            # Extract job ID
            if 'vjk=' in url:
                result['job_id'] = url.split('vjk=')[1].split('&')[0]
            
            # Extract search query if present
            if 'q=' in url:
                result['query'] = url.split('q=')[1].split('&')[0].replace('+', ' ')
            
            # Extract location if present
            if 'l=' in url:
                result['location'] = url.split('l=')[1].split('&')[0].replace('+', ' ')
    except Exception as e:
        print(f"Error analyzing Indeed URL: {str(e)}")
    
    return result

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Authentication logic
        if username == 'Karim' and password == 'SécuR!té@2025!':
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