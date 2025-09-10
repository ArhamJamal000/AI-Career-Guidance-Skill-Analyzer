# Flask Career Guidance System

A web-based career guidance application built with Flask that helps users assess their skills and get personalized career recommendations. The system includes dynamic quiz generation using Google's Gemini AI for testing knowledge in various career fields.

## Features

- **Skill Assessment**: Multi-step questionnaire to rate proficiency in various programming languages and frameworks
- **Career Recommendations**: AI-powered analysis to match user skills with suitable careers
- **Personalized Roadmaps**: Customized learning paths based on skill gaps and current levels
- **Dynamic Quizzes**: Generate fresh multiple-choice questions for any career using Gemini AI
- **Quiz Scoring**: Detailed score breakdown with difficulty analysis and improvement suggestions

## Prerequisites

- Python 3.7+
- Flask
- Google Gemini API key

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd flask-career-guidance
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up your Gemini API key:
   - Get an API key from [Google AI Studio](https://makersuite.google.com/app/apikey)
   - Replace the `api_key` variable in `app.py` with your actual API key

4. Ensure data files are in place:
   - `data/careers.json` - Career information and requirements
   - `data/skills.json` - Skills and frameworks data
   - Templates in `templates/` directory

## Usage

1. Run the application:
   ```bash
   python app.py
   ```

2. Open your browser and navigate to `http://localhost:5000`

3. Follow the guided process:
   - Select your skill areas
   - Rate your proficiency in frameworks
   - View career recommendations
   - Explore personalized roadmaps
   - Take dynamic quizzes for selected careers

## Project Structure

```
flask-career-guidance/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── data/
│   ├── careers.json       # Career data and requirements
│   └── skills.json        # Skills and frameworks
├── templates/             # HTML templates
│   ├── index.html
│   ├── frameworks.html
│   ├── results.html
│   ├── roadmap.html
│   ├── quiz.html
│   ├── quiz_report.html
│   └── quiz_unavailable.html
└── README.md
```

## API Endpoints

- `GET /` - Home page
- `GET/POST /frameworks` - Skill selection
- `GET/POST /analyze` - Skill analysis and recommendations
- `GET /roadmap/<career>` - Career roadmap
- `GET /quiz/<career_name>` - Generate and display quiz
- `POST /quiz/<career_name>/submit` - Submit quiz answers

## Configuration

- **Session Management**: Uses Flask sessions for user data persistence
- **API Integration**: Gemini AI for dynamic quiz generation
- **Error Handling**: Graceful handling of API failures with fallback pages

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Built with Flask web framework
- Powered by Google Gemini AI
- Career data sourced from industry standards
