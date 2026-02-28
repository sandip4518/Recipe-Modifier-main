import json
import pickle
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from difflib import SequenceMatcher
import os
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MLService:
    def __init__(self):
        """Initialize ML model with recipe data"""
        try:
            # Set paths relative to this file
            base_dir = Path(__file__).parent
            json_path = base_dir / "MLModel" / "recipes.json"
            pickle_path = base_dir / "MLModel" / "model.pkl"
            
            # Try loading from pickle first for performance
            if pickle_path.exists():
                logger.info(f"📂 Loading pre-computed model from {pickle_path}...")
                with open(pickle_path, "rb") as f:
                    model_data = pickle.load(f)
                
                self.recipe_data = model_data['recipe_data']
                self.texts = model_data['texts']
                self.recipe_keys = model_data['recipe_keys']
                self.vectorizer = model_data['vectorizer']
                self.vectors = model_data['vectors']
                logger.info("✨ ML Service initialized from pickle successfully")
                return

            # Fallback to JSON if pickle not found
            logger.info(f"📂 Loading recipe data from {json_path} (pickle not found)...")
            if not json_path.exists():
                logger.error(f"Recipe data not found at {json_path}")
                self.recipe_data = {}
                self.texts = []
                self.recipe_keys = []
                self.vectorizer = None
                self.vectors = None
                return

            with open(json_path, "r") as f:
                self.recipe_data = json.load(f)
            
            # Prepare data for TF-IDF
            self.texts = []
            self.recipe_keys = []
            
            for recipe_key, recipe_info in self.recipe_data.items():
                for alias in recipe_info.get("aliases", []):
                    self.texts.append(alias.lower())
                    self.recipe_keys.append(recipe_key)
            
            if self.texts:
                # TF-IDF Vectorizer
                self.vectorizer = TfidfVectorizer(
                    analyzer="char_wb",
                    ngram_range=(2, 5),
                    min_df=1,
                    max_df=0.95,
                    sublinear_tf=True
                )
                self.vectors = self.vectorizer.fit_transform(self.texts)
                logger.info(f"✨ ML Service initialized from JSON with {len(self.recipe_data)} recipes")
            else:
                self.vectorizer = None
                self.vectors = None
                logger.warning("ML Service initialized with empty recipe records")
                
        except Exception as e:
            logger.error(f"Failed to initialize ML Service: {e}")
            self.recipe_data = {}
            self.texts = []
            self.recipe_keys = []
            self.vectorizer = None
            self.vectors = None

    def _levenshtein_distance(self, s1, s2):
        if len(s1) < len(s2):
            return self._levenshtein_distance(s2, s1)
        if len(s2) == 0:
            return len(s1)
        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        return previous_row[-1]

    def _normalized_levenshtein_similarity(self, s1, s2):
        distance = self._levenshtein_distance(s1.lower(), s2.lower())
        max_len = max(len(s1), len(s2))
        return 1.0 - (distance / max_len) if max_len > 0 else 1.0

    def _jaro_winkler_similarity(self, s1, s2):
        # Implementation from test2_optimized.py
        s1, s2 = s1.lower(), s2.lower()
        if s1 == s2: return 1.0
        len1, len2 = len(s1), len(s2)
        max_dist = max(len1, len2) // 2 - 1
        if max_dist < 1: max_dist = 1
        match1, match2 = [False] * len1, [False] * len2
        matches = 0
        for i in range(len1):
            start = max(0, i - max_dist)
            end = min(i + max_dist + 1, len2)
            for j in range(start, end):
                if match2[j] or s1[i] != s2[j]: continue
                match1[i] = match2[j] = True
                matches += 1
                break
        if matches == 0: return 0.0
        k, transpositions = 0, 0
        for i in range(len1):
            if not match1[i]: continue
            while not match2[k]: k += 1
            if s1[i] != s2[k]: transpositions += 1
            k += 1
        jaro = (matches / len1 + matches / len2 + (matches - transpositions / 2) / matches) / 3
        prefix = 0
        for i in range(min(len1, len2)):
            if s1[i] == s2[i]: prefix += 1
            else: break
        prefix = min(4, prefix)
        return jaro + (prefix * 0.1 * (1 - jaro))

    def _ngram_similarity(self, s1, s2, n=2):
        def get_ngrams(s, n):
            s = s.lower()
            return set([s[i:i+n] for i in range(len(s) - n + 1)])
        ngrams1, ngrams2 = get_ngrams(s1, n), get_ngrams(s2, n)
        if not ngrams1 and not ngrams2: return 1.0
        if not ngrams1 or not ngrams2: return 0.0
        intersection = len(ngrams1 & ngrams2)
        union = len(ngrams1 | ngrams2)
        return intersection / union if union > 0 else 0.0

    def _subsequence_similarity(self, s1, s2):
        return SequenceMatcher(None, s1.lower(), s2.lower()).ratio()

    def _weighted_ensemble_score(self, query, target):
        weights = {'levenshtein': 0.25, 'jaro_winkler': 0.30, 'ngram': 0.25, 'subsequence': 0.20}
        scores = {
            'levenshtein': self._normalized_levenshtein_similarity(query, target),
            'jaro_winkler': self._jaro_winkler_similarity(query, target),
            'ngram': self._ngram_similarity(query, target),
            'subsequence': self._subsequence_similarity(query, target)
        }
        ensemble_score = sum(scores[key] * weights[key] for key in weights)
        return ensemble_score

    def predict_recipe(self, user_input, threshold=0.25):
        """Find the best matching recipe key for the given input"""
        if self.vectorizer is None or self.vectors is None:
            return None
        
        user_input_lower = user_input.lower()
        user_vec = self.vectorizer.transform([user_input_lower])
        tfidf_scores = cosine_similarity(user_vec, self.vectors)[0]
        
        results = {}
        for idx, (text, recipe_key) in enumerate(zip(self.texts, self.recipe_keys)):
            tfidf_score = tfidf_scores[idx]
            ensemble_score = self._weighted_ensemble_score(user_input_lower, text)
            final_score = (0.4 * tfidf_score) + (0.6 * ensemble_score)
            
            if recipe_key not in results or final_score > results[recipe_key]:
                results[recipe_key] = final_score
        
        if not results:
            return None
            
        # Get the best match
        best_recipe_key = max(results.items(), key=lambda x: x[1])
        if best_recipe_key[1] >= threshold:
            return best_recipe_key[0]
        return None

    def get_recipe_details(self, recipe_key, condition):
        """Get recipe details (ingredients and instructions) for a condition"""
        if recipe_key not in self.recipe_data:
            return None
            
        variants = self.recipe_data[recipe_key]["variants"]
        variant_data = variants.get(condition) or variants.get("default")
        
        if not variant_data:
            return None
            
        # Format ingredients and instructions into a markdown string similar to Gemini's output
        ingredients_list = []
        for ing in variant_data.get("ingredients", []):
            ingredients_list.append(f"- {ing['name']} ({ing['qty']})")
        
        ingredients_md = "\n".join(ingredients_list)
        instructions_md = "\n".join(variant_data.get("instructions", []))
        
        recipe_md = f"""**Health Benefits**
This modified recipe for {recipe_key.replace('_', ' ').title()} is optimized for {condition.replace('_', ' ').title()}.

**Ingredients**
{ingredients_md}

**Instructions**
{instructions_md}

**Cooking Tips**
- Follow the instructions carefully for best results.
- Adjust seasoning according to your preference and dietary restrictions.

**Serving Suggestions**
Serve warm and enjoy your healthy meal!"""
        
        return recipe_md

    def generate_recipe_instructions(self, original_ingredients, modified_ingredients, condition, harmful_ingredients=None, recipe_name=None):
        """Main method to provide recipe content, replacing Gemini's direct instruction generation"""
        
        # 1. Try to find a match by recipe name if provided
        recipe_key = None
        if recipe_name:
            recipe_key = self.predict_recipe(recipe_name)
        
        # 2. If no recipe name match, try matching by looking at ingredients (heuristic)
        if not recipe_key and original_ingredients:
            # We could try to match by ingredients, but for now let's just use the name
            # or a default fallback if we can't find anything.
            pass
            
        if recipe_key:
            return self.get_recipe_details(recipe_key, condition)
            
        # 3. Fallback: Generic instructions if no model match
        return self._fallback_recipe_generation(modified_ingredients, condition)

    def _fallback_recipe_generation(self, ingredients, condition):
        ingredients_str = "\n".join([f"- {i}" for i in ingredients])
        return f"""**Health Benefits**
This recipe is adapted to be safer for {condition.replace('_', ' ').title()}.

**Ingredients**
{ingredients_str}

**Instructions**
1. Prepare all ingredients as listed.
2. Combine the main ingredients in a cooking vessel.
3. Cook thoroughly until done, following standard safety temperatures.
4. Season lightly according to health requirements.

**Cooking Tips**
- Using fresh ingredients yields the best nutritional value.
- Avoid overcooking to preserve vitamins and minerals.

**Serving Suggestions**
Portion according to your dietary plan. Enjoy!"""

    def generate_health_tips(self, condition, ingredients):
        """Generate common health tips for a condition"""
        # Static tips since we no longer have Gemini
        tips = {
            "diabetes": [
                "Focus on low-glycemic index foods to manage blood sugar.",
                "Control portion sizes to help regulate glucose levels.",
                "Include fiber-rich ingredients like whole grains and vegetables.",
                "Monitor your carbohydrate intake consistently."
            ],
            "hypertension": [
                "Reduce salt intake by using herbs and spices for flavor instead.",
                "Increase potassium-rich foods like bananas and spinach.",
                "Avoid processed foods which often contain hidden sodium.",
                "Maintain a healthy weight through balanced eating."
            ],
            "celiac_disease": [
                "Always check labels for cross-contamination with gluten.",
                "Use certified gluten-free grains like quinoa or rice.",
                "Be cautious of hidden gluten in sauces and seasonings.",
                "Focus on naturally gluten-free whole foods."
            ]
        }
        
        cond_tips = tips.get(condition, ["Consult with a healthcare provider for personalized advice."])
        return "\n".join([f"- {tip}" for tip in cond_tips])

    def extract_ingredients(self, text_or_name):
        """Extract ingredients from a recipe name if it exists in our data"""
        recipe_key = self.predict_recipe(text_or_name)
        if recipe_key and recipe_key in self.recipe_data:
            default_variant = self.recipe_data[recipe_key]["variants"].get("default")
            if default_variant:
                return [ing["name"].lower() for ing in default_variant["ingredients"]]
        
        # Fallback if no match
        return [item.strip().lower() for item in text_or_name.split(',')]

# Global instance
ml_service = MLService()
