"""
Nutrition Service Module
Fetches nutrition data from USDA FoodData Central API for recipe ingredients.
Provides calorie, macro, vitamin, and mineral calculations.
"""

import os
import requests
import logging
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# USDA FoodData Central API configuration
USDA_API_BASE_URL = "https://api.nal.usda.gov/fdc/v1"


class NutritionService:
    """Service for fetching and calculating nutrition data from USDA API."""
    
    # Nutrient IDs from USDA API
    NUTRIENT_IDS = {
        'calories': 1008,       # Energy (kcal)
        'protein': 1003,        # Protein (g)
        'total_fat': 1004,      # Total Fat (g)
        'saturated_fat': 1258,  # Saturated Fat (g)
        'carbohydrates': 1005,  # Carbohydrates (g)
        'fiber': 1079,          # Fiber (g)
        'sugar': 2000,          # Total Sugars (g)
        'sodium': 1093,         # Sodium (mg)
        'potassium': 1092,      # Potassium (mg)
        'calcium': 1087,        # Calcium (mg)
        'iron': 1089,           # Iron (mg)
        'vitamin_a': 1106,      # Vitamin A (IU)
        'vitamin_c': 1162,      # Vitamin C (mg)
        'vitamin_d': 1114,      # Vitamin D (IU)
        'vitamin_b12': 1178,    # Vitamin B12 (mcg)
        'cholesterol': 1253,    # Cholesterol (mg)
    }
    
    # Daily recommended values for calculating percentages
    DAILY_VALUES = {
        'calories': 2000,
        'protein': 50,
        'total_fat': 65,
        'saturated_fat': 20,
        'carbohydrates': 300,
        'fiber': 25,
        'sugar': 50,
        'sodium': 2300,
        'potassium': 4700,
        'calcium': 1000,
        'iron': 18,
        'vitamin_a': 5000,  # IU
        'vitamin_c': 90,
        'vitamin_d': 800,   # IU
        'vitamin_b12': 2.4,
        'cholesterol': 300,
    }
    
    # Condition-specific nutrient thresholds for warnings
    CONDITION_THRESHOLDS = {
        'diabetes': {
            'sugar': {'max': 25, 'warning': 'High sugar content - consider portion control'},
            'carbohydrates': {'max': 45, 'warning': 'High carb content - monitor blood glucose'},
        },
        'hypertension': {
            'sodium': {'max': 500, 'warning': 'High sodium content - may affect blood pressure'},
            'saturated_fat': {'max': 7, 'warning': 'Limit saturated fat for heart health'},
        },
        'heart_disease': {
            'cholesterol': {'max': 100, 'warning': 'High cholesterol - limit intake'},
            'saturated_fat': {'max': 5, 'warning': 'Reduce saturated fat for heart health'},
            'sodium': {'max': 400, 'warning': 'High sodium may affect heart health'},
        },
        'kidney_disease': {
            'potassium': {'max': 200, 'warning': 'High potassium - consult your dietitian'},
            'sodium': {'max': 300, 'warning': 'Limit sodium for kidney health'},
            'protein': {'max': 20, 'warning': 'Monitor protein intake'},
        },
        'obesity': {
            'calories': {'max': 400, 'warning': 'High calorie content - watch portion size'},
            'total_fat': {'max': 15, 'warning': 'High fat content - choose lean alternatives'},
            'sugar': {'max': 15, 'warning': 'Limit added sugars for weight management'},
        },
    }
    
    def __init__(self):
        """Initialize the Nutrition Service with USDA API key."""
        self.api_key = os.getenv("USDA_API_KEY")
        self.available = bool(self.api_key)
        self._cache = {}  # Simple cache for ingredient nutrition
        
        if not self.available:
            logger.warning("USDA_API_KEY not found. Nutrition features will use estimates.")
    
    def search_food(self, query: str, limit: int = 5) -> list:
        """
        Search for foods in USDA database.
        
        Args:
            query: Food name to search for
            limit: Maximum number of results
            
        Returns:
            List of matching food items
        """
        if not self.available:
            return []
        
        try:
            url = f"{USDA_API_BASE_URL}/foods/search"
            params = {
                'api_key': self.api_key,
                'query': query,
                'pageSize': limit,
                'dataType': ['Foundation', 'SR Legacy', 'Survey (FNDDS)']
            }
            
            response = requests.get(url, params=params, timeout=3)  # Reduced timeout for faster response
            response.raise_for_status()
            
            data = response.json()
            return data.get('foods', [])
            
        except requests.RequestException as e:
            logger.error(f"USDA API search error for '{query}': {e}")
            return []
    
    def get_ingredient_nutrition(self, ingredient: str) -> dict:
        """
        Get nutrition data for a single ingredient per 100g serving.
        Uses caching to avoid repeated API calls.
        
        Args:
            ingredient: Name of the ingredient
            
        Returns:
            Dictionary with nutrition values
        """
        # Check cache first
        cache_key = ingredient.lower().strip()
        if cache_key in self._cache:
            return self._cache[cache_key].copy()
        
        # Initialize with zeros
        nutrition = {key: 0 for key in self.NUTRIENT_IDS.keys()}
        nutrition['ingredient'] = ingredient
        nutrition['found'] = False
        
        if not self.available:
            result = self._estimate_nutrition(ingredient)
            self._cache[cache_key] = result
            return result
        
        foods = self.search_food(ingredient, limit=1)
        
        if not foods:
            logger.info(f"No USDA data found for '{ingredient}', using estimates")
            result = self._estimate_nutrition(ingredient)
            self._cache[cache_key] = result
            return result
        
        food = foods[0]
        nutrition['found'] = True
        nutrition['description'] = food.get('description', ingredient)
        
        # Extract nutrient values
        for nutrient in food.get('foodNutrients', []):
            nutrient_id = nutrient.get('nutrientId')
            value = nutrient.get('value', 0)
            
            for key, nid in self.NUTRIENT_IDS.items():
                if nutrient_id == nid:
                    nutrition[key] = round(value, 2)
                    break
        
        # Cache the result
        self._cache[cache_key] = nutrition
        return nutrition
    
    def calculate_recipe_nutrition(self, ingredients: list, servings: int = 4) -> dict:
        """
        Calculate total nutrition for a list of ingredients.
        Uses concurrent requests for faster processing.
        
        Args:
            ingredients: List of ingredient names
            servings: Number of servings the recipe makes
            
        Returns:
            Dictionary with total and per-serving nutrition
        """
        # Filter valid ingredients
        valid_ingredients = [ing.strip() for ing in ingredients if ing and ing.strip()]
        
        if not valid_ingredients:
            return self._empty_nutrition_result(servings)
        
        # Initialize totals
        totals = {key: 0 for key in self.NUTRIENT_IDS.keys()}
        ingredient_details = []
        found_count = 0
        
        # Use ThreadPoolExecutor for concurrent API calls (max 8 concurrent for faster processing)
        with ThreadPoolExecutor(max_workers=8) as executor:
            # Submit all ingredient lookups concurrently
            future_to_ingredient = {
                executor.submit(self.get_ingredient_nutrition, ing): ing 
                for ing in valid_ingredients
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_ingredient):
                try:
                    nutrition = future.result()
                    ingredient_details.append(nutrition)
                    
                    if nutrition.get('found'):
                        found_count += 1
                    
                    # Add to totals (assuming ~100g per ingredient as default)
                    for key in self.NUTRIENT_IDS.keys():
                        totals[key] += nutrition.get(key, 0)
                except Exception as e:
                    logger.error(f"Error fetching nutrition: {e}")
        
        # Calculate per-serving values
        per_serving = {}
        for key, value in totals.items():
            per_serving[key] = round(value / servings, 1) if servings > 0 else value
        
        # Calculate daily value percentages
        daily_percentages = {}
        for key, value in per_serving.items():
            dv = self.DAILY_VALUES.get(key, 0)
            if dv > 0:
                daily_percentages[key] = round((value / dv) * 100, 1)
            else:
                daily_percentages[key] = 0
        
        return {
            'totals': totals,
            'per_serving': per_serving,
            'daily_percentages': daily_percentages,
            'servings': servings,
            'ingredients_analyzed': len(valid_ingredients),
            'ingredients_found': found_count,
            'ingredient_details': ingredient_details,
            'accuracy': 'estimated' if found_count < len(valid_ingredients) / 2 else 'calculated'
        }
    
    def _empty_nutrition_result(self, servings: int) -> dict:
        """Return empty nutrition result for invalid input."""
        empty = {key: 0 for key in self.NUTRIENT_IDS.keys()}
        return {
            'totals': empty,
            'per_serving': empty,
            'daily_percentages': empty,
            'servings': servings,
            'ingredients_analyzed': 0,
            'ingredients_found': 0,
            'ingredient_details': [],
            'accuracy': 'estimated'
        }
    
    def get_condition_warnings(self, nutrition: dict, condition: str) -> list:
        """
        Get health warnings based on condition and nutrition values.
        
        Args:
            nutrition: Nutrition data dictionary with per_serving values
            condition: Patient's health condition
            
        Returns:
            List of warning messages
        """
        warnings = []
        condition_lower = condition.lower().replace(' ', '_') if condition else ''
        
        thresholds = self.CONDITION_THRESHOLDS.get(condition_lower, {})
        per_serving = nutrition.get('per_serving', {})
        
        for nutrient, limits in thresholds.items():
            value = per_serving.get(nutrient, 0)
            max_value = limits.get('max', float('inf'))
            
            if value > max_value:
                warnings.append({
                    'nutrient': nutrient.replace('_', ' ').title(),
                    'value': value,
                    'threshold': max_value,
                    'message': limits.get('warning', f'High {nutrient} content'),
                    'severity': 'warning' if value < max_value * 1.5 else 'danger'
                })
        
        return warnings
    
    def _estimate_nutrition(self, ingredient: str) -> dict:
        """
        Provide estimated nutrition when API data isn't available.
        Uses general category-based estimates.
        
        Args:
            ingredient: Name of the ingredient
            
        Returns:
            Dictionary with estimated nutrition values
        """
        ingredient_lower = ingredient.lower()
        
        # Category-based estimates per 100g
        estimates = {
            'default': {'calories': 100, 'protein': 5, 'carbohydrates': 15, 'total_fat': 3, 'sugar': 5, 'fiber': 2, 'sodium': 50},
            'meat': {'calories': 200, 'protein': 25, 'carbohydrates': 0, 'total_fat': 12, 'sugar': 0, 'fiber': 0, 'sodium': 70},
            'vegetable': {'calories': 25, 'protein': 2, 'carbohydrates': 5, 'total_fat': 0.3, 'sugar': 2, 'fiber': 2, 'sodium': 15},
            'fruit': {'calories': 50, 'protein': 0.5, 'carbohydrates': 12, 'total_fat': 0.2, 'sugar': 10, 'fiber': 2, 'sodium': 2},
            'grain': {'calories': 350, 'protein': 10, 'carbohydrates': 75, 'total_fat': 2, 'sugar': 1, 'fiber': 5, 'sodium': 5},
            'dairy': {'calories': 100, 'protein': 8, 'carbohydrates': 5, 'total_fat': 5, 'sugar': 5, 'fiber': 0, 'sodium': 100},
            'oil': {'calories': 880, 'protein': 0, 'carbohydrates': 0, 'total_fat': 100, 'sugar': 0, 'fiber': 0, 'sodium': 0},
        }
        
        # Categorize ingredient
        category = 'default'
        meat_keywords = ['chicken', 'beef', 'pork', 'fish', 'lamb', 'turkey', 'meat', 'salmon', 'tuna', 'shrimp']
        vegetable_keywords = ['carrot', 'broccoli', 'spinach', 'tomato', 'onion', 'garlic', 'pepper', 'lettuce', 'cabbage', 'cucumber', 'celery']
        fruit_keywords = ['apple', 'banana', 'orange', 'berry', 'grape', 'mango', 'lemon', 'lime', 'strawberry', 'blueberry']
        grain_keywords = ['rice', 'wheat', 'bread', 'pasta', 'flour', 'oat', 'cereal', 'noodle', 'quinoa']
        dairy_keywords = ['milk', 'cheese', 'yogurt', 'cream', 'butter', 'curd', 'paneer']
        oil_keywords = ['oil', 'ghee', 'lard']
        
        for keyword in meat_keywords:
            if keyword in ingredient_lower:
                category = 'meat'
                break
        for keyword in vegetable_keywords:
            if keyword in ingredient_lower:
                category = 'vegetable'
                break
        for keyword in fruit_keywords:
            if keyword in ingredient_lower:
                category = 'fruit'
                break
        for keyword in grain_keywords:
            if keyword in ingredient_lower:
                category = 'grain'
                break
        for keyword in dairy_keywords:
            if keyword in ingredient_lower:
                category = 'dairy'
                break
        for keyword in oil_keywords:
            if keyword in ingredient_lower:
                category = 'oil'
                break
        
        base = estimates[category]
        nutrition = {key: 0 for key in self.NUTRIENT_IDS.keys()}
        nutrition.update(base)
        nutrition['ingredient'] = ingredient
        nutrition['found'] = False
        nutrition['estimated'] = True
        nutrition['category'] = category
        
        return nutrition
    
    def format_nutrition_summary(self, nutrition: dict) -> dict:
        """
        Format nutrition data for display in templates.
        
        Args:
            nutrition: Raw nutrition calculation result
            
        Returns:
            Formatted dictionary ready for template rendering
        """
        per_serving = nutrition.get('per_serving', {})
        daily_pct = nutrition.get('daily_percentages', {})
        
        # Extract matched and unmatched ingredients from details
        ingredient_details = nutrition.get('ingredient_details', [])
        matched_ingredients = []
        unmatched_ingredients = []
        
        for detail in ingredient_details:
            ingredient_name = detail.get('ingredient', 'Unknown')
            if detail.get('found', False):
                matched_ingredients.append({
                    'name': ingredient_name,
                    'description': detail.get('description', ingredient_name)
                })
            else:
                # Use estimated category for context
                category = detail.get('category', 'default')
                unmatched_ingredients.append({
                    'name': ingredient_name,
                    'category': category.title() if category != 'default' else 'General',
                    'estimated': detail.get('estimated', True)
                })
        
        return {
            'macros': {
                'calories': {'value': per_serving.get('calories', 0), 'unit': 'kcal', 'dv': daily_pct.get('calories', 0)},
                'protein': {'value': per_serving.get('protein', 0), 'unit': 'g', 'dv': daily_pct.get('protein', 0)},
                'total_fat': {'value': per_serving.get('total_fat', 0), 'unit': 'g', 'dv': daily_pct.get('total_fat', 0)},
                'carbohydrates': {'value': per_serving.get('carbohydrates', 0), 'unit': 'g', 'dv': daily_pct.get('carbohydrates', 0)},
                'fiber': {'value': per_serving.get('fiber', 0), 'unit': 'g', 'dv': daily_pct.get('fiber', 0)},
                'sugar': {'value': per_serving.get('sugar', 0), 'unit': 'g', 'dv': daily_pct.get('sugar', 0)},
            },
            'minerals': {
                'sodium': {'value': per_serving.get('sodium', 0), 'unit': 'mg', 'dv': daily_pct.get('sodium', 0)},
                'potassium': {'value': per_serving.get('potassium', 0), 'unit': 'mg', 'dv': daily_pct.get('potassium', 0)},
                'calcium': {'value': per_serving.get('calcium', 0), 'unit': 'mg', 'dv': daily_pct.get('calcium', 0)},
                'iron': {'value': per_serving.get('iron', 0), 'unit': 'mg', 'dv': daily_pct.get('iron', 0)},
            },
            'vitamins': {
                'vitamin_a': {'value': per_serving.get('vitamin_a', 0), 'unit': 'IU', 'dv': daily_pct.get('vitamin_a', 0)},
                'vitamin_c': {'value': per_serving.get('vitamin_c', 0), 'unit': 'mg', 'dv': daily_pct.get('vitamin_c', 0)},
                'vitamin_d': {'value': per_serving.get('vitamin_d', 0), 'unit': 'IU', 'dv': daily_pct.get('vitamin_d', 0)},
                'vitamin_b12': {'value': per_serving.get('vitamin_b12', 0), 'unit': 'mcg', 'dv': daily_pct.get('vitamin_b12', 0)},
            },
            'servings': nutrition.get('servings', 4),
            'accuracy': nutrition.get('accuracy', 'estimated'),
            'ingredients_found': nutrition.get('ingredients_found', 0),
            'ingredients_analyzed': nutrition.get('ingredients_analyzed', 0),
            'matched_ingredients': matched_ingredients,
            'unmatched_ingredients': unmatched_ingredients,
        }


# Global instance
nutrition_service = NutritionService()
