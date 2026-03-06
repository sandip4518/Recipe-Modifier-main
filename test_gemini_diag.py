try:
    from gemini_service import gemini_service
    import os
    from dotenv import load_dotenv
    load_dotenv()

    print(f"Gemini Enabled: {gemini_service.enabled}")
    key = os.getenv("GEMINI_API_KEY")
    print(f"Key in env: {key[:5]}..." if key else "Key not in env")
    
    if gemini_service.enabled:
        print("Testing extraction for 'grape juice'...")
        result = gemini_service.extract_ingredients("grape juice")
        print(f"Result: {result}")
    else:
        print("Gemini NOT enabled properly.")
except Exception as e:
    import traceback
    traceback.print_exc()
