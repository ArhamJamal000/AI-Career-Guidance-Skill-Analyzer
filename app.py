from flask import Flask, render_template, request, redirect, url_for, session
import os
import json
from collections import defaultdict
import json as json_module
import requests
import re

app = Flask(__name__)
app.secret_key = os.urandom(24)  # For session

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
                max_score += 5  # Max rating is 5
                if avg_rating <= 2.5:  # Consider skills with rating <= 2.5 as low-rated
                    low_rated_skills.append(skill)
            else:
                missing_skills.append(skill)
                max_score += 5

        match_percentage = (total_score / max_score) * 100 if max_score > 0 else 0

        # Calculate readiness level based on match percentage
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

    # Identify missing and low-rated skills
    for skill in career_data[career]['required_skills']:
        if skill not in skill_levels:
            missing_skills.append(skill)
        elif skill_levels[skill]['average_rating'] <= 2.5:
            low_rated_skills.append(skill)

    # Customize roadmap to focus on missing/low-rated skills first
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
    blocks = re.split(r"Q\d+\.", response_text)
    for block in blocks:
        block = block.strip()
        if not block: continue
        lines = block.split("\n")
        q_text = lines[0].strip()
        options = [line[3:].strip() for line in lines if re.match(r"^[A-D]\)", line.strip())]
        answer_match = re.search(r"Answer:\s*([A-D])", block)
        answer = answer_match.group(1) if answer_match else None
        diff_match = re.search(r"Difficulty:\s*(\w+)", block, re.IGNORECASE)
        difficulty = diff_match.group(1).capitalize() if diff_match else "Unknown"
        questions.append({"question": q_text, "options": options, "answer": answer, "difficulty": difficulty})
    return questions

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
        top_3 = recommendations[:3]  # Show top 3 career recommendations

        skill_levels_json = json_module.dumps(skill_levels)
        return render_template('results.html', recommendations=top_3, user_ratings=user_ratings, skill_levels=skill_levels, skill_levels_json=skill_levels_json)

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

    # Always generate new quiz using Gemini API
    api_key = "AIzaSyCusi29EUENaQ5_H6nfWTEtX5JpU9EM2yw"  # Provided API key
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent?key={api_key}"
    prompt = f"Generate 10 multiple choice questions for {career_name}. Each question should have 4 options A-D, the correct answer, and difficulty level (Easy, Intermediate, Difficult). Ensure a mix of easy, intermediate, and difficult questions. Format as Q1. Question text\nA) option1\nB) option2\nC) option3\nD) option4\nAnswer: A\nDifficulty: Easy\n\nQ2. ..."
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
    try:
        response = requests.post(url, json=data)
        response.raise_for_status()
        print("Gemini API response:", response.text)  # Debug log
        response_text = response.json()['candidates'][0]['content']['parts'][0]['text']
        questions = parse_gemini_mcqs(response_text)
    except Exception as e:
        print("Gemini API error:", str(e))  # Debug log
        # API failure
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
    for i, q in enumerate(quiz_questions):
        diff = q['difficulty']
        if diff not in difficulty_breakdown:
            diff = 'Unknown'
        difficulty_breakdown[diff]['total'] += 1
        if user_answers[i] == q['answer']:
            correct += 1
            difficulty_breakdown[diff]['correct'] += 1

    percentage = (correct / total) * 100 if total > 0 else 0

    # Suggestions
    suggestions = []
    for diff, data in difficulty_breakdown.items():
        if data['total'] > 0:
            pct = (data['correct'] / data['total']) * 100
            if pct < 50:
                suggestions.append(f"Focus on {diff.lower()} level concepts in {career_name}.")

    return render_template('quiz_report.html', career_name=career_name, correct=correct, total=total, percentage=percentage, difficulty_breakdown=difficulty_breakdown, suggestions=suggestions)

if __name__ == '__main__':
    app.run(debug=True)
