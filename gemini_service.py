import os
import google.generativeai as genai
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Gemini API
api_key = os.getenv("GEMINI_API_KEY")
if api_key and api_key != "your_gemini_api_key_here":
    genai.configure(api_key=api_key)
    # Using gemini-1.5-flash for speed and reliability
    model = genai.GenerativeModel('gemini-2.5-flash')
else:
    if api_key == "your_gemini_api_key_here":
        logger.warning("GEMINI_API_KEY is still the placeholder. Please update it in .env")
    else:
        logger.warning("GEMINI_API_KEY not found in environment variables")
    model = None

class GeminiService:
    def __init__(self):
        self.enabled = model is not None

    def generate_recipe(self, condition, original_ingredients, modified_ingredients, harmful_ingredients, user_profile=None):
        """
        Generate a detailed recipe using Gemini API
        """
        if not self.enabled:
            logger.error("Gemini API is not configured")
            return None

        # Build profile context
        profile_context = ""
        if user_profile:
            diet = user_profile.get('diet_type')
            allergies = user_profile.get('allergies')
            if diet:
                profile_context += f"- Diet Type: {diet}\n"
            if allergies:
                profile_context += f"- Allergies: {allergies}\n"

        prompt = f"""
You are a medical chef. Create a concise, medically-safe recipe.

Profile:
- Condition: {condition}
{profile_context}- Safe Ingredients: {', '.join(modified_ingredients)}
- Omit/Replace: {', '.join(harmful_ingredients)}

Task:
Provide a brief, direct recipe for 2 servings. Use simple formatting.
STRICTLY AVOID any ingredients listed in 'Allergies' or 'Omit/Replace'.
Respect the 'Diet Type' preferences.

Format:
**Health Logic**
(A single, impactful sentence on why this is safer for {condition})

**Ingredients**
(Precise items and quantities)

**Instructions**
(Short, step-by-step bullet points)

**Quick Tips**
(1-2 essential medical tips for this specific meal)
        """

        try:
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Error generating recipe with Gemini: {e}")
            return None

    def extract_ingredients(self, text):
        """
        Extract a list of ingredients from a recipe name or free text
        """
        if not self.enabled:
            logger.error("Gemini API is not configured")
            return None

        prompt = f"""
You are a recipe expert. Extract a COMPREHENSIVE comma-separated list of standard ingredients for the dish: "{text}"

Rules:
1. Return ONLY the ingredient names, separated by commas.
2. Include ALL standard components (e.g., for 'juice', include water, sugar/sweetener, lemon, etc., if typically used).
3. Do not include quantities (like "1 cup"), units, or prepare instructions. Just the core ingredient names.
4. Be accurate to the recipe name provided.
5. If "{text}" is already a list of ingredients, just return them cleaned up.

Example Input: "Lemonade"
Output: lemon juice, water, sugar, honey, ice cubes, mint leaves

Example Input: "Puran Poli"
Output: wheat flour, chana dal, jaggery, ghee, cardamom, nutmeg, turmeric, salt

Input: "{text}"
Output:
        """

        try:
            response = model.generate_content(prompt)
            ingredients_text = response.text.strip()
            if not ingredients_text:
                return []
            return [i.strip().lower() for i in ingredients_text.split(',') if i.strip()]
        except Exception as e:
            logger.error(f"Error extracting ingredients with Gemini: {e}")
            return None

    def generate_custom_content(self, prompt):
        """
        Generic method to generate content using Gemini for any given prompt
        """
        if not self.enabled:
            return None
        try:
            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            logger.error(f"Error generating custom content with Gemini: {e}")
            return None

# Global instance
gemini_service = GeminiService()
