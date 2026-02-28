from flask import Flask, render_template, request, redirect, url_for, send_file, jsonify, flash, abort
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime
from dotenv import load_dotenv
import os
import bleach
import time
from functools import lru_cache
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
import json
from config import Config
from ml_service import ml_service
from models import UserManager
from forms import RegistrationForm, LoginForm, ProfileUpdateForm, ChangePasswordForm, ProfileCompletionForm
import requests
from spell_checker import spell_checker
from nutrition_service import nutrition_service

load_dotenv()

# Validate critical environment variables (warn but don't crash)
def validate_env_vars():
    """Validate that critical environment variables are set"""
    missing = []
    if not os.getenv("SECRET_KEY") or os.getenv("SECRET_KEY") == 'your-secret-key-change-this-in-production':
        missing.append("SECRET_KEY")
    if not os.getenv("MONGODB_URI") or os.getenv("MONGODB_URI") == 'mongodb://localhost:27017/':
        missing.append("MONGODB_URI")
    
    if missing:
        print(f"WARNING: Missing or default environment variables: {', '.join(missing)}")
        print("These should be set in Vercel project settings for production deployment.")
    else:
        print("✅ All critical environment variables are set")

# Only validate in production/serverless (not local dev)
if os.environ.get('VERCEL') or os.environ.get('VERCEL_ENV'):
    validate_env_vars()

app = Flask(__name__, 
            static_folder='static',
            template_folder='templates')
app.config.from_object(Config)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

# Initialize Flask-Limiter for rate limiting (prevents brute force attacks)
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# Allowed HTML tags for sanitization (XSS prevention)
ALLOWED_TAGS = ['p', 'h5', 'h6', 'ul', 'ol', 'li', 'strong', 'em', 'i', 'b', 'br', 'span', 'div', 'class']
ALLOWED_ATTRIBUTES = {'*': ['class']}

def sanitize_html(html_content):
    """Sanitize HTML content to prevent XSS attacks"""
    if not html_content:
        return ""
    return bleach.clean(html_content, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, strip=True)

# MongoDB Configuration - Lazy initialization for serverless
_client = None
_db = None
_ingredient_rules = None
_food_entries = None
_recipes = None
_generated_recipes = None
_user_manager = None

def get_db():
    """Lazy initialization of MongoDB connection"""
    global _client, _db, _ingredient_rules, _food_entries, _recipes, _generated_recipes, _user_manager
    
    if _db is None:
        try:
            # Initialize MongoDB client with connection pooling for better performance
            _client = MongoClient(
                Config.MONGODB_URI,
                # Connection Pool Settings
                maxPoolSize=Config.MONGODB_MAX_POOL_SIZE,  # Max connections in pool
                minPoolSize=Config.MONGODB_MIN_POOL_SIZE,  # Min connections to maintain
                maxIdleTimeMS=Config.MONGODB_MAX_IDLE_TIME_MS,  # Max idle time before removal
                waitQueueTimeoutMS=Config.MONGODB_WAIT_QUEUE_TIMEOUT_MS,  # Wait time for connection
                maxConnecting=Config.MONGODB_MAX_CONNECTING,  # Limit concurrent connection establishment
                # Timeout Settings (optimized for serverless)
                serverSelectionTimeoutMS=Config.MONGODB_SERVER_SELECTION_TIMEOUT_MS,
                connectTimeoutMS=Config.MONGODB_CONNECT_TIMEOUT_MS,
                socketTimeoutMS=Config.MONGODB_SOCKET_TIMEOUT_MS,
                # Additional optimizations
                retryWrites=True,  # Automatically retry write operations
                retryReads=True,  # Automatically retry read operations
                # Write Concern - optimize for performance (acknowledge writes but don't wait for journal)
                w=1,  # Wait for acknowledgment from primary
                # Read Preference - read from nearest server for better latency
                readPreference='primaryPreferred',  # Read from primary if available, otherwise secondary
                # Connection monitoring
                appName='health-recipe-modifier',  # Helps identify connections in MongoDB logs
                # Compression for reduced network traffic
                compressors='snappy,zlib',  # Enable compression
            )
            _db = _client[Config.DATABASE_NAME]
            
            # Initialize collections
            _ingredient_rules = _db['ingredient_rules']
            _food_entries = _db['food_entries']
            _recipes = _db['recipes']
            _generated_recipes = _db['generated_recipes']
            
            # Ensure indexes for fast lookups
            try:
                _ingredient_rules.create_index('ingredient', unique=True)
                _generated_recipes.create_index([('condition', 1), ('ingredients_key', 1)])
            except Exception:
                # Index creation is best-effort; ignore if permissions/environment restrict this
                pass
            
            # Initialize User Manager
            _user_manager = UserManager(_db)
            
            # Initialize database on first connection
            initialize_database()
            ensure_core_ingredients()
            
        except Exception as e:
            print(f"MongoDB connection error: {e}")
            # Create dummy collections to prevent crashes
            class DummyCollection:
                def find_one(self, *args, **kwargs): return None
                def find(self, *args, **kwargs): return []
                def insert_one(self, *args, **kwargs): return type('obj', (object,), {'inserted_id': None})()
                def update_one(self, *args, **kwargs): return type('obj', (object,), {'modified_count': 0})()
                def count_documents(self, *args, **kwargs): return 0
                def create_index(self, *args, **kwargs): pass
                def aggregate(self, *args, **kwargs): return []
                def sort(self, *args, **kwargs): return self
                def limit(self, *args, **kwargs): return self
                def delete_one(self, *args, **kwargs): return type('obj', (object,), {'deleted_count': 0})()
            
            _ingredient_rules = DummyCollection()
            _food_entries = DummyCollection()
            _recipes = DummyCollection()
            _generated_recipes = DummyCollection()
            _user_manager = UserManager(None)
    
    return _db

# Accessor functions for collections
def get_ingredient_rules():
    get_db()
    return _ingredient_rules

def get_food_entries():
    get_db()
    return _food_entries


def get_recipes():
    get_db()
    return _recipes

def get_generated_recipes():
    get_db()
    return _generated_recipes

def get_user_manager():
    get_db()
    return _user_manager

# Ingredient rules cache for faster lookups
_ingredient_rules_cache = None
_ingredient_rules_cache_time = 0
_CACHE_TTL = 300  # 5 minutes

def get_cached_ingredient_rules():
    """Get ingredient rules from cache (cached for 5 minutes)"""
    global _ingredient_rules_cache, _ingredient_rules_cache_time
    
    current_time = time.time()
    if _ingredient_rules_cache is None or (current_time - _ingredient_rules_cache_time) > _CACHE_TTL:
        try:
            rules = list(get_ingredient_rules().find({}, {"ingredient": 1, "harmful_for": 1, "alternative": 1, "_id": 0}))
            _ingredient_rules_cache = {doc["ingredient"].lower(): doc for doc in rules if doc.get("ingredient")}
            _ingredient_rules_cache_time = current_time
        except Exception as e:
            print(f"Error caching ingredient rules: {e}")
            if _ingredient_rules_cache is None:
                _ingredient_rules_cache = {}
    
    return _ingredient_rules_cache

def get_cached_db_ingredients():
    """Get all ingredient names from cache"""
    rules = get_cached_ingredient_rules()
    return set(rules.keys())

# Note: All database access should use the getter functions above
# Direct access to collections is no longer supported

@login_manager.user_loader
def load_user(user_id):
    """Load user for Flask-Login"""
    return get_user_manager().get_user_by_id(user_id)

def initialize_database():
    """Initialize the database with sample data if collections are empty"""
    try:
        ingredient_rules_col = get_ingredient_rules()
        
        recipes_col = get_recipes()
    except Exception as e:
        print(f"Error initializing database: {e}")
        return
    
    # Check if ingredient_rules collection is empty
    try:
        if ingredient_rules_col.count_documents({}) == 0:
            sample_rules = [
                {
                    "ingredient": "sugar",
                    "harmful_for": ["diabetes", "obesity"],
                    "alternative": "stevia",
                    "category": "sweetener"
                },
                {
                    "ingredient": "salt",
                    "harmful_for": ["hypertension", "heart_disease"],
                    "alternative": "low-sodium salt",
                    "category": "seasoning"
                },
                {
                    "ingredient": "flour",
                    "harmful_for": ["celiac", "gluten_intolerance"],
                    "alternative": "almond flour",
                    "category": "baking"
                },
                {
                    "ingredient": "butter",
                    "harmful_for": ["cholesterol", "heart_disease"],
                    "alternative": "olive oil",
                    "category": "fat"
                },
                {
                    "ingredient": "milk",
                    "harmful_for": ["lactose_intolerance"],
                    "alternative": "almond milk",
                    "category": "dairy"
                },
                {
                    "ingredient": "eggs",
                    "harmful_for": ["egg_allergy"],
                    "alternative": "flaxseed meal",
                    "category": "protein"
                },
                {
                    "ingredient": "peanuts",
                    "harmful_for": ["peanut_allergy"],
                    "alternative": "sunflower seeds",
                    "category": "nuts"
                },
                {
                    "ingredient": "soy",
                    "harmful_for": ["soy_allergy"],
                    "alternative": "coconut aminos",
                    "category": "protein"
                },
                {
                    "ingredient": "wheat",
                    "harmful_for": ["celiac", "gluten_intolerance"],
                    "alternative": "quinoa",
                    "category": "grain"
                },
                {
                    "ingredient": "corn",
                    "harmful_for": ["corn_allergy"],
                    "alternative": "rice",
                    "category": "grain"
                }
            ]
            ingredient_rules_col.insert_many(sample_rules)
            print("Sample ingredient rules added to database")
    except Exception as e:
        print(f"Error adding sample ingredient rules: {e}")
    
    # Check if patients collection is empty
    

    # Seed sample recipes if empty
    try:
        if recipes_col.count_documents({}) == 0:
            sample_recipes = [
                {
                    "name": "banana bread",
                    "ingredients": ["flour", "banana", "sugar", "butter", "eggs"],
                    "tags": ["dessert", "bread"]
                },
                {
                    "name": "pancakes",
                    "ingredients": ["flour", "milk", "eggs", "butter", "salt", "sugar"],
                    "tags": ["breakfast"]
                },
                {
                    "name": "peanut stir fry",
                    "ingredients": ["soy", "peanuts", "salt", "corn", "butter"],
                    "tags": ["dinner"]
                },
                {
                    "name": "bread",
                    "ingredients": ["flour", "water", "yeast", "salt"],
                    "tags": ["bread", "basic"]
                },
                {
                    "name": "puran poli",
                    "ingredients": ["wheat flour", "chana dal", "jaggery", "ghee", "cardamom", "turmeric", "salt"],
                    "tags": ["indian", "sweet", "festive"]
                }
            ]
            recipes_col.insert_many(sample_recipes)
            print("Sample recipes added to database")
    except Exception as e:
        print(f"Error adding sample recipes: {e}")
    except Exception as e:
        print(f"Error in initialize_database: {e}")

def ensure_core_ingredients():
    """Ensure critical common ingredients exist (for autocomplete and matching)."""
    try:
        ingredient_rules_col = get_ingredient_rules()
        core_ingredients = [
            {
                "ingredient": "pasta",
                "harmful_for": ["celiac", "gluten_intolerance"],
                "alternative": "gluten-free pasta",
                "category": "grain"
            }
        ]
        for item in core_ingredients:
            try:
                ingredient_rules_col.update_one(
                    {"ingredient": item["ingredient"]},
                    {"$setOnInsert": item},
                    upsert=True
                )
            except Exception:
                # Best-effort; ignore failures in restricted environments
                pass
    except Exception as e:
        print(f"Error ensuring core ingredients: {e}")

# def check_ingredients(ingredients, condition):
#     """Check ingredients against patient condition and return harmful/safe lists.

#     Optimized to perform a single batched MongoDB query instead of per-ingredient lookups.
#     """
#     harmful_ingredients = []
#     safe_ingredients = []
#     replacements = {}

#     # Normalize and de-duplicate for query
#     normalized = [ingredient.strip().lower() for ingredient in ingredients if ingredient and ingredient.strip()]
#     unique_ingredients = list({i for i in normalized})

#     if unique_ingredients:
#         try:
#             cursor = get_ingredient_rules().find({"ingredient": {"$in": unique_ingredients}}, {"ingredient": 1, "harmful_for": 1, "alternative": 1, "_id": 0})
#             # Use .get() to prevent KeyError if document structure is unexpected
#             rules_by_ingredient = {doc.get("ingredient"): doc for doc in cursor if doc.get("ingredient")}
#         except Exception as e:
#             print(f"Error querying ingredient rules: {e}")
#             rules_by_ingredient = {}
#     else:
#         rules_by_ingredient = {}

#     for ingredient in normalized:
#         rule = rules_by_ingredient.get(ingredient)
#         if rule and condition in rule.get("harmful_for", []):
#             harmful_ingredients.append(ingredient)
#             replacements[ingredient] = rule.get("alternative")
#         else:
#             safe_ingredients.append(ingredient)

#     return harmful_ingredients, safe_ingredients, replacements

def check_ingredients(ingredients, condition):
    """Check ingredients against patient condition and return harmful/safe lists.

    Optimized to use cached ingredient rules instead of per-ingredient lookups.
    Handles plural/singular safely.
    """
    harmful_ingredients = []
    safe_ingredients = []
    replacements = {}

    # Use cached ingredient rules for fast lookups
    DB_INGREDIENTS = get_cached_db_ingredients()
    rules_by_ingredient = get_cached_ingredient_rules()

    # Safe plural → singular normalizer
    def safe_normalize(name: str) -> str:
        name = name.strip().lower()
        if name.endswith("s"):
            singular = name[:-1]
            if singular in DB_INGREDIENTS:
                return singular
        return name

    # Map original ingredients to normalized
    original_to_normalized = {}
    for ing in ingredients:
        if ing and ing.strip():
            normalized = safe_normalize(ing)
            original_to_normalized[ing] = normalized

    # Determine harmful/safe using normalized ingredient but store original
    for original, ingredient in original_to_normalized.items():
        rule = rules_by_ingredient.get(ingredient)
        if rule and condition in rule.get("harmful_for", []):
            harmful_ingredients.append(original)
            replacements[original] = rule.get("alternative")
        else:
            safe_ingredients.append(original)

    return harmful_ingredients, safe_ingredients, replacements




def format_recipe_html(recipe_text):
    """Convert markdown recipe text to formatted HTML"""
    if not recipe_text:
        return "<p class='text-muted'>No recipe instructions available.</p>"
    
    html_parts = []
    lines = recipe_text.split('\n')
    current_section = ''
    current_content = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        if line.startswith('**') and line.endswith('**'):
            # Header
            if current_content:
                html_parts.append(render_current_section(current_section, current_content))
            header_text = line.replace('**', '').strip()
            
            html_parts.append(f'<h6 class="text-success fw-bold mb-2">{header_text}</h6>')
            
            current_section = ''
            current_content = []
        elif line.startswith('*') and line.endswith('*'):
            # Italic text
            if current_section != 'italic':
                if current_content:
                    html_parts.append(render_current_section(current_section, current_content))
                current_section = 'italic'
                current_content = []
            italic_text = line.replace('*', '').strip()
            html_parts.append(f'<strong><em class="text-success fw-light mb-2">{italic_text}</em></strong>')
        elif line.startswith('- ') or line.startswith('* '):
            # List item
            if current_section != 'list':
                if current_content:
                    html_parts.append(render_current_section(current_section, current_content))
                current_section = 'list'
                current_content = []
            clean_item = line.replace('- ', '').replace('* ', '').replace('**', '').strip()
            current_content.append(clean_item)
            
        elif any(line.startswith(f"{i}.") for i in range(1, 10)):
            # Numbered list item
            if current_section != 'numbered':
                if current_content:
                    html_parts.append(render_current_section(current_section, current_content))
                current_section = 'numbered'
                current_content = []
            clean_item = line.split('.', 1)[1].replace('**', '').strip()
            current_content.append(clean_item)
            
        else:
            # Regular text
            if current_section in ['list', 'numbered']:
                html_parts.append(render_current_section(current_section, current_content))
                current_section = 'text'
                current_content = []
            current_content.append(line.replace('**', '').strip())
    
    # Render final section
    if current_content:
        html_parts.append(render_current_section(current_section, current_content))
    
    return '\n'.join(html_parts)

def render_current_section(section_type, content):
    """Render the current section based on its type"""
    if section_type == 'list':
        items_html = []
        for item in content:
            items_html.append(f'<li class="mb-1"><i class="fas fa-check-circle text-success me-2"></i>{item}</li>')
        return f'<ul class="list-unstyled ms-3 mb-3">{"".join(items_html)}</ul>'
    elif section_type == 'numbered':
        items_html = []
        for item in content:
            items_html.append(f'<li class="mb-2">{item}</li>')
        return f'<ol class="ms-3 mb-3">{"".join(items_html)}</ol>'
    else:
        return f'<p class="mb-3 lh-base">{" ".join(content)}</p>'

def generate_recipe(original_ingredients, safe_ingredients, replacements, condition, recipe_name=None):
    """Generate a modified recipe based on safe ingredients using Gemini API"""
    
    # Create modified ingredient list
    modified_ingredients = []
    for ingredient in original_ingredients:
        ingredient = ingredient.strip().lower()
        if ingredient in replacements:
            modified_ingredients.append(replacements[ingredient])
        else:
            modified_ingredients.append(ingredient)
    
    # Get harmful ingredients for Gemini
    harmful_ingredients = list(replacements.keys())
    
    # Use ML Service to generate detailed recipe based on local data
    recipe = ml_service.generate_recipe_instructions(
        original_ingredients, 
        modified_ingredients, 
        condition, 
        harmful_ingredients,
        recipe_name
    )
    
    return recipe

def _reports_dir():
    """Return a writable reports directory (handles Vercel /tmp)."""
    # Check if we're on Vercel (serverless environment)
    # Vercel sets VERCEL=1 or we can check if /tmp exists and is writable
    is_vercel = os.environ.get('VERCEL') == '1' or os.environ.get('VERCEL_ENV') is not None
    if is_vercel:
        base_dir = '/tmp/reports'
    else:
        base_dir = 'reports'
    os.makedirs(base_dir, exist_ok=True)
    return base_dir

def generate_pdf_report(user_id):
    print(f"[DEBUG] Generating PDF report... {user_id}")
    # make pdf report for user
    try:
        user = get_user_manager().get_user_by_id(user_id)
        entries = list(get_food_entries().find({"patient_id": user_id}).sort("timestamp", -1))
        
        if not entries:
            return None
            
        filename = os.path.join(_reports_dir(), f"patient_{user_id}_report.pdf")
        doc = SimpleDocTemplate(filename, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
        elements = []
        styles = getSampleStyleSheet()
        
        # Title
        title_style = styles['Title']
        title_style.fontSize = 24
        elements.append(Paragraph("Patient Health Report", title_style))
        elements.append(Spacer(1, 24))
        
        # Patient Info Section (Top)
        # Patient ID, Age/Gender, Health Condition, Diet Type, Allergies, Report Generated On, Report Version
        
        # Safe access to user attributes
        u_age = getattr(user, 'age', 'N/A')
        u_gender = getattr(user, 'gender', 'Not Specified') # Field implied by request
        u_condition = getattr(user, 'medical_condition', 'None')
        u_diet = getattr(user, 'diet_type', 'Not Specified') # Field implied by request
        u_allergies = getattr(user, 'allergies', 'Not Specified') # Field implied by request
        
        # If diet/allergies stored elsewhere or need default "N/A"
        if not u_age: u_age = "N/A"
        if not u_condition: u_condition = "None"
        
        user_info = [
            [Paragraph(f"<b>Patient ID:</b> {user_id}", styles['Normal']), Paragraph(f"<b>Report Version:</b> v1.1", styles['Normal'])],
            [Paragraph(f"<b>Age / Gender:</b> {u_age} / {u_gender}", styles['Normal']), Paragraph(f"<b>Report Generated On:</b> {datetime.now().strftime('%d-%m-%Y %H:%M')}", styles['Normal'])],
            [Paragraph(f"<b>Health Condition(s):</b> {u_condition.title()}", styles['Normal']), ""],
            [Paragraph(f"<b>Diet Type:</b> {u_diet}", styles['Normal']), ""],
            [Paragraph(f"<b>Allergies:</b> {u_allergies}", styles['Normal']), ""]
        ]
        
        t_info = Table(user_info, colWidths=[4*inch, 3.5*inch])
        t_info.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ]))
        elements.append(t_info)
        elements.append(Spacer(1, 24))
        
        # Table of Records (Bottom)
        # Headers: Sr No | Recipe Name | Harmful Ingredients | Safe Alternatives | Net Calories | Timestamp
        
        headers = [
            Paragraph("<b>Sr No</b>", styles['Normal']),
            Paragraph("<b>Recipe Name</b>", styles['Normal']),
            Paragraph("<b>Harmful Ingredients</b>", styles['Normal']),
            Paragraph("<b>Safe Alternatives</b>", styles['Normal']),
            Paragraph("<b>Net Calories</b>", styles['Normal']),
            Paragraph("<b>Timestamp</b>", styles['Normal'])
        ]
        
        data = [headers]
        
        for idx, entry in enumerate(entries, 1):
            # 1. Sr No
            sr_no = str(idx)
            
            # 2. Recipe Name (Use input ingredients as proxy if no name)
            # 2. Recipe Name
            recipe_name_text = entry.get("recipe_name", "")
            
            # If no explicit name, try to extract from the generated recipe text (for old records)
            if not recipe_name_text:
                recipe_text = entry.get("recipe", "")
                if recipe_text:
                    lines = recipe_text.split('\n')
                    for line in lines:
                        line = line.strip()
                        if not line: continue
                        # Check for bold title style **Title**
                        if line.startswith('**') and line.endswith('**'):
                            cleaned = line.replace('**', '').strip()
                            # Filter out common section headers
                            if cleaned.lower() not in ['ingredients', 'instructions', 'method', 'directions', 'nutritional info', 'nutrition']:
                                recipe_name_text = cleaned
                                break
            
            # Final fallback
            if not recipe_name_text:
                # User requested avoiding ingredient list in name column
                recipe_name_text = "Custom Recipe"  
                
            # 3. Harmful Ingredients
            harmful_text = ", ".join(entry.get("harmful", [])).title() or "None"
            
            # 4. Safe Alternatives (Using user's safe list or replacements)
            # Request says "Safe Alternatives", but we store full safe list. 
            # Showing full safe list is more useful.
            safe_text = ", ".join(entry.get("safe", [])).title() or "None"

            # 5. Net Calories
            calories_text = "N/A"
            if 'nutrition' in entry and entry['nutrition']:
                nut = entry['nutrition']
                # Check for nested structure (new format)
                if isinstance(nut, dict):
                    if 'macros' in nut and isinstance(nut['macros'], dict):
                        cal_entry = nut['macros'].get('calories')
                        if isinstance(cal_entry, dict):
                            calories_text = f"{int(cal_entry.get('value', 0))} kcal"
                    # Fallback for legacy flat format
                    elif 'calories' in nut:
                        calories_text = f"{int(nut.get('calories', 0))} kcal"
            
            # 6. Timestamp
            ts = entry.get("timestamp")
            timestamp_text = ts.strftime('%Y-%m-%d\n%H:%M') if ts else "N/A"
            
            row = [
                sr_no,
                Paragraph(recipe_name_text, styles['Normal']),
                Paragraph(harmful_text, styles['Normal']),
                Paragraph(safe_text, styles['Normal']),
                calories_text,
                timestamp_text
            ]
            data.append(row)
            
        # Table Styling
        # Columns: 0.5, 1.5, 1.5, 1.5, 1.0, 1.0 = 7.0 inch total width
        col_widths = [0.5*inch, 1.4*inch, 1.5*inch, 1.5*inch, 1.0*inch, 1.1*inch]
        
        t_data = Table(data, colWidths=col_widths, repeatRows=1)
        t_data.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.Color(0.9, 0.9, 0.9)), # Header background
            ('TEXTCOLOR', (0,0), (-1,0), colors.black),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('TOPPADDING', (0,0), (-1,-1), 6),
        ]))
        
        elements.append(t_data)
        
        doc.build(elements)
        print(f"PDF report generated for user {user_id}: {filename}")
        return filename
    except Exception as e:
        print(f"Error generating PDF report: {e}")
        import traceback
        traceback.print_exc()
        return None
    
    
@app.route('/')
def landing_page():
    """Landing page for the application"""
    return render_template('landing_page.html')

def get_profile_warnings(ingredients, user):
    if not user or not user.is_authenticated:
        return []
        
    warnings = []
    
    # 1. Diet Type check
    diet_type = getattr(user, 'diet_type', '')
    if diet_type:
        diet = diet_type.lower()
        non_veg_keywords = ['chicken', 'beef', 'pork', 'meat', 'fish', 'salmon', 'tuna', 'shrimp', 'prawn', 'mutton', 'lamb', 'bacon', 'ham', 'turkey', 'sausage']
        vegan_keywords = non_veg_keywords + ['milk', 'cheese', 'butter', 'egg', 'honey', 'yogurt', 'cream', 'whey']
        
        found_non_veg = [i for i in ingredients if any(k in i.lower() for k in non_veg_keywords)]
        found_animal_products = [i for i in ingredients if any(k in i.lower() for k in vegan_keywords)]
        
        if ('veg' in diet and 'non' not in diet) or 'vegetarian' in diet:
            if found_non_veg:
                warnings.append({
                    'severity': 'danger',
                    'icon': 'alert-triangle',
                    'title': 'Diet Type Conflict: Vegetarian',
                    'message': f'Your profile indicates a vegetarian diet, but these ingredients are non-veg.',
                    'ingredients': found_non_veg
                })
        elif 'vegan' in diet:
            if found_animal_products:
                warnings.append({
                    'severity': 'danger',
                    'icon': 'alert-triangle',
                    'title': 'Diet Type Conflict: Vegan',
                    'message': f'Your profile indicates a vegan diet, but these ingredients contain animal products.',
                    'ingredients': found_animal_products
                })
                
    # 2. Allergies check
    allergies_str = getattr(user, 'allergies', '')
    if allergies_str:
        allergies = [a.strip().lower() for a in allergies_str.split(',') if a.strip()]
        for allergy in allergies:
            # check if allergy is in ingredients
            found_allergy = [i for i in ingredients if allergy in i.lower() or any(len(word) > 2 and word in i.lower() for word in allergy.split())]
            if found_allergy:
                warnings.append({
                    'severity': 'danger',
                    'icon': 'alert-circle',
                    'title': 'Allergy Warning',
                    'message': f'Warning: Contains ingredients matching your reported allergy ({allergy}).',
                    'ingredients': list(set(found_allergy))
                })
                
    # 3. Fitness Goal check (soft warnings)
    goal = getattr(user, 'goal', '')
    if goal:
        high_calorie_keywords = ['sugar', 'butter', 'cream', 'oil', 'mayo', 'cheese', 'bacon', 'syrup', 'caramel', 'chocolate']
        if goal == 'lose_weight':
            found_high_cal = [i for i in ingredients if any(k in i.lower() for k in high_calorie_keywords)]
            if len(found_high_cal) > 0:
                warnings.append({
                    'severity': 'warning',
                    'icon': 'info',
                    'title': 'Goal Reminder: Lose Weight',
                    'message': 'These ingredients are high in calories. Consider using moderation to meet your weight loss goals.',
                    'ingredients': found_high_cal
                })
                
    return warnings

@app.route('/app')
def index():
    """Main page with ingredient submission form"""
    return render_template('index.html')

@app.route('/api/profile-warnings', methods=['POST'])
def api_profile_warnings():
    """API endpoint to get real-time profile warnings for ingredients"""
    if not current_user.is_authenticated:
        return jsonify({'warnings': []})
        
    data = request.get_json(force=True, silent=True) or {}
    ingredients = data.get('ingredients', [])
    warnings = get_profile_warnings(ingredients, current_user)
    return jsonify({'warnings': warnings})

@app.route('/check_ingredients', methods=['POST'])
def check_ingredients_route():
    """Process ingredient submission and return results"""
    
    ingredients_text = request.form.get('ingredients', '').strip()
    recipe_name = request.form.get('recipe_name', '').strip()
    condition = request.form.get('condition', '').strip()
    
    # Validate ingredients input
    if not ingredients_text:
        flash('Please enter at least one ingredient.', 'error')
        return redirect(url_for('index'))
    
    # Validate ingredients length (prevent abuse)
    if len(ingredients_text) > 2000:
        flash('Ingredients text is too long. Please limit to 2000 characters.', 'error')
        return redirect(url_for('index'))
    
    # Validate condition
    if not condition:
        # For authenticated users, use their stored condition
        if current_user.is_authenticated and current_user.medical_condition:
            condition = current_user.medical_condition
        else:
            flash('Please select a medical condition.', 'error')
            return redirect(url_for('index'))
    
    # Parse ingredients
    ingredients = [ingredient.strip() for ingredient in ingredients_text.split(',') if ingredient.strip()]
    
    # For authenticated users, use their stored condition if none provided
    if current_user.is_authenticated and not condition:
        condition = current_user.medical_condition or 'diabetes'
    
    # Check ingredients
    harmful, safe, replacements = check_ingredients(ingredients, condition)

    # Create modified ingredients list
    modified_ingredients = []
    for ingredient in ingredients:
        ingredient_lower = ingredient.strip().lower()
        if ingredient_lower in replacements:
            modified_ingredients.append(replacements[ingredient_lower])
        else:
            modified_ingredients.append(ingredient)

    # Try to serve from cache first to avoid a slow LLM call
    ingredients_key = ",".join(sorted([i.strip().lower() for i in modified_ingredients if i and i.strip()]))
    try:
        cached_doc = get_generated_recipes().find_one({"condition": condition, "ingredients_key": ingredients_key}, {"recipe": 1, "_id": 0})
        if cached_doc and cached_doc.get("recipe"):
            recipe = cached_doc["recipe"]
        else:
            # Generate modified recipe via ML Service
            recipe = generate_recipe(ingredients, safe, replacements, condition, recipe_name)
            try:
                get_generated_recipes().update_one(
                    {"condition": condition, "ingredients_key": ingredients_key},
                    {"$set": {"recipe": recipe, "updated_at": datetime.now()}},
                    upsert=True
                )
            except Exception:
                # Caching is best-effort; ignore failures
                pass
    except Exception as e:
        print(f"Error checking cache: {e}")
        # Generate modified recipe via Gemini
        recipe = generate_recipe(ingredients, safe, replacements, condition, recipe_name)
    
    # Skip synchronous nutrition calculation - will be loaded via AJAX for faster initial page load
    # Pass modified ingredients to frontend for async nutrition loading
    
    # Store in database (without nutrition - will be updated if needed)
    entry_id = None
    if current_user.is_authenticated:
        patient_id = current_user.user_id
        food_entry = {
            "patient_id": patient_id,
            "condition": condition,
            "recipe_name": recipe_name,
            "input_ingredients": ingredients,
            "harmful": harmful,
            "safe": modified_ingredients,
            "recipe": recipe,
            "timestamp": datetime.now(),
            "is_favorite": False,
            "category": "General"
            }
        
        try:
            result = get_food_entries().insert_one(food_entry)
            entry_id = str(result.inserted_id)
        except Exception as e:
            print(f"Error storing food entry: {e}")
    
    # Format recipe for better display and sanitize HTML to prevent XSS
    formatted_recipe = sanitize_html(format_recipe_html(recipe))
    
    # Get profile warnings
    profile_warnings = get_profile_warnings(ingredients, current_user)
    
    return render_template('result.html', 
                         harmful=harmful, 
                         safe=modified_ingredients, 
                         recipe=formatted_recipe,
                         original_ingredients=ingredients,
                         condition=condition,
                         nutrition=None,  # Will be loaded via AJAX
                         entry_id=entry_id, # Pass entry_id for nutrition update
                         nutrition_warnings=[],
                         modified_ingredients_json=json.dumps(modified_ingredients),
                         recipe_name=recipe_name,
                         profile_warnings=profile_warnings,
                         moment=datetime.now().strftime('%B %d, %Y at %I:%M %p'))

@app.route('/generate_report/<patient_id>')
@login_required
def generate_report(patient_id):
    """Generate and download PDF report"""
    if str(current_user.user_id) != str(patient_id):
        abort(403)
    filename = generate_pdf_report(patient_id)
    
    if filename and os.path.exists(filename):
        # Build compact download name: firstname_lastname_DDMMYY_HHMM.pdf
        safe_name = current_user.username.strip().lower().replace(' ', '_')
        now = datetime.now()
        download_name = f"{safe_name}_{now.strftime('%d%m%y')}_{now.strftime('%H%M')}.pdf"
        return send_file(filename, as_attachment=True, download_name=download_name)
    else:
        return "Report generation failed", 400

@app.route('/view_report/<patient_id>')
@login_required
def view_report(patient_id):
    """View PDF report in a dedicated report viewer page"""
    if str(current_user.user_id) != str(patient_id):
        abort(403)
    
    # Generate the PDF (so it's ready for the iframe)
    filename = generate_pdf_report(patient_id)
    report_available = filename is not None and os.path.exists(filename)
    
    # Gather info for the report viewer page
    user = current_user
    total_entries = 0
    try:
        total_entries = get_food_entries().count_documents({"patient_id": patient_id})
    except Exception:
        pass
    
    condition = getattr(user, 'medical_condition', 'Not set') or 'Not set'
    if condition and condition != 'Not set':
        condition = condition.replace('_', ' ').title()
    
    now = datetime.now()
    safe_name = user.username.strip().lower().replace(' ', '_')
    report_filename = f"{safe_name}_{now.strftime('%d%m%y')}_{now.strftime('%H%M')}.pdf"
    
    return render_template('report_viewer.html',
                         patient_id=patient_id,
                         report_available=report_available,
                         username=user.username,
                         condition=condition,
                         total_entries=total_entries,
                         report_filename=report_filename,
                         generated_date=now.strftime('%B %d, %Y'),
                         generated_time=now.strftime('%I:%M %p'))

@app.route('/serve_report_pdf/<patient_id>')
@login_required
def serve_report_pdf(patient_id):
    """Serve the raw PDF file for embedding in the report viewer"""
    if str(current_user.user_id) != str(patient_id):
        abort(403)
    filename = os.path.join(_reports_dir(), f"patient_{patient_id}_report.pdf")
    if filename and os.path.exists(filename):
        return send_file(filename, mimetype='application/pdf')
    else:
        return "Report not found", 404

@app.route('/api/ingredients')
def get_ingredients():
    """API endpoint to get all available ingredients"""
    try:
        ingredients = list(get_ingredient_rules().find({}, {"ingredient": 1, "category": 1, "_id": 0}))
        return jsonify(ingredients)
    except Exception as e:
        print(f"Error getting ingredients: {e}")
        return jsonify([])

@app.route('/api/recipes/ingredients')
def get_recipe_ingredients():
    """API endpoint to get ingredients list by recipe name"""
    name = request.args.get('name', '')
    if not name:
        return jsonify({"error": "Missing recipe name"}), 400
    try:
        # Try exact case-insensitive match first
        recipe_doc = get_recipes().find_one({"name": {"$regex": f"^{name.strip()}$", "$options": "i"}})
        if not recipe_doc:
            # Fallback to partial case-insensitive contains match
            recipe_doc = get_recipes().find_one({"name": {"$regex": name.strip(), "$options": "i"}})
        if not recipe_doc:
            return jsonify({"ingredients": []})
        return jsonify({"ingredients": recipe_doc.get("ingredients", [])})
    except Exception as e:
        print(f"Error getting recipe ingredients: {e}")
        return jsonify({"ingredients": []})

@app.route('/api/ai/extract-ingredients', methods=['POST'])
def ai_extract_ingredients():
    """Use Gemini to extract ingredients from a recipe name or free text.

    Body: { "text": "..." }
    Returns: { ingredients: [ ... ] }
    """
    try:
        data = request.get_json(force=True, silent=True) or {}
        # print(f"Data : {data}")
        text = (data.get('text'))
        # print(f"Text : {text}")
        if not text:
            return jsonify({"ingredients": []}), 200

        # 1) Try ML Service extraction first
        ai_items = ml_service.extract_ingredients(text) or []
        ai_items_normalized = [i.strip().lower() for i in ai_items if i and i.strip()]
        input_normalized = text.lower()

        # If AI returned a meaningful list (not just echoing the input), use it
        if ai_items_normalized and not (len(ai_items_normalized) == 1 and ai_items_normalized[0] == input_normalized):
            return jsonify({"ingredients": ai_items_normalized}), 200

        # 2) Fallback to recipes DB lookup by name (exact, then partial)
        try:
            recipe_doc = get_recipes().find_one({"name": {"$regex": f"^{text}$", "$options": "i"}})
            if not recipe_doc:
                recipe_doc = get_recipes().find_one({"name": {"$regex": text, "$options": "i"}})
            if recipe_doc:
                return jsonify({"ingredients": recipe_doc.get("ingredients", [])}), 200
        except Exception as e:
            print(f"Error looking up recipe: {e}")

        # 3) External recipe API fallback (TheMealDB)
        try:
            api_url = f"https://www.themealdb.com/api/json/v1/1/search.php?s={requests.utils.quote(text)}"
            resp = requests.get(api_url, timeout=3)  # Reduced timeout for faster response
            if resp.ok:
                payload = resp.json() or {}
                meals = payload.get("meals") or []
                if meals:
                    first = meals[0]
                    api_ingredients = []
                    for idx in range(1, 21):
                        val = (first.get(f"strIngredient{idx}") or "").strip()
                        if val:
                            api_ingredients.append(val.lower())
                    if api_ingredients:
                        return jsonify({"ingredients": api_ingredients}), 200
        except Exception:
            pass

        # 4) Last resort: parse comma-separated list; avoid echoing single term
        guessed = [t.strip().lower() for t in text.split(',') if t.strip()]
        if len(guessed) > 1:
            return jsonify({"ingredients": guessed}), 200

        # 5) Heuristic defaults for common single-term dishes
        defaults = {
            "pasta": ["pasta", "olive oil", "garlic", "salt", "water"],
            "pizza": ["pizza dough", "tomato sauce", "mozzarella", "olive oil", "salt"],
            "salad": ["lettuce", "tomato", "cucumber", "olive oil", "salt"],
            "sandwich": ["bread", "lettuce", "tomato", "cheese", "mayonnaise"],
        }
        if input_normalized in defaults:
            return jsonify({"ingredients": defaults[input_normalized]}), 200

        # Nothing reliable
        return jsonify({"ingredients": []}), 200
    except Exception as e:
        print(f"AI extract ingredients error: {e}")
        return jsonify({"ingredients": []}), 200

@app.route('/api/conditions')
def get_conditions():
    """API endpoint to get all available conditions"""
    try:
        pipeline = [
            {"$unwind": "$harmful_for"},
            {"$group": {"_id": "$harmful_for"}},
            {"$sort": {"_id": 1}}
        ]
        conditions = list(get_ingredient_rules().aggregate(pipeline))
        return jsonify([condition["_id"] for condition in conditions])
    except Exception as e:
        print(f"Error getting conditions: {e}")
        return jsonify([])

@app.route('/api/spell-check', methods=['POST'])
def spell_check_recipe_name():
    """Check recipe name spelling and return suggestions"""
    data = request.get_json(force=True, silent=True) or {}
    recipe_name = data.get('recipe_name', '').strip()
    
    if not recipe_name or len(recipe_name) < 2:
        return jsonify({"suggestions": [], "is_correct": True})
    
    try:
        result = spell_checker.check_spelling(recipe_name)
        return jsonify(result)
    except Exception as e:
        print(f"Spell check error: {e}")
        return jsonify({"suggestions": [], "is_correct": True})

@app.route('/api/nutrition', methods=['POST'])
def get_nutrition_data():
    """API endpoint to calculate nutrition for ingredients"""
    try:
        data = request.get_json(force=True, silent=True) or {}
        ingredients = data.get('ingredients', [])
        condition = data.get('condition', '')
        
        if not ingredients:
            return jsonify({'nutrition': None, 'warnings': []})
        
        # Calculate nutrition using nutrition service
        raw_nutrition = nutrition_service.calculate_recipe_nutrition(ingredients)
        formatted_nutrition = nutrition_service.format_nutrition_summary(raw_nutrition)
        
        # Get condition-specific warnings
        warnings = nutrition_service.get_condition_warnings(raw_nutrition, condition)
        
        # Update database if entry_id is provided
        entry_id = data.get('entry_id')
        if entry_id:
            try:
                if current_user.is_authenticated:
                    get_food_entries().update_one(
                        {"_id": ObjectId(entry_id), "patient_id": current_user.user_id},
                        {"$set": {"nutrition": formatted_nutrition}}
                    )
            except Exception as e:
                print(f"Error updating nutrition for entry {entry_id}: {e}")
        
        return jsonify({
            'nutrition': formatted_nutrition,
            'warnings': warnings
        })
    except Exception as e:
        print(f"Nutrition API error: {e}")
        return jsonify({'nutrition': None, 'warnings': [], 'error': str(e)})

# Cache for landing page stats
_landing_stats_cache = None
_landing_stats_cache_time = 0
_STATS_CACHE_TTL = 60  # Cache for 60 seconds

@app.route('/api/stats')
def get_landing_stats():
    """API endpoint to get dynamic statistics for landing page (cached)"""
    global _landing_stats_cache, _landing_stats_cache_time
    
    current_time = time.time()
    
    # Return cached stats if still valid
    if _landing_stats_cache is not None and (current_time - _landing_stats_cache_time) < _STATS_CACHE_TTL:
        return jsonify(_landing_stats_cache)
    
    try:
        # Get total user count from users collection
        total_users = 0
        try:
            user_manager = get_user_manager()
            if user_manager.db is not None:
                users_collection = user_manager.db['users']
                # Use count_documents for accurate count
                total_users = users_collection.count_documents({})
                print(f"[DEBUG] Total users count: {total_users}")
            else:
                print("[DEBUG] Database is None")
        except Exception as e:
            print(f"Error counting users: {e}")
            import traceback
            traceback.print_exc()
            total_users = 0
        
        # Get total recipes modified from food_entries collection
        recipes_modified = 0
        try:
            # Use count_documents for accurate count
            recipes_modified = get_food_entries().count_documents({})
            print(f"[DEBUG] Total recipes: {recipes_modified}")
        except Exception as e:
            print(f"Error counting recipes: {e}")
            recipes_modified = 0
        
        # Count supported health conditions (from cached ingredient rules)
        health_conditions = 12  # Default count
        try:
            # Use cached ingredient rules to avoid DB query
            cached_rules = get_cached_ingredient_rules()
            conditions_set = set()
            for rule in cached_rules.values():
                conditions_set.update(rule.get('harmful_for', []))
            health_conditions = len(conditions_set) if conditions_set else 12
            print(f"[DEBUG] Total conditions: {health_conditions}")
        except Exception as e:
            print(f"Error counting conditions: {e}")
        
        # Build stats response
        stats = {
            'users': total_users,
            'recipes_modified': recipes_modified,
            'health_conditions': health_conditions,
            'accuracy_rate': 99
        }
        
        # Update cache
        _landing_stats_cache = stats
        _landing_stats_cache_time = current_time
        
        print(f"[DEBUG] Returning stats: {stats}")
        return jsonify(stats)
    except Exception as e:
        print(f"Stats API error: {e}")
        import traceback
        traceback.print_exc()
        # Return default values on error
        return jsonify({
            'users': 0,
            'recipes_modified': 0,
            'health_conditions': 12,
            'accuracy_rate': 99
        })

# Authentication Routes
@app.route('/register', methods=['GET', 'POST'])
@limiter.limit("3 per minute", error_message="Too many registration attempts. Please try again later.")
def register():
    """User registration"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        user, error = get_user_manager().create_user(
            username=form.username.data,
            email=form.email.data,
            password=form.password.data,
            medical_condition=form.medical_condition.data if form.medical_condition.data else None
        )
        
        if user:
            login_user(user)
            flash('Account created successfully! Let\'s complete your profile.', 'success')
            return redirect(url_for('complete_profile'))
        else:
            flash(error, 'error')
    
    return render_template('register.html', form=form)

@app.route('/complete-profile', methods=['GET', 'POST'])
@login_required
def complete_profile():
    """Complete user profile with health metrics and goals"""
    # If profile is already completed, redirect to index
    if current_user.profile_completed:
        return redirect(url_for('index'))
    
    form = ProfileCompletionForm()
    if form.validate_on_submit():
        get_user_manager().update_user_profile(
            user_id=current_user.user_id,
            age=form.age.data,
            gender=form.gender.data,
            weight=form.weight.data,
            height=form.height.data,
            diet_type=form.diet_type.data,
            allergies=form.allergies.data,
            calorie_target=form.calorie_target.data,
            goal=form.goal.data
        )
        flash('Profile completed successfully! Welcome to HealthRecipeAI.', 'success')
        return redirect(url_for('index'))
    
    return render_template('complete_profile.html', form=form)


@app.route('/update-health-metrics', methods=['GET', 'POST'])
@login_required
def update_health_metrics():
    """Update user health metrics and goals"""
    form = ProfileCompletionForm()
    
    if form.validate_on_submit():
        get_user_manager().update_user_profile(
            user_id=current_user.user_id,
            age=form.age.data,
            gender=form.gender.data,
            weight=form.weight.data,
            height=form.height.data,
            diet_type=form.diet_type.data,
            allergies=form.allergies.data,
            calorie_target=form.calorie_target.data,
            goal=form.goal.data
        )
        flash('Health metrics updated successfully!', 'success')
        return redirect(url_for('profile'))
    
    # Pre-fill form with current data if GET request
    if request.method == 'GET':
        form.age.data = current_user.age
        form.gender.data = current_user.gender
        form.weight.data = current_user.weight
        form.height.data = current_user.height
        form.diet_type.data = current_user.diet_type
        form.allergies.data = current_user.allergies
        form.calorie_target.data = current_user.calorie_target
        form.goal.data = current_user.goal
    
    return render_template('complete_profile.html', 
                         form=form,
                         page_title="Update Health Metrics",
                         page_subtitle="Update your body metrics and goals",
                         submit_text="Update Metrics",
                         form_action=url_for('update_health_metrics'))


@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute", error_message="Too many login attempts. Please try again later.")
def login():
    """User login"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        # Try to find user by username or email
        user = get_user_manager().get_user_by_username(form.username.data)
        if not user:
            user = get_user_manager().get_user_by_email(form.username.data)
        
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember_me.data)
            get_user_manager().update_last_login(user.user_id)
            
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            else:
                flash(f'Welcome back, {user.username}!', 'success')
                return redirect(url_for('index'))
        else:
            flash('Invalid username/email or password.', 'error')
    
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    """User logout"""
    logout_user()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('index'))

@app.route('/profile')
@login_required
def profile():
    """User profile page"""
    try:
        # Get user statistics
        user_entries = list(get_food_entries().find({"patient_id": current_user.user_id}))
        total_entries = len(user_entries)
        
        total_harmful = sum(len(entry.get('harmful', [])) for entry in user_entries)
        total_safe = sum(len(entry.get('safe', [])) for entry in user_entries)
        
        # Get recent entries
        recent_entries = list(get_food_entries().find({"patient_id": current_user.user_id})
                             .sort("timestamp", -1).limit(10))
        
        # Calculate today's calorie consumption
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_entries = list(get_food_entries().find({
            "patient_id": current_user.user_id,
            "timestamp": {"$gte": today}
        }))
        
        # Sum up calories from today's entries (if nutrition data exists)
        today_calories = 0
        for entry in today_entries:
            if 'nutrition' in entry and entry['nutrition']:
                # Extract calories from nutrition data
                nutrition = entry['nutrition']
                if isinstance(nutrition, dict):
                    # Check for nested structure (new format)
                    if 'macros' in nutrition and isinstance(nutrition['macros'], dict):
                        cal_entry = nutrition['macros'].get('calories')
                        if isinstance(cal_entry, dict):
                            today_calories += int(cal_entry.get('value', 0))
                    # Fallback for legacy flat format
                    elif 'calories' in nutrition:
                        today_calories += int(nutrition.get('calories', 0))
        
        # Calculate BMI if height and weight are available
        bmi = None
        bmi_category = None
        if current_user.height and current_user.weight:
            height_m = current_user.height / 100  # Convert cm to meters
            bmi = round(current_user.weight / (height_m ** 2), 1)
            
            # Categorize BMI
            if bmi < 18.5:
                bmi_category = "Underweight"
            elif 18.5 <= bmi < 25:
                bmi_category = "Normal"
            elif 25 <= bmi < 30:
                bmi_category = "Overweight"
            else:
                bmi_category = "Obese"
        
        # Calculate calorie progress percentage
        calorie_percentage = 0
        if current_user.calorie_target and current_user.calorie_target > 0:
            calorie_percentage = min(round((today_calories / current_user.calorie_target) * 100), 100)
        
    except Exception as e:
        print(f"Error getting user profile data: {e}")
        user_entries = []
        total_entries = 0
        total_harmful = 0
        total_safe = 0
        recent_entries = []
        today_calories = 0
        calorie_percentage = 0
        bmi = None
        bmi_category = None
    
    # Create forms
    profile_form = ProfileUpdateForm()
    password_form = ChangePasswordForm()
    
    # Set current values
    profile_form.email.data = current_user.email
    profile_form.medical_condition.data = current_user.medical_condition
    
    return render_template('profile.html', 
                         profile_form=profile_form,
                         password_form=password_form,
                         total_entries=total_entries,
                         harmful_ingredients=total_harmful,
                         safe_ingredients=total_safe,
                         recent_entries=recent_entries,
                         today_calories=today_calories,
                         calorie_percentage=calorie_percentage,
                         bmi=bmi,
                         bmi_category=bmi_category)

@app.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    """Update user profile"""
    form = ProfileUpdateForm()
    if form.validate_on_submit():
        try:
            # Update user data
            get_user_manager().update_medical_condition(current_user.user_id, form.medical_condition.data)
            
            # Update email if changed
            if form.email.data != current_user.email:
                # Check if email is already taken
                existing_user = get_user_manager().get_user_by_email(form.email.data)
                if existing_user and existing_user.user_id != current_user.user_id:
                    flash('Email address is already in use.', 'error')
                    return redirect(url_for('profile'))
                
                # Update email
                get_user_manager().users.update_one(
                    {'user_id': current_user.user_id},
                    {'$set': {'email': form.email.data}}
                )
        except Exception as e:
            print(f"Error updating profile: {e}")
            flash('Error updating profile. Please try again.', 'error')
            return redirect(url_for('profile'))
        
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile'))
    
    flash('Please correct the errors below.', 'error')
    return redirect(url_for('profile'))

@app.route('/change_password', methods=['POST'])
@login_required
def change_password():
    """Change user password"""
    form = ChangePasswordForm()
    if form.validate_on_submit():
        try:
            if current_user.check_password(form.current_password.data):
                # Update password
                current_user.set_password(form.new_password.data)
                get_user_manager().users.update_one(
                    {'user_id': current_user.user_id},
                    {'$set': {'password_hash': current_user.password_hash}}
                )
                flash('Password changed successfully!', 'success')
            else:
                flash('Current password is incorrect.', 'error')
        except Exception as e:
            print(f"Error changing password: {e}")
            flash('Error changing password. Please try again.', 'error')
    
    return redirect(url_for('profile'))

@app.route('/cookbook')
@login_required
def cookbook():
    """Personal Cookbook (Meal Portfolio) page"""
    try:
        # Get all favorited entries for the user, newest first
        favorite_entries = list(get_food_entries().find({
            "patient_id": current_user.user_id,
            "is_favorite": True
        }).sort("timestamp", -1))
        
        # Deduplicate: keep only the most recent entry per unique recipe name
        seen_names = set()
        unique_entries = []
        for entry in favorite_entries:
            # Build a normalised key from the recipe name (case-insensitive, trimmed)
            name = (entry.get('recipe_name') or '').strip().lower()
            if not name:
                # Fallback: use sorted ingredients as the key
                ings = entry.get('input_ingredients') or entry.get('safe') or []
                name = ','.join(sorted(i.strip().lower() for i in ings if i))
            if name and name in seen_names:
                continue  # skip duplicate
            if name:
                seen_names.add(name)
            unique_entries.append(entry)
        
        favorite_entries = unique_entries
        
        # Get unique categories used by the user
        categories = sorted(list(set(entry.get('category', 'General') for entry in favorite_entries)))
        if 'General' not in categories:
            categories.insert(0, 'General')
            
    except Exception as e:
        print(f"Error getting cookbook data: {e}")
        favorite_entries = []
        categories = ['General']
    
    return render_template('cookbook.html', 
                         entries=favorite_entries, 
                         categories=categories)

@app.route('/api/favorite/<entry_id>', methods=['POST'])
@login_required
def toggle_favorite(entry_id):
    """Toggle favorite status for a recipe entry"""
    try:
        entry = get_food_entries().find_one({"_id": ObjectId(entry_id), "patient_id": current_user.user_id})
        if not entry:
            return jsonify({"error": "Entry not found"}), 404
            
        new_status = not entry.get('is_favorite', False)
        get_food_entries().update_one(
            {"_id": ObjectId(entry_id)},
            {"$set": {"is_favorite": new_status}}
        )
        return jsonify({"success": True, "is_favorite": new_status})
    except Exception as e:
        print(f"Error toggling favorite: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/categorize/<entry_id>', methods=['POST'])
@login_required
def update_category(entry_id):
    """Update category for a recipe entry"""
    try:
        data = request.get_json()
        category = data.get('category', 'General').strip()
        
        if not category:
            category = 'General'
            
        result = get_food_entries().update_one(
            {"_id": ObjectId(entry_id), "patient_id": current_user.user_id},
            {"$set": {"category": category, "is_favorite": True}} # Categorizing automatically makes it a favorite
        )
        
        if result.modified_count == 0:
            return jsonify({"error": "Entry not found or not modified"}), 404
            
        return jsonify({"success": True, "category": category})
    except Exception as e:
        print(f"Error updating category: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Initialize database on startup (only for local development)
    # On Vercel, initialization happens lazily on first request
    initialize_database()
    ensure_core_ingredients()
    
    # Create reports directory
    os.makedirs("reports", exist_ok=True)
    
    # Run with debug mode enabled for auto-reload
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=True, extra_files=[
        'templates/',
        'static/css/',
        'static/js/'
    ])
