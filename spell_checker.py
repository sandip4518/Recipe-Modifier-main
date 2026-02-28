"""
Spell Checker Service for Recipe Names

Uses Python's built-in difflib for fuzzy matching - NO external dependencies!
Optimized for Vercel serverless deployment (lightweight).
"""

import os
import logging
from difflib import SequenceMatcher, get_close_matches

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SpellChecker:
    """Lightweight spell checker using difflib fuzzy matching"""
    
    def __init__(self):
        self.recipes = []
        self.recipes_lower = []
        self._loaded = False
        self._load_attempted = False
    
    def _ensure_loaded(self):
        """Lazy load recipes on first use"""
        if self._load_attempted:
            return self._loaded
        self._load_attempted = True
        self._load_recipes()
        return self._loaded
    
    def _load_recipes(self):
        """Load recipe names from CSV file"""
        try:
            base_path = os.path.dirname(os.path.abspath(__file__))
            recipes_path = os.path.join(base_path, 'models', 'recipes.csv')
            
            if not os.path.exists(recipes_path):
                logger.warning(f"Recipes file not found: {recipes_path}")
                return
            
            # Read CSV manually (no pandas needed!)
            with open(recipes_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Skip header, get recipe names
            self.recipes = [line.strip() for line in lines[1:] if line.strip()]
            self.recipes_lower = [r.lower() for r in self.recipes]
            
            logger.info(f"Loaded {len(self.recipes)} recipe names")
            self._loaded = True
            
        except Exception as e:
            logger.error(f"Error loading recipes: {e}")
            self._loaded = False
    
    def check_spelling(self, text, threshold=0.6, top_n=3):
        """
        Check if input matches a recipe; return suggestions if not.
        
        Args:
            text: User input recipe name
            threshold: Minimum similarity score (0.0 to 1.0)
            top_n: Maximum number of suggestions
            
        Returns:
            dict: {"is_correct": bool, "suggestions": list}
        """
        if not self._ensure_loaded() or not text:
            return {"is_correct": True, "suggestions": []}
        
        text_lower = text.strip().lower()
        
        # Exact match check
        if text_lower in self.recipes_lower:
            return {"is_correct": True, "suggestions": []}
        
        try:
            # Use difflib's get_close_matches for fuzzy matching
            matches = get_close_matches(
                text_lower, 
                self.recipes_lower, 
                n=top_n, 
                cutoff=threshold
            )
            
            # Map back to original case
            suggestions = []
            for match in matches:
                idx = self.recipes_lower.index(match)
                suggestions.append(self.recipes[idx])
            
            # Check if top match is very close (>90% similar)
            is_correct = len(suggestions) == 0
            if suggestions:
                ratio = SequenceMatcher(None, text_lower, matches[0]).ratio()
                is_correct = ratio > 0.9
            
            return {
                "is_correct": bool(is_correct),
                "suggestions": suggestions
            }
            
        except Exception as e:
            logger.error(f"Spell check error: {e}")
            return {"is_correct": True, "suggestions": []}
    
    def get_all_recipes(self):
        """Return all recipe names"""
        self._ensure_loaded()
        return self.recipes if self._loaded else []


# Global singleton
spell_checker = SpellChecker()
