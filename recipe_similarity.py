"""
Recipe Similarity Embedding Validation Service

Uses Sentence Transformers to check if a recipe name is realistic 
compared to a known database of recipe names.
"""

import os
import logging
import numpy as np
from pathlib import Path

# Try to import sentence_transformers safely
try:
    from sentence_transformers import SentenceTransformer, util
    HAS_ST = True
except ImportError:
    HAS_ST = False

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RecipeSimilarityValidator:
    """Validator using Sentence Embeddings for recipe name realism checking"""
    
    def __init__(self, model_name='all-MiniLM-L6-v2'):
        self.model_name = model_name
        self.model = None
        self.recipe_embeddings = None
        self.recipes = []
        self._initialized = False
        
    def _initialize(self):
        """Lazy load model and embeddings"""
        if self._initialized or not HAS_ST:
            return
            
        try:
            logger.info(f"🚀 Initializing RecipeSimilarityValidator with model: {self.model_name}...")
            self.model = SentenceTransformer(self.model_name)
            
            # Paths
            base_dir = Path(__file__).parent
            csv_path = base_dir / "models" / "recipes.csv"
            cache_path = base_dir / "models" / "recipe_embeddings.npy"
            
            # Load recipes from CSV
            if csv_path.exists():
                with open(csv_path, 'r', encoding='utf-8') as f:
                    self.recipes = [line.strip() for line in f.readlines() if line.strip()]
                # Skip header if it exists (assuming first line is "recipe" or similar)
                # But looking at recipes.csv, it has no header.
                # If it had one, we'd skip it. 
                # Let's assume no header as we saw in the view_file output.
            else:
                logger.error(f"Recipe CSV not found: {csv_path}")
                self.recipes = ["Chicken Biryani", "Paneer Butter Masala", "Veg Fried Rice", "Tomato Soup", "Chocolate Cake"]
                
            # Load or compute embeddings
            if cache_path.exists():
                logger.info("📂 Loading pre-computed embeddings from cache...")
                self.recipe_embeddings = np.load(cache_path)
            else:
                logger.info(f"🧠 Computing embeddings for {len(self.recipes)} recipes (this may take a while)...")
                self.recipe_embeddings = self.model.encode(self.recipes, show_progress_bar=False)
                # Cache them
                np.save(cache_path, self.recipe_embeddings)
                logger.info(f"✅ Embeddings computed and cached at {cache_path}")
                
            self._initialized = True
            
        except Exception as e:
            logger.error(f"Failed to initialize RecipeSimilarityValidator: {e}")
            self._initialized = False

    def validate_recipe_name(self, user_input, threshold=0.45):
        """
        Check if user input is similar to a known recipe.
        
        Args:
            user_input: Name of the recipe to validate
            threshold: Similarity score (0.0 - 1.0) above which it's valid
            
        Returns:
            bool: True if it's a realistic recipe name, False otherwise
        """
        if not user_input or len(user_input.strip()) < 3:
            return False
            
        if not HAS_ST:
            logger.warning("Sentence Transformers not installed. Falling back to basic validation.")
            return True # Fallback: assume True for safety if model unavailable
            
        self._initialize()
        if not self._initialized:
            return True
            
        try:
            # Compute embedding for input
            input_embedding = self.model.encode(user_input, show_progress_bar=False)
            
            # Compute cosine similarity
            # self.recipe_embeddings is (N, D), input_embedding is (D,)
            similarities = util.cos_sim(input_embedding, self.recipe_embeddings)
            max_score = similarities.max().item()
            
            logger.info(f"Similarity check for '{user_input}': max_score={max_score:.4f}")
            
            return max_score >= threshold
            
        except Exception as e:
            logger.error(f"Error during similarity validation: {e}")
            return True # Fallback to True on error to not block users

# Global singleton
recipe_validator = RecipeSimilarityValidator()

# Test code if run directly
if __name__ == "__main__":
    if HAS_ST:
        print(f"Testing validation for 'Chicken Biryani': {recipe_validator.validate_recipe_name('Chicken Biryani')}")
        print(f"Testing validation for 'dvhdhvgdv': {recipe_validator.validate_recipe_name('dvhdhvgdv')}")
    else:
        print("Sentence Transformers not installed.")
