#!/usr/bin/env python3
"""
Startup Script for Health-Aware Recipe Modifier
This script checks dependencies, sets up the database, and starts the application.
"""

import os
import sys
import subprocess
import importlib.util

def check_python_version():
    """Check if Python version is compatible"""
    if sys.version_info < (3, 7):
        print("❌ Python 3.7 or higher is required")
        print(f"Current version: {sys.version}")
        return False
    print(f"✅ Python version: {sys.version.split()[0]}")
    return True

def check_dependencies():
    """Check if required packages are installed"""
    required_packages = [
        'flask',
        'pymongo', 
        'reportlab',
        'python-dateutil'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        spec = importlib.util.find_spec(package)
        if spec is None:
            missing_packages.append(package)
        else:
            print(f"✅ {package} is installed")
    
    if missing_packages:
        print(f"\n❌ Missing packages: {', '.join(missing_packages)}")
        print("Installing missing packages...")
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install'] + missing_packages)
            print("✅ All packages installed successfully")
        except subprocess.CalledProcessError:
            print("❌ Failed to install packages")
            return False
    
    return True

def check_mongodb():
    """Check if MongoDB is accessible"""
    try:
        from pymongo import MongoClient
        client = MongoClient('mongodb://localhost:27017/', serverSelectionTimeoutMS=5000)
        client.server_info()
        print("✅ MongoDB is running and accessible")
        return True
    except Exception as e:
        print("❌ MongoDB connection failed")
        print("Please make sure MongoDB is running on localhost:27017")
        print("You can:")
        print("  1. Install MongoDB locally")
        print("  2. Use MongoDB Atlas (cloud)")
        print("  3. Update the connection string in app.py")
        return False

def setup_database():
    """Set up the database with sample data"""
    try:
        from database_setup import setup_database
        print("\n🗄️  Setting up database...")
        setup_database()
        return True
    except Exception as e:
        print(f"❌ Database setup failed: {e}")
        return False

def create_directories():
    """Create necessary directories"""
    directories = ['reports', 'static', 'templates']
    
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"✅ Created directory: {directory}")
        else:
            print(f"✅ Directory exists: {directory}")

def start_application():
    """Start the Flask application"""
    print("\n🚀 Starting Health-Aware Recipe Modifier...")
    print("The application will be available at: http://localhost:5000")
    print("Press Ctrl+C to stop the application")
    print("-" * 50)
    
    try:
        from app import app
        app.run(debug=True, host='0.0.0.0', port=5000)
    except KeyboardInterrupt:
        print("\n👋 Application stopped by user")
    except Exception as e:
        print(f"❌ Failed to start application: {e}")

def main():
    """Main startup function"""
    print("🧠 Health-Aware Recipe Modifier - Startup")
    print("=" * 50)
    
    # Check Python version
    if not check_python_version():
        return
    
    # Check dependencies
    if not check_dependencies():
        return
    
    # Create directories
    create_directories()
    
    # Check MongoDB
    if not check_mongodb():
        print("\n💡 You can still run the application, but database features won't work")
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            return
    
    # Setup database
    setup_database()
    
    # Start application
    start_application()

if __name__ == "__main__":
    main()
