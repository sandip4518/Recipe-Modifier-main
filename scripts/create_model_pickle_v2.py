import json
import pickle
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from pathlib import Path
import sys

def create_pickle():
    log_file = "pickle_log.txt"
    try:
        with open(log_file, "w", encoding='utf-8') as log:
            log.write("Starting model pickling process...\n")
            
            # Path setup
            base_dir = Path(__file__).parent.parent
            json_path = base_dir / "MLModel" / "recipes.json"
            pickle_path = base_dir / "MLModel" / "model.pkl"
            
            log.write(f"JSON path: {json_path}\n")
            log.write(f"Pickle path: {pickle_path}\n")
            
            # 1. Load data
            if not json_path.exists():
                log.write(f"Error: JSON not found at {json_path}\n")
                return
                
            log.write(f"Loading recipe data...\n")
            with open(json_path, "r", encoding='utf-8') as f:
                recipe_data = json.load(f)
            
            # 2. Extract texts and keys
            log.write("Processing recipe aliases...\n")
            texts = []
            recipe_keys = []
            
            for recipe_key, recipe_info in recipe_data.items():
                for alias in recipe_info.get("aliases", []):
                    texts.append(alias.lower())
                    recipe_keys.append(recipe_key)
            
            log.write(f"Count: {len(texts)} aliases\n")
            
            # 3. Fit TF-IDF
            log.write(f"Fitting TF-IDF Vectorizer...\n")
            vectorizer = TfidfVectorizer(
                analyzer="char_wb",
                ngram_range=(2, 5),
                min_df=1,
                max_df=0.95,
                sublinear_tf=True
            )
            vectors = vectorizer.fit_transform(texts)
            
            log.write(f"Saving model to pickle...\n")
            model_data = {
                'recipe_data': recipe_data,
                'texts': texts,
                'recipe_keys': recipe_keys,
                'vectorizer': vectorizer,
                'vectors': vectors
            }
            
            with open(pickle_path, "wb") as f:
                pickle.dump(model_data, f)
            
            log.write("Model pickling complete!\n")
            print("Done")
    except Exception as e:
        with open("pickle_error.txt", "w", encoding='utf-8') as err:
            err.write(f"Error: {str(e)}\n")
            import traceback
            err.write(traceback.format_exc())
        print(f"Error: {e}")

if __name__ == "__main__":
    create_pickle()
