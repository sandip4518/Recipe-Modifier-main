import json
import pickle
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from pathlib import Path

def create_pickle():
    print("🚀 Starting model pickling process...")
    
    # Path setup
    base_dir = Path(__file__).parent
    json_path = base_dir / "MLModel" / "recipes.json"
    pickle_path = base_dir / "MLModel" / "model.pkl"
    
    # 1. Load data
    print(f"📂 Loading recipe data from {json_path}...")
    with open(json_path, "r") as f:
        recipe_data = json.load(f)
    
    # 2. Extract texts and keys
    print("📝 Processing recipe aliases...")
    texts = []
    recipe_keys = []
    
    for recipe_key, recipe_info in recipe_data.items():
        for alias in recipe_info.get("aliases", []):
            texts.append(alias.lower())
            recipe_keys.append(recipe_key)
    
    # 3. Fit TF-IDF
    print(f"🧪 Fitting TF-IDF Vectorizer on {len(texts)} aliases...")
    vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(2, 5),
        min_df=1,
        max_df=0.95,
        sublinear_tf=True
    )
    vectors = vectorizer.fit_transform(texts)
    
    # 4. Save to Pickle
    print(f"📦 Saving model to {pickle_path}...")
    model_data = {
        'recipe_data': recipe_data,
        'texts': texts,
        'recipe_keys': recipe_keys,
        'vectorizer': vectorizer,
        'vectors': vectors
    }
    
    with open(pickle_path, "wb") as f:
        pickle.dump(model_data, f)
    
    print("✨ Model pickling complete!")

if __name__ == "__main__":
    create_pickle()
