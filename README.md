# 🧠 Health-Aware Recipe Modifier

A full-stack web application that helps patients modify their recipes based on their medical conditions. The app automatically detects harmful ingredients and suggests healthy alternatives, generating personalized recipes tailored to specific health needs.

## 🎯 Features

### Core Functionality
- **Ingredient Analysis**: Automatically detects harmful ingredients based on medical conditions
- **Smart Replacements**: Suggests healthy alternatives for harmful ingredients
- **ML-Powered Recipe Retrieval**: Uses a custom ML model to find and adapt professional recipes
- **Mathematical Optimization**: Uses ensemble similarity metrics (TF-IDF, Levenshtein, Jaro-Winkler) for high-accuracy recipe matching
- **Enhanced PDF Reports**: Professional, well-formatted reports with summary statistics
- **User Authentication**: Secure registration, login, and profile management
- **Individual Data Storage**: Each user's data is stored separately and securely
- **Session Logging**: Stores all food entries in MongoDB for tracking
- **View & Download Reports**: Both view in browser and download functionality

### Supported Medical Conditions
- Diabetes
- Hypertension
- Heart Disease
- Celiac Disease
- Gluten Intolerance
- Lactose Intolerance
- Egg Allergy
- Peanut Allergy
- Soy Allergy
- Corn Allergy
- Obesity
- High Cholesterol

### Ingredient Database
The app includes a comprehensive database of ingredients with their health implications:
- **Sugar** → Stevia (for diabetes/obesity)
- **Salt** → Low-sodium salt (for hypertension/heart disease)
- **Flour** → Almond flour (for celiac/gluten intolerance)
- **Butter** → Olive oil (for cholesterol/heart disease)
- **Milk** → Almond milk (for lactose intolerance)
- And many more...

## 🏗 Technology Stack

- **Frontend**: HTML, CSS, JavaScript, Bootstrap 5
- **Backend**: Python Flask
- **Database**: MongoDB with PyMongo
- **PDF Generation**: ReportLab with improved formatting
- **ML Integration**: Scikit-Learn based TF-IDF and ensemble similarity model for recipe matching
- **Authentication**: Flask-Login with secure password hashing
- **Forms**: Flask-WTF with validation
- **Styling**: Custom CSS with Font Awesome icons

## 📁 Project Structure

```
project/
├── app.py                 # Main Flask application
├── config.py              # Configuration settings
├── models.py              # User models and authentication logic
├── ml_service.py          # AI recipe generation logic (Gemini API)
├── nutrition_service.py   # USDA API integration & nutrition analysis
├── forms.py               # Flask-WTF forms for auth and profile
├── database_setup.py      # Database initialization script
├── spell_checker.py       # Ingredient spell checking utility
├── requirements.txt       # Python dependencies
├── templates/             # Jinja2 HTML templates
├── static/                # CSS, client-side JS, and assets
├── reports/               # Generated PDF reports (ReportLab)
└── scripts/               # Utility scripts and data seeding
```

## 🚀 Installation & Setup

### Prerequisites
- Python 3.7 or higher
- MongoDB (Local or Atlas)
- Google Gemini API Key
- USDA FoodData Central API Key

### Step 1: Clone the Project
```bash
git clone <repository-url>
cd Recipe-Modifier-main
```

### Step 2: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 3: Environment Variables
Create a `.env` file in the root directory:
```env
SECRET_KEY=your_secret_key
MONGODB_URI=your_mongodb_connection_string
GEMINI_API_KEY=your_gemini_api_key
USDA_API_KEY=your_usda_api_key
```

### Step 4: Run the Application
```bash
python app.py
```
The app will be available at `http://localhost:5000`.

## 📖 Usage Guide

### 1. User Authentication
- **Register**: Create a personalized account with your medical condition.
- **Login**: Secure access to your profile and recipe history.
- **Profile**: Update your health profile and view statistics.

### 2. Recipe Modification
- **Analyze**: Enter ingredients or a recipe name.
- **Modify**: The AI identifies harmful ingredients and suggests safe alternatives.
- **Generate**: Get a complete, step-by-step healthy recipe tailored to your condition.

### 3. Nutrition & Reports
- **Nutrition**: View detailed macronutrient and micronutrient breakdown.
- **PDF Reports**: Download professional health reports of your recipe history.

## 🚀 Deployment (Render)

The application is optimized for deployment on **Render**.

1. **Connect Repository**: Link your GitHub/GitLab repository to Render.
2. **Environment Variables**: Add `SECRET_KEY`, `MONGODB_URI`, `GEMINI_API_KEY`, and `USDA_API_KEY` in Render's dashboard.
3. **Build Command**: `pip install -r requirements.txt`
4. **Start Command**: `gunicorn app:app` (or `python app.py` if using the built-in server for simple cases).
5. **Disk (Optional)**: If you want persistent PDF reports, attach a Render Disk to the `/reports` directory.

## 🔒 Security Notes
- Uses **Flask-Login** for secure session management.
- Passwords are encrypted using **Werkzeug** security helpers.
- **Flask-Limiter** prevents brute-force attacks.
- **Bleach** sanitization prevents XSS in generated content.
- Always consult healthcare providers for medical advice.

---

**⚠️ Disclaimer**: This application is for educational and demonstration purposes only. Always consult with qualified healthcare professionals for medical advice and dietary recommendations.
