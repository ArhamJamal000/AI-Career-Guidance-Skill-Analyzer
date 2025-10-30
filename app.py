from flask import Flask, render_template, request, redirect, url_for, session
import os
import json
from collections import defaultdict
import json as json_module
import requests
import time
import re
import random
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = os.urandom(24) 

api_call_times = []  
MAX_CALLS_PER_MINUTE = 3
CACHE_DURATION_MINUTES = 60  # Cache quizzes for 1 hour
quiz_cache = {}  # Cache for generated quizzes

# Load data from JSON files
with open('data/careers.json', 'r') as f:
    career_data = json.load(f)

with open('data/skills.json', 'r') as f:
    skills_data = json.load(f)

# Skill groups for multi-step questionnaire
skill_groups = list(skills_data.keys())

def calculate_skill_levels(user_ratings):
    """Calculate skill levels per language by averaging framework ratings"""
    skill_levels = {}
    framework_ratings = defaultdict(list)

    # Group ratings by main skill
    for framework, rating in user_ratings.items():
        for main_skill, frameworks in skills_data.items():
            if framework in frameworks:
                framework_ratings[main_skill].append(rating)
                break

    # Calculate averages and levels
    for main_skill, ratings in framework_ratings.items():
        avg_rating = sum(ratings) / len(ratings)
        if avg_rating <= 1.5:
            level = "Beginner"
        elif avg_rating <= 3.0:
            level = "Intermediate"
        elif avg_rating <= 4.0:
            level = "Advanced"
        else:
            level = "Expert"

        skill_levels[main_skill] = {
            'average_rating': round(avg_rating, 2),
            'level': level,
            'framework_ratings': dict(zip([f for f in skills_data[main_skill] if f in user_ratings], ratings))
        }

    return skill_levels

def analyze_skills(user_ratings, skill_levels):
    recommendations = []
    for career, data in career_data.items():
        required_skills = data['required_skills']
        total_score = 0
        max_score = 0
        missing_skills = []
        low_rated_skills = []

        for skill in required_skills:
            if skill in skill_levels:
                avg_rating = skill_levels[skill]['average_rating']
                total_score += avg_rating
                max_score += 5  
                if avg_rating <= 2.5:
                    low_rated_skills.append(skill)
            else:
                missing_skills.append(skill)
                max_score += 5

        match_percentage = (total_score / max_score) * 100 if max_score > 0 else 0

        # Calculate level based on match percentage
        if match_percentage <= 30:
            readiness_level = "Beginner"
        elif match_percentage <= 70:
            readiness_level = "Intermediate"
        else:
            readiness_level = "Advanced"

        recommendations.append({
            'career': career,
            'match_percentage': round(match_percentage, 2),
            'missing_skills': missing_skills,
            'low_rated_skills': low_rated_skills,
            'readiness_level': readiness_level,
            'total_score': total_score,
            'max_score': max_score,
            'skill_levels': skill_levels
        })

    recommendations.sort(key=lambda x: (x['match_percentage'], x['total_score']), reverse=True)
    return recommendations

def generate_roadmap(career, user_ratings, skill_levels):
    base_roadmap = career_data[career]['roadmap']
    missing_skills = []
    low_rated_skills = []

    for skill in career_data[career]['required_skills']:
        if skill not in skill_levels:
            missing_skills.append(skill)
        elif skill_levels[skill]['average_rating'] <= 2.5:
            low_rated_skills.append(skill)

    # Customize roadmap to focus 
    customized_roadmap = []
    if missing_skills or low_rated_skills:
        focus_skills = missing_skills + low_rated_skills
        customized_roadmap.append(f"Months 1-2: Focus on building fundamentals in {', '.join(focus_skills[:3])}")
        customized_roadmap.extend(base_roadmap[1:])
    else:
        customized_roadmap = base_roadmap

    return customized_roadmap

def analyze_level(match_pct):
    if match_pct <= 30:
        return "Beginner"
    elif match_pct <= 70:
        return "Intermediate"
    else:
        return "Advanced"

def parse_gemini_mcqs(response_text):
    questions = []
    blocks = re.split(r"\*\*Q\d+\.\*\*", response_text)
    for block in blocks:
        block = block.strip()
        if not block: continue
        print("Parsing question block:\n", block)  # Debug log
        lines = block.split("\n")
        q_text = lines[0].strip()
        options = [line[3:].strip() for line in lines if re.match(r"^[A-D]\)", line.strip())]
        answer_match = re.search(r"\*\*Answer:\*\*\s*([A-Da-d])", block)
        if not answer_match:
            answer_match = re.search(r"Answer:\s*([A-Da-d])", block, re.IGNORECASE)
        answer = answer_match.group(1).upper() if answer_match else None
        diff_match = re.search(r"\*\*Difficulty:\*\*\s*(\w+)", block, re.IGNORECASE)
        if not diff_match:
            diff_match = re.search(r"Difficulty:\s*(\w+)", block, re.IGNORECASE)
        difficulty = diff_match.group(1).capitalize() if diff_match else "Unknown"
        print(f"Extracted difficulty: {difficulty}")  # Debug log
        questions.append({"question": q_text, "options": options, "answer": answer, "difficulty": difficulty})
    return questions

def check_rate_limit():
    """Check if we're within the rate limit (3 calls per minute)"""
    global api_call_times
    now = datetime.now()
    api_call_times = [t for t in api_call_times if now - t < timedelta(minutes=1)]
    return len(api_call_times) < MAX_CALLS_PER_MINUTE

def record_api_call():
    """Record an API call timestamp"""
    global api_call_times
    api_call_times.append(datetime.now())

def get_cached_quiz(career_name):
    """Get cached quiz if available and not expired"""
    if career_name in quiz_cache:
        cached_time, questions = quiz_cache[career_name]
        if datetime.now() - cached_time < timedelta(minutes=CACHE_DURATION_MINUTES):
            print(f"Using cached quiz for {career_name}")  # Debug log
            return questions
        else:
            del quiz_cache[career_name]
    return None

def cache_quiz(career_name, questions):
    """Cache the generated quiz"""
    quiz_cache[career_name] = (datetime.now(), questions)
    print(f"Cached quiz for {career_name}")  # Debug log

@app.route('/')
def home():
    session.clear()
    return render_template('index.html', skill_groups=skill_groups, skills_data=skills_data)

@app.route('/frameworks', methods=['GET', 'POST'])
def frameworks():
    if request.method == 'POST':
        selected_skills = request.form.getlist('selected_skills')
        session['selected_skills'] = selected_skills
        return render_template('frameworks.html', selected_skills=selected_skills, skills_data=skills_data)
    else:
        selected_skills = session.get('selected_skills', [])
        if not selected_skills:
            return redirect(url_for('home'))
        return render_template('frameworks.html', selected_skills=selected_skills, skills_data=skills_data)

@app.route('/analyze', methods=['GET', 'POST'])
def analyze():
    if request.method == 'POST':
        user_ratings = {}
        for skill_group in skills_data:
            for framework in skills_data[skill_group]:
                rating_key = f'rating_{framework}'
                rating_value = request.form.get(rating_key, '0')
                user_ratings[framework] = int(rating_value)
        session['user_ratings'] = user_ratings
        return redirect(url_for('analyze'))
    else:
        user_ratings = session.get('user_ratings', {})
        if not user_ratings:
            return redirect(url_for('home'))

        # Calculate skill levels
        skill_levels = calculate_skill_levels(user_ratings)

        # Get recommendations with skill levels
        recommendations = analyze_skills(user_ratings, skill_levels)
        top_6 = recommendations[:6]  # Show top 6 career recommendations

        skill_levels_json = json_module.dumps(skill_levels)
        return render_template('results.html', recommendations=top_6, user_ratings=user_ratings, skill_levels=skill_levels, skill_levels_json=skill_levels_json)

@app.route('/roadmap/<career>')
def roadmap(career):
    if career not in career_data:
        return redirect(url_for('home'))

    user_ratings = session.get('user_ratings', {})
    skill_levels = calculate_skill_levels(user_ratings)
    recommendations = analyze_skills(user_ratings, skill_levels)
    rec = next((r for r in recommendations if r['career'] == career), None)
    if not rec:
        return redirect(url_for('home'))

    match_percentage = rec['match_percentage']
    missing_skills = rec['missing_skills']
    low_rated_skills = rec['low_rated_skills']
    level = analyze_level(match_percentage)
    roadmap_steps = generate_roadmap(career, user_ratings, skill_levels)
    resources = career_data[career]['resources']

    return render_template('roadmap.html', career=career, roadmap_steps=roadmap_steps, level=level, resources=resources, missing_skills=missing_skills, low_rated_skills=low_rated_skills, skill_levels=skill_levels, match_percentage=match_percentage)

@app.route('/quiz/<career_name>')
def quiz(career_name):
    if career_name not in career_data:
        return redirect(url_for('home'))

    
    cached_questions = get_cached_quiz(career_name)
    if cached_questions:
        return render_template('quiz.html', career_name=career_name, questions=cached_questions)

   
    if not check_rate_limit():
        print("Rate limit exceeded. Please wait before making more requests.")
        return render_template('quiz_unavailable.html', career_name=career_name)

    # Always generate new quiz using Gemini API
    api_key = os.environ.get('GEMINI_API_KEY', 'AIzaSyCusi29EUENaQ5_H6nfWTEtX5JpU9EM2yw')  # Use env var, fallback to provided key
    if not api_key:
        print("Gemini API key not found. Please set GEMINI_API_KEY environment variable.")
        return render_template('quiz_unavailable.html', career_name=career_name)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    prompt = f"""Generate exactly 10 multiple choice questions for {career_name}. Each question must have exactly 4 options labeled A, B, C, D. Provide the correct answer and difficulty level (Easy, Intermediate, or Difficult). Ensure a mix of easy, intermediate, and difficult questions. Format each question exactly as follows, using bold for markers:

**Q1.** Question text here
A) Option 1
B) Option 2
C) Option 3
D) Option 4
**Answer:** A
**Difficulty:** Easy

**Q2.** Next question text
A) Option 1
B) Option 2
C) Option 3
D) Option 4
**Answer:** B
**Difficulty:** Intermediate

And so on for all 10 questions."""
    data = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ]
    }
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=data, timeout=60)
            response.raise_for_status()
            print("Gemini API response:", response.text)  # Debug log
            response_json = response.json()
            if 'candidates' in response_json and len(response_json['candidates']) > 0:
                response_text = response_json['candidates'][0]['content']['parts'][0]['text']
                questions = parse_gemini_mcqs(response_text)
                # Record API call and cache quiz
                record_api_call()
                cache_quiz(career_name, questions)
                break  # success
            else:
                print("Gemini API error: No candidates in response")  # Debug log
                return render_template('quiz_unavailable.html', career_name=career_name)
        except requests.exceptions.RequestException as e:
            print(f"Gemini API error on attempt {attempt + 1}: {str(e)}")
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                print(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                print("All retries failed.")
                return render_template('quiz_unavailable.html', career_name=career_name)

    # Store in session for submission
    quiz_questions = session.get('quiz_questions', {})
    quiz_questions[career_name] = questions
    session['quiz_questions'] = quiz_questions

    return render_template('quiz.html', career_name=career_name, questions=questions)

@app.route('/quiz/<career_name>/submit', methods=['POST'])
def submit_quiz(career_name):
    if career_name not in career_data:
        return redirect(url_for('home'))

    quiz_questions = session.get('quiz_questions', {}).get(career_name, [])
    if not quiz_questions:
        return redirect(url_for('quiz', career_name=career_name))

    user_answers = {}
    for i in range(len(quiz_questions)):
        user_answers[i] = request.form.get(f'answer_{i}', '')

    # Calculate score
    correct = 0
    total = len(quiz_questions)
    difficulty_breakdown = {'Easy': {'correct': 0, 'total': 0}, 'Intermediate': {'correct': 0, 'total': 0}, 'Difficult': {'correct': 0, 'total': 0}, 'Unknown': {'correct': 0, 'total': 0}}
    review_data = []
    for i, q in enumerate(quiz_questions):
        diff = q['difficulty']
        if diff not in difficulty_breakdown:
            diff = 'Unknown'
        difficulty_breakdown[diff]['total'] += 1
        user_ans = user_answers[i].upper() if user_answers[i] else ''
        correct_ans = q['answer'].upper() if q['answer'] else ''
        is_correct = user_ans == correct_ans
        if is_correct:
            correct += 1
            difficulty_breakdown[diff]['correct'] += 1
        review_data.append({
            'question': q['question'],
            'options': q['options'],
            'user_answer': user_ans,
            'correct_answer': correct_ans,
            'is_correct': is_correct,
            'difficulty': diff
        })
        print(f"Question {i}: User answer: '{user_ans}', Correct answer: '{correct_ans}'")  # Debug log

    percentage = (correct / total) * 100 if total > 0 else 0

    # Suggestions
    suggestions = []
    for diff, data in difficulty_breakdown.items():
        if data['total'] > 0:
            pct = (data['correct'] / data['total']) * 100
            if pct < 50:
                suggestions.append(f"Focus on {diff.lower()} level concepts in {career_name}.")

    return render_template('quiz_report.html', career_name=career_name, correct=correct, total=total, percentage=percentage, difficulty_breakdown=difficulty_breakdown, suggestions=suggestions, review_data=review_data)

if __name__ == '__main__':
    app.run(debug=True)
