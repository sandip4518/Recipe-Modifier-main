"""
Test all Flask routes defined in app.py
Uses Flask's built-in test client (no server needed).
"""
import sys
import os
import json

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(__file__))

from app import app

# -- Helpers -------------------------------------------------------------------
PASS = "[PASS]"
FAIL = "[FAIL]"
SKIP = "[SKIP]"

results = {"pass": 0, "fail": 0, "skip": 0}

def report(method, path, expected_codes, actual_code, note=""):
    """Pretty-print one test result."""
    ok = actual_code in expected_codes
    tag = PASS if ok else FAIL
    if ok:
        results["pass"] += 1
    else:
        results["fail"] += 1
    extra = f"  ({note})" if note else ""
    print(f"  {tag}  {method:6s} {path:45s}  ->  {actual_code}  (expected {expected_codes}){extra}")

def skip(method, path, reason):
    results["skip"] += 1
    print(f"  {SKIP}  {method:6s} {path:45s}  ->  skipped: {reason}")


# -- Test client ---------------------------------------------------------------
app.config["TESTING"] = True
app.config["WTF_CSRF_ENABLED"] = False          # disable CSRF for testing
app.config["LOGIN_DISABLED"] = False             # keep login_required active
client = app.test_client()


# ==============================================================================
#  1. PUBLIC GET routes (no login needed)
# ==============================================================================
print("\n" + "="*80)
print("  PUBLIC GET ROUTES (no login required)")
print("="*80)

public_get_routes = [
    ("GET", "/",                    [200]),
    ("GET", "/app",                 [200]),
    ("GET", "/register",            [200]),
    ("GET", "/login",               [200]),
    ("GET", "/community",           [200]),
    ("GET", "/api/ingredients",     [200]),
    ("GET", "/api/conditions",      [200]),
    ("GET", "/api/stats",           [200]),
    ("GET", "/api/recipes/ingredients?name=pasta", [200]),
]

for method, path, codes in public_get_routes:
    resp = client.get(path)
    report(method, path, codes, resp.status_code)


# ==============================================================================
#  2. PUBLIC POST routes - API endpoints (no login needed)
# ==============================================================================
print("\n" + "="*80)
print("  PUBLIC POST / API ROUTES (no login required)")
print("="*80)

# /api/profile-warnings (returns empty if not logged in)
resp = client.post("/api/profile-warnings",
                   data=json.dumps({"ingredients": ["sugar", "butter"]}),
                   content_type="application/json")
report("POST", "/api/profile-warnings", [200], resp.status_code, "unauthenticated -> empty warnings")

# /check_ingredients (POST - needs form data; redirects on missing data)
resp = client.post("/check_ingredients", data={}, follow_redirects=False)
report("POST", "/check_ingredients (empty)", [302, 200], resp.status_code, "redirect on missing ingredients")

resp = client.post("/check_ingredients",
                   data={"ingredients": "sugar, butter, flour", "condition": "diabetes"},
                   follow_redirects=False)
report("POST", "/check_ingredients (valid)", [200], resp.status_code, "with valid ingredients+condition")

# /api/spell-check
resp = client.post("/api/spell-check",
                   data=json.dumps({"recipe_name": "spagetti"}),
                   content_type="application/json")
report("POST", "/api/spell-check", [200], resp.status_code)

# /api/nutrition
resp = client.post("/api/nutrition",
                   data=json.dumps({"ingredients": ["rice", "chicken"], "condition": "diabetes"}),
                   content_type="application/json")
report("POST", "/api/nutrition", [200], resp.status_code)

# /api/ai/extract-ingredients
resp = client.post("/api/ai/extract-ingredients",
                   data=json.dumps({"text": "pasta"}),
                   content_type="application/json")
report("POST", "/api/ai/extract-ingredients", [200], resp.status_code)


# ==============================================================================
#  3. PROTECTED GET routes - should redirect (302) to login when not authed
# ==============================================================================
print("\n" + "="*80)
print("  PROTECTED GET ROUTES (should 302 -> /login when unauthenticated)")
print("="*80)

protected_get_routes = [
    "/profile",
    "/cookbook",
    "/planner",
    "/grocery",
    "/pantry",
    "/complete-profile",
    "/update-health-metrics",
    "/generate_report/test123",
    "/view_report/test123",
    "/serve_report_pdf/test123",
    "/cook/000000000000000000000000",      # valid-format ObjectId
]

for path in protected_get_routes:
    resp = client.get(path, follow_redirects=False)
    # Flask-Login redirects to /login?next=... with 302
    report("GET", path, [302, 401], resp.status_code, "should redirect to login")


# ==============================================================================
#  4. PROTECTED POST routes - should 302/401 when not authed
# ==============================================================================
print("\n" + "="*80)
print("  PROTECTED POST ROUTES (should 302/401 when unauthenticated)")
print("="*80)

protected_post_routes = [
    ("/update_profile",                       {}),
    ("/change_password",                      {}),
    ("/logout",                               None),  # GET actually
    ("/api/favorite/000000000000000000000000", {}),
    ("/api/categorize/000000000000000000000000", {"category": "Dinner"}),
    ("/api/cookbook/export",                   {}),
    ("/api/community/share/000000000000000000000000", {}),
    ("/api/community/like/000000000000000000000000",  {}),
    ("/api/mealplan/add",                     {"date": "2026-03-04", "meal_type": "lunch", "entry_id": "000000000000000000000000"}),
    ("/api/mealplan/remove/000000000000000000000000", {}),
    ("/api/grocery/generate",                 {"start_date": "2026-03-01", "end_date": "2026-03-07"}),
    ("/api/grocery/toggle/000000000000000000000000",  {"name": "rice", "checked": True}),
    ("/api/pantry/add",                       {"item": "salt"}),
    ("/api/pantry/remove",                    {"item": "salt"}),
]

for path, payload in protected_post_routes:
    if payload is None:
        resp = client.get(path, follow_redirects=False)
        report("GET", path, [302, 401], resp.status_code, "protected GET -> redirect")
    else:
        resp = client.post(path,
                           data=json.dumps(payload),
                           content_type="application/json",
                           follow_redirects=False)
        report("POST", path, [302, 401], resp.status_code, "protected POST -> redirect")


# ==============================================================================
#  5. AUTH FLOW: register -> login -> test protected routes -> logout
# ==============================================================================
print("\n" + "="*80)
print("  AUTHENTICATED FLOW (register -> test protected -> logout)")
print("="*80)

import random, string
rand = ''.join(random.choices(string.ascii_lowercase, k=6))
test_user = f"testbot_{rand}"
test_email = f"{test_user}@test.com"
test_pass = "TestPass123!"

# Register
resp = client.post("/register", data={
    "username": test_user,
    "email": test_email,
    "password": test_pass,
    "confirm_password": test_pass,
    "medical_condition": "diabetes",
}, follow_redirects=False)
# Successful registration redirects to /complete-profile
report("POST", "/register (new user)", [302, 200], resp.status_code, "register -> redirect")

# Complete profile  
resp = client.post("/complete-profile", data={
    "age": 25,
    "gender": "male",
    "weight": 70,
    "height": 170,
    "diet_type": "non-vegetarian",
    "allergies": "",
    "calorie_target": 2000,
    "goal": "maintain_fitness",
}, follow_redirects=False)
report("POST", "/complete-profile", [302, 200], resp.status_code, "complete profile -> redirect")

# Now test protected GET routes while logged in
auth_get_tests = [
    ("/profile",          [200]),
    ("/cookbook",          [200]),
    ("/planner",          [200]),
    ("/grocery",          [200]),
    ("/pantry",           [200]),
]

for path, codes in auth_get_tests:
    resp = client.get(path)
    report("GET", path + " (authed)", codes, resp.status_code)

# Test /community while authed
resp = client.get("/community")
report("GET", "/community (authed)", [200], resp.status_code)

# Test /api/profile-warnings authed
resp = client.post("/api/profile-warnings",
                   data=json.dumps({"ingredients": ["sugar", "butter"]}),
                   content_type="application/json")
report("POST", "/api/profile-warnings (authed)", [200], resp.status_code)

# Test /check_ingredients authed
resp = client.post("/check_ingredients",
                   data={"ingredients": "rice, chicken, salt",
                         "condition": "diabetes",
                         "recipe_name": "Test Rice"},
                   follow_redirects=False)
report("POST", "/check_ingredients (authed)", [200], resp.status_code)

# Test /update_profile authed
resp = client.post("/update_profile", data={
    "email": test_email,
    "medical_condition": "hypertension",
}, follow_redirects=False)
report("POST", "/update_profile (authed)", [302, 200], resp.status_code, "redirect to profile")

# Test /change_password authed
resp = client.post("/change_password", data={
    "current_password": test_pass,
    "new_password": "NewTestPass123!",
    "confirm_new_password": "NewTestPass123!",
}, follow_redirects=False)
report("POST", "/change_password (authed)", [302, 200], resp.status_code, "redirect to profile")

# Test update-health-metrics GET
resp = client.get("/update-health-metrics")
report("GET", "/update-health-metrics (authed)", [200], resp.status_code)

# Test pantry API endpoints
resp = client.post("/api/pantry/add",
                   data=json.dumps({"item": "salt"}),
                   content_type="application/json")
report("POST", "/api/pantry/add (authed)", [200], resp.status_code)

resp = client.post("/api/pantry/remove",
                   data=json.dumps({"item": "salt"}),
                   content_type="application/json")
report("POST", "/api/pantry/remove (authed)", [200], resp.status_code)

# Logout
resp = client.get("/logout", follow_redirects=False)
report("GET", "/logout (authed)", [302], resp.status_code, "redirect after logout")

# Verify redirect after logout
resp = client.get("/profile", follow_redirects=False)
report("GET", "/profile (after logout)", [302], resp.status_code, "should redirect to login")


# ==============================================================================
#  SUMMARY
# ==============================================================================
print("\n" + "="*80)
total = results["pass"] + results["fail"] + results["skip"]
print(f"  TOTAL: {total}   |   {PASS}: {results['pass']}   |   {FAIL}: {results['fail']}   |   {SKIP}: {results['skip']}")
print("="*80 + "\n")

if results["fail"] > 0:
    sys.exit(1)
