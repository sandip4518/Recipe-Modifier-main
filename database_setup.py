#!/usr/bin/env python3
"""
Database Setup Script for Health-Aware Recipe Modifier
This script initializes the MongoDB database with sample data.
"""

from pymongo import MongoClient
from datetime import datetime

def setup_database():
    """Initialize the database with sample data"""
    
    # Connect to MongoDB
    try:
        client = MongoClient('mongodb://localhost:27017/')
        db = client['health_recipe_modifier']
        
        print("✅ Connected to MongoDB successfully!")
        
        # Initialize collections
        ingredient_rules = db['ingredient_rules']
        food_entries = db['food_entries']
        patients = db['patients']
        
        # Clear existing data (optional - comment out if you want to keep existing data)
        ingredient_rules.delete_many({})
        patients.delete_many({})
        food_entries.delete_many({})
        
        print("🗑️  Cleared existing data")
        
        # Sample ingredient rules
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
        
        # Insert ingredient rules
        result = ingredient_rules.insert_many(sample_rules)
        print(f"✅ Added {len(result.inserted_ids)} ingredient rules")
        
        # Sample patient
        sample_patient = {
            "patient_id": "1",
            "name": "John Doe",
            "condition": "diabetes",
            "email": "john.doe@example.com",
            "created_at": datetime.now()
        }
        
        patients.insert_one(sample_patient)
        print("✅ Added sample patient")
        
        # Sample food entry
        sample_entry = {
            "patient_id": "1",
            "condition": "diabetes",
            "input_ingredients": ["sugar", "flour", "butter", "banana"],
            "harmful": ["sugar", "flour"],
            "safe": ["stevia", "almond flour", "olive oil", "banana"],
            "recipe": "Mix almond flour, banana, stevia, olive oil. Cook in a non-stick pan until golden brown.",
            "timestamp": datetime.now()
        }
        
        food_entries.insert_one(sample_entry)
        print("✅ Added sample food entry")
        
        # Print database statistics
        print("\n📊 Database Statistics:")
        print(f"   - Ingredient Rules: {ingredient_rules.count_documents({})}")
        print(f"   - Patients: {patients.count_documents({})}")
        print(f"   - Food Entries: {food_entries.count_documents({})}")
        
        print("\n🎉 Database setup completed successfully!")
        print("You can now run the Flask application with: python app.py")
        
    except Exception as e:
        print(f"❌ Error setting up database: {e}")
        print("Make sure MongoDB is running on localhost:27017")

if __name__ == "__main__":
    setup_database()
