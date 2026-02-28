"""
Vercel Serverless Function Entry Point
This file is used by Vercel to serve the Flask application as a serverless function.
"""
import sys
import os

try:
    # Get the directory containing this file (api/)
    api_dir = os.path.dirname(os.path.abspath(__file__))
    # Get the parent directory (project root)
    project_root = os.path.dirname(api_dir)

    # Add project root to Python path
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    # Change working directory to project root for relative paths (templates, static)
    os.chdir(project_root)
    
    # Verify critical directories exist
    templates_path = os.path.join(project_root, 'templates')
    static_path = os.path.join(project_root, 'static')
    
    if not os.path.exists(templates_path):
        raise FileNotFoundError(f"Templates directory not found: {templates_path}")
    if not os.path.exists(static_path):
        raise FileNotFoundError(f"Static directory not found: {static_path}")

    # Import the Flask app
    from app import app

    # Vercel expects a module-level variable named 'app'
    # This is the WSGI application that Vercel will use to handle requests
    # The app variable is already imported above and will be used by Vercel
    
except Exception as e:
    # Log the error for debugging in Vercel logs
    import traceback
    error_msg = f"Error initializing Flask app in api/index.py: {e}"
    print(error_msg)
    print(f"Current working directory: {os.getcwd()}")
    print(f"Project root: {project_root if 'project_root' in locals() else 'N/A'}")
    print(traceback.format_exc())
    # Re-raise to see the error in Vercel
    raise