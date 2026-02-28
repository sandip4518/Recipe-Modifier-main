# Vercel Deployment Guide

## Changes Made for Vercel Compatibility

### 1. Lazy MongoDB Connection
- MongoDB connection is now initialized lazily (on first use) instead of at module import time
- This prevents connection failures during cold starts on Vercel
- Added proper error handling with fallback dummy collections

### 2. Serverless Function Entry Point
- Updated `api/index.py` to properly handle Vercel's serverless function format
- Fixed path resolution for templates and static files
- Set working directory to project root

### 3. File System Operations
- PDF reports now use `/tmp/reports` on Vercel (read-only filesystem)
- Automatically detects Vercel environment using `VERCEL` or `VERCEL_ENV` environment variables

### 4. Error Handling
- Added comprehensive error handling throughout the application
- Database operations won't crash the app if MongoDB is unavailable
- Graceful fallbacks for all database operations

### 5. Gemini API Integration Fix
- Fixed incorrect import: Changed `from google import genai` to `import google.generativeai as genai`
- Updated API usage to match `google-generativeai==0.3.2`:
  - Use `genai.configure(api_key=...)` instead of `genai.Client(api_key=...)`
  - Use `genai.GenerativeModel('gemini-pro')` to create models
  - Use `model.generate_content(prompt)` instead of `client.generate_content(prompt)`
- Added proper error handling for missing API keys

## Required Environment Variables in Vercel

You **must** set these environment variables in your Vercel project settings:

1. **MONGODB_URI** - Your MongoDB connection string
   - Example: `mongodb+srv://username:password@cluster.mongodb.net/?retryWrites=true&w=majority`
   - Get this from MongoDB Atlas or your MongoDB provider

2. **SECRET_KEY** - Flask secret key for sessions
   - Generate a secure random string
   - Example: `python -c "import secrets; print(secrets.token_hex(32))"`

3. **GEMINI_API_KEY** - Your Google Gemini API key
   - Get this from Google AI Studio: https://makersuite.google.com/app/apikey

## How to Set Environment Variables in Vercel

1. Go to your Vercel project dashboard
2. Navigate to **Settings** → **Environment Variables**
3. Add each variable:
   - **Name**: `MONGODB_URI`
   - **Value**: Your MongoDB connection string
   - **Environment**: Production, Preview, Development (select all)
4. Repeat for `SECRET_KEY` and `GEMINI_API_KEY`
5. **Redeploy** your application after adding environment variables

## Deployment Steps

1. **Push your code to GitHub/GitLab/Bitbucket**
   ```bash
   git add .
   git commit -m "Fix Vercel deployment"
   git push
   ```

2. **Connect to Vercel** (if not already connected)
   - Go to https://vercel.com
   - Import your repository
   - Vercel will auto-detect the Python project

3. **Set Environment Variables** (see above)

4. **Deploy**
   - Vercel will automatically deploy on push
   - Or manually trigger a deployment from the dashboard

## Troubleshooting

### Error: FUNCTION_INVOCATION_FAILED

**Common causes:**
1. **Missing Environment Variables** - Check that all required env vars are set
2. **MongoDB Connection Issues** - Verify your MongoDB URI is correct and accessible
3. **Import Errors** - Check Vercel build logs for Python import errors
4. **Gemini API Import Error** - Fixed: Changed `from google import genai` to `import google.generativeai as genai` and updated API usage to match `google-generativeai==0.3.2`

### Check Vercel Logs

1. Go to your Vercel project dashboard
2. Click on **Deployments**
3. Click on the latest deployment
4. Click on **Functions** tab
5. Check the logs for error messages

### Common Issues

**Issue**: MongoDB connection timeout
- **Solution**: Ensure your MongoDB Atlas IP whitelist includes `0.0.0.0/0` (all IPs) or Vercel's IP ranges

**Issue**: Template not found
- **Solution**: Ensure `templates/` and `static/` folders are in the project root and committed to git

**Issue**: Module not found
- **Solution**: Ensure all dependencies are in `requirements.txt` and properly installed

## Testing Locally

You can test the Vercel setup locally using Vercel CLI:

```bash
# Install Vercel CLI
npm i -g vercel

# Run locally
vercel dev
```

This will simulate the Vercel environment locally.

## Notes

- The application uses lazy initialization, so the first request might be slower
- Database initialization happens on first connection
- Static files and templates are served by Flask (no need for separate static hosting)
- PDF reports are stored in `/tmp/reports` on Vercel (temporary, cleared between invocations)

