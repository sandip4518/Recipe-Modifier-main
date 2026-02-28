import json
from pathlib import Path

def list_top_recipes():
    json_path = Path("MLModel/recipes.json")
    if not json_path.exists():
        print("Error: recipes.json not found")
        return
        
    with open(json_path, "r", encoding='utf-8') as f:
        recipe_data = json.load(f)
    
    print("--- Top 20 Recipes ---")
    keys = list(recipe_data.keys())[:20]
    for key in keys:
        aliases = recipe_data[key].get("aliases", [])
        name = aliases[0] if aliases else key
        print(f"- {name} (Key: {key})")

if __name__ == "__main__":
    list_top_recipes()
