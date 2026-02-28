import json
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from difflib import SequenceMatcher
import re
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pathlib import Path
import os

# Create images folder if it doesn't exist
IMAGES_FOLDER = Path("images")
IMAGES_FOLDER.mkdir(exist_ok=True)


# ------------------------------
# Load recipe data
# ------------------------------
with open("recipes.json", "r") as f:
    recipe_data = json.load(f)


# ------------------------------
# Mathematical Optimization Functions
# ------------------------------

def levenshtein_distance(s1, s2):
    """
    Calculate Levenshtein distance (edit distance) between two strings.
    Uses dynamic programming for optimization.
    Time Complexity: O(m*n), Space Complexity: O(min(m,n))
    """
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    
    if len(s2) == 0:
        return len(s1)
    
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            # Cost of insertions, deletions, or substitutions
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    
    return previous_row[-1]


def normalized_levenshtein_similarity(s1, s2):
    """
    Normalize Levenshtein distance to similarity score [0, 1].
    Formula: 1 - (distance / max_length)
    """
    distance = levenshtein_distance(s1.lower(), s2.lower())
    max_len = max(len(s1), len(s2))
    if max_len == 0:
        return 1.0
    return 1 - (distance / max_len)


def jaro_winkler_similarity(s1, s2):
    """
    Jaro-Winkler similarity - better for short strings and typos.
    Gives more weight to matching prefixes.
    """
    s1, s2 = s1.lower(), s2.lower()
    
    # If strings are equal
    if s1 == s2:
        return 1.0
    
    # Length of the strings
    len1, len2 = len(s1), len(s2)
    
    # Maximum distance for matching
    max_dist = max(len1, len2) // 2 - 1
    if max_dist < 1:
        max_dist = 1
    
    # Initialize match arrays
    match1 = [False] * len1
    match2 = [False] * len2
    
    matches = 0
    transpositions = 0
    
    # Find matches
    for i in range(len1):
        start = max(0, i - max_dist)
        end = min(i + max_dist + 1, len2)
        
        for j in range(start, end):
            if match2[j] or s1[i] != s2[j]:
                continue
            match1[i] = match2[j] = True
            matches += 1
            break
    
    if matches == 0:
        return 0.0
    
    # Find transpositions
    k = 0
    for i in range(len1):
        if not match1[i]:
            continue
        while not match2[k]:
            k += 1
        if s1[i] != s2[k]:
            transpositions += 1
        k += 1
    
    # Jaro similarity
    jaro = (matches / len1 + matches / len2 + 
            (matches - transpositions / 2) / matches) / 3
    
    # Jaro-Winkler modification (prefix bonus)
    prefix = 0
    for i in range(min(len1, len2)):
        if s1[i] == s2[i]:
            prefix += 1
        else:
            break
    prefix = min(4, prefix)  # Max prefix length is 4
    
    jaro_winkler = jaro + (prefix * 0.1 * (1 - jaro))
    
    return jaro_winkler


def ngram_similarity(s1, s2, n=2):
    """
    Calculate n-gram based similarity.
    Uses Jaccard coefficient for n-gram sets.
    """
    def get_ngrams(s, n):
        s = s.lower()
        return set([s[i:i+n] for i in range(len(s) - n + 1)])
    
    ngrams1 = get_ngrams(s1, n)
    ngrams2 = get_ngrams(s2, n)
    
    if not ngrams1 and not ngrams2:
        return 1.0
    if not ngrams1 or not ngrams2:
        return 0.0
    
    # Jaccard similarity
    intersection = len(ngrams1 & ngrams2)
    union = len(ngrams1 | ngrams2)
    
    return intersection / union if union > 0 else 0.0


def subsequence_similarity(s1, s2):
    """
    Longest common subsequence ratio.
    Good for handling insertions/deletions.
    """
    s1, s2 = s1.lower(), s2.lower()
    matcher = SequenceMatcher(None, s1, s2)
    return matcher.ratio()


def weighted_ensemble_score(query, target, weights=None):
    """
    Ensemble multiple similarity metrics with weighted averaging.
    
    Weights: [tfidf, levenshtein, jaro_winkler, ngram, subsequence]
    Default weights optimized through experimentation.
    """
    if weights is None:
        # Optimized weights (sum = 1.0)
        weights = {
            'levenshtein': 0.25,
            'jaro_winkler': 0.30,
            'ngram': 0.25,
            'subsequence': 0.20
        }
    
    scores = {
        'levenshtein': normalized_levenshtein_similarity(query, target),
        'jaro_winkler': jaro_winkler_similarity(query, target),
        'ngram': ngram_similarity(query, target, n=2),
        'subsequence': subsequence_similarity(query, target)
    }
    
    # Weighted sum
    ensemble_score = sum(scores[key] * weights[key] for key in weights)
    
    return ensemble_score, scores


# ------------------------------
# Extract all available conditions
# ------------------------------
def get_all_available_conditions(data):
    """Extract all unique condition variants from the recipe data."""
    conditions = set()
    for recipe_info in data.values():
        conditions.update(recipe_info["variants"].keys())
    return sorted(conditions)


# ------------------------------
# Prepare alias list
# ------------------------------
texts = []
recipe_keys = []

for recipe_key, recipe_info in recipe_data.items():
    for alias in recipe_info["aliases"]:
        texts.append(alias.lower())
        recipe_keys.append(recipe_key)


# ------------------------------
# TF-IDF Vectorizer (Enhanced)
# ------------------------------
vectorizer = TfidfVectorizer(
    analyzer="char_wb",
    ngram_range=(2, 5),
    min_df=1,
    max_df=0.95,
    sublinear_tf=True  # Use logarithmic term frequency
)

vectors = vectorizer.fit_transform(texts)


# ------------------------------
# Optimized Prediction with Ensemble
# ------------------------------
def predict_recipe_optimized(user_input, threshold=0.3, top_n=5):
    """
    Advanced prediction using ensemble of multiple algorithms.
    
    Combines:
    1. TF-IDF with cosine similarity
    2. Levenshtein distance
    3. Jaro-Winkler similarity
    4. N-gram matching
    5. Subsequence matching
    
    Returns:
        List of tuples (recipe_key, final_score, score_breakdown)
    """
    user_input_lower = user_input.lower()
    
    # Step 1: TF-IDF Cosine Similarity
    user_vec = vectorizer.transform([user_input_lower])
    tfidf_scores = cosine_similarity(user_vec, vectors)[0]
    
    # Step 2: Calculate ensemble scores for each recipe alias
    results = {}
    
    for idx, (text, recipe_key) in enumerate(zip(texts, recipe_keys)):
        # Get TF-IDF score
        tfidf_score = tfidf_scores[idx]
        
        # Calculate ensemble score using multiple metrics
        ensemble_score, score_breakdown = weighted_ensemble_score(user_input_lower, text)
        
        # Combine TF-IDF with ensemble (weighted average)
        # TF-IDF weight: 0.4, Ensemble weight: 0.6
        final_score = (0.4 * tfidf_score) + (0.6 * ensemble_score)
        
        # Keep the best score for each recipe
        if recipe_key not in results or final_score > results[recipe_key][0]:
            results[recipe_key] = (final_score, tfidf_score, ensemble_score, score_breakdown)
    
    # Sort by final score
    sorted_results = sorted(results.items(), key=lambda x: x[1][0], reverse=True)
    
    # Filter by threshold and return top N
    filtered_results = [
        (recipe_key, scores[0], scores[1], scores[2], scores[3])
        for recipe_key, scores in sorted_results[:top_n]
        if scores[0] >= threshold
    ]
    
    return filtered_results


# ------------------------------
# Variant Retrieval
# ------------------------------
def get_recipe_variant(data, recipe_key, condition):
    """Get recipe variant for a specific condition."""
    if recipe_key not in data:
        return None, None

    variants = data[recipe_key]["variants"]

    if condition in variants:
        return variants[condition], "condition-specific"
    elif "default" in variants:
        return variants["default"], "default"
    else:
        return None, None


# ------------------------------
# Display condition menu
# ------------------------------
def display_condition_menu(available_conditions):
    """Display a numbered menu of available conditions."""
    print("\n" + "="*50)
    print("AVAILABLE HEALTH CONDITIONS / DIETARY PREFERENCES")
    print("="*50)
    
    for i, condition in enumerate(available_conditions, 1):
        display_name = condition.replace("_", " ").title()
        print(f"{i:2d}. {display_name}")
    
    print("="*50)


# ------------------------------
# Get user condition choice
# ------------------------------
def get_condition_choice(available_conditions):
    """Get user's condition choice with validation."""
    display_condition_menu(available_conditions)
    
    while True:
        choice = input(f"\nSelect a condition (1-{len(available_conditions)}) or type condition name: ").strip()
        
        if choice.isdigit():
            choice_num = int(choice)
            if 1 <= choice_num <= len(available_conditions):
                return available_conditions[choice_num - 1]
            else:
                print(f"❌ Please enter a number between 1 and {len(available_conditions)}")
        else:
            normalized_input = choice.lower().replace(" ", "_")
            if normalized_input in available_conditions:
                return normalized_input
            else:
                print(f"❌ Invalid condition. Please try again.")


# ------------------------------
# Display recipe details
# ------------------------------
def display_recipe(recipe_key, variant, variant_type, confidence, show_breakdown=False, breakdown=None):
    """Display recipe details in a formatted way."""
    print("\n" + "="*60)
    print("🍽️  RECIPE DETAILS")
    print("="*60)
    
    recipe_name = recipe_key.replace("_", " ").title()
    print(f"📌 Recipe: {recipe_name}")
    print(f"🎯 Overall Confidence: {confidence:.2%}")
    print(f"🏷️  Variant: {variant_type.replace('_', ' ').title()}")
    
    if show_breakdown and breakdown:
        print(f"\n📊 Score Breakdown:")
        for metric, score in breakdown.items():
            print(f"   • {metric.replace('_', ' ').title()}: {score:.2%}")
    
    if variant:
        print("\n" + "-"*60)
        print("📋 INGREDIENTS:")
        print("-"*60)
        for ing in variant["ingredients"]:
            print(f"  • {ing['name']} — {ing['qty']}")
        
        print("\n" + "-"*60)
        print("👨‍🍳 INSTRUCTIONS:")
        print("-"*60)
        for step in variant["instructions"]:
            if step.startswith("**"):
                print(f"\n{step}")
            else:
                print(f"{step}")
    else:
        print("\n❌ No recipe available for this condition.")
    
    print("="*60)




# ------------------------------
# Visualization Functions
# ------------------------------
def plot_score_breakdown(score_breakdown, recipe_name, user_input, final_score, filename="score_breakdown.png"):
    """Generate a bar chart showing individual metric scores."""
    metrics = list(score_breakdown.keys())
    scores = [score_breakdown[m] * 100 for m in metrics]
    
    plt.figure(figsize=(10, 6))
    colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A']
    bars = plt.bar(metrics, scores, color=colors, edgecolor='black', linewidth=1.5)
    
    # Add value labels on bars
    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.1f}%',
                ha='center', va='bottom', fontweight='bold', fontsize=10)
    
    plt.xlabel('Similarity Metrics', fontsize=12, fontweight='bold')
    plt.ylabel('Score (%)', fontsize=12, fontweight='bold')
    plt.title(f'Score Breakdown for "{user_input}" → {recipe_name}\nFinal Score: {final_score:.2%}', 
              fontsize=14, fontweight='bold', pad=20)
    plt.ylim(0, 105)
    plt.grid(axis='y', alpha=0.3, linestyle='--')
    plt.xticks(rotation=15, ha='right')
    plt.tight_layout()
    
    filepath = IMAGES_FOLDER / filename
    plt.savefig(filepath, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"✅ Saved: {filepath}")


def plot_score_comparison(tfidf_score, ensemble_score, final_score, recipe_name, filename="score_comparison.png"):
    """Generate a comparison chart of TF-IDF, Ensemble, and Final scores."""
    categories = ['TF-IDF\nScore', 'Ensemble\nScore', 'Final\nScore']
    scores = [tfidf_score * 100, ensemble_score * 100, final_score * 100]
    
    plt.figure(figsize=(10, 6))
    colors = ['#3498db', '#e74c3c', '#2ecc71']
    bars = plt.bar(categories, scores, color=colors, edgecolor='black', linewidth=2, width=0.6)
    
    # Add value labels
    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.1f}%',
                ha='center', va='bottom', fontweight='bold', fontsize=12)
    
    plt.ylabel('Confidence Score (%)', fontsize=12, fontweight='bold')
    plt.title(f'Score Comparison for {recipe_name}', fontsize=14, fontweight='bold', pad=20)
    plt.ylim(0, 105)
    plt.grid(axis='y', alpha=0.3, linestyle='--')
    plt.tight_layout()
    
    filepath = IMAGES_FOLDER / filename
    plt.savefig(filepath, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"✅ Saved: {filepath}")


def plot_top_matches(matches, user_input, filename="top_matches.png"):
    """Generate a horizontal bar chart showing top recipe matches."""
    if not matches:
        return
    
    # Limit to top 5
    top_matches = matches[:5]
    recipe_names = [m[0].replace('_', ' ').title() for m in top_matches]
    final_scores = [m[1] * 100 for m in top_matches]
    
    plt.figure(figsize=(10, 7))
    colors = plt.cm.viridis(np.linspace(0.3, 0.9, len(recipe_names)))
    bars = plt.barh(recipe_names, final_scores, color=colors, edgecolor='black', linewidth=1.5)
    
    # Add value labels
    for i, bar in enumerate(bars):
        width = bar.get_width()
        plt.text(width, bar.get_y() + bar.get_height()/2.,
                f' {width:.1f}%',
                ha='left', va='center', fontweight='bold', fontsize=10)
    
    plt.xlabel('Confidence Score (%)', fontsize=12, fontweight='bold')
    plt.ylabel('Recipe Name', fontsize=12, fontweight='bold')
    plt.title(f'Top Recipe Matches for "{user_input}"', fontsize=14, fontweight='bold', pad=20)
    plt.xlim(0, 105)
    plt.grid(axis='x', alpha=0.3, linestyle='--')
    plt.tight_layout()
    
    filepath = IMAGES_FOLDER / filename
    plt.savefig(filepath, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"✅ Saved: {filepath}")


def plot_metric_weights_pie(filename="metric_weights.png"):
    """Generate a pie chart showing the weights used in ensemble scoring."""
    weights = {
        'Levenshtein': 0.25,
        'Jaro-Winkler': 0.30,
        'N-gram': 0.25,
        'Subsequence': 0.20
    }
    
    labels = list(weights.keys())
    sizes = [w * 100 for w in weights.values()]
    colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A']
    explode = (0.05, 0.05, 0.05, 0.05)
    
    plt.figure(figsize=(10, 8))
    wedges, texts, autotexts = plt.pie(sizes, explode=explode, labels=labels, colors=colors,
                                        autopct='%1.1f%%', startangle=90, textprops={'fontsize': 11, 'fontweight': 'bold'})
    
    # Make percentage text more visible
    for autotext in autotexts:
        autotext.set_color('white')
        autotext.set_fontsize(12)
        autotext.set_fontweight('bold')
    
    plt.title('Ensemble Metric Weights Distribution', fontsize=14, fontweight='bold', pad=20)
    plt.tight_layout()
    
    filepath = IMAGES_FOLDER / filename
    plt.savefig(filepath, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"✅ Saved: {filepath}")


def plot_all_metrics_comparison(score_breakdown, tfidf_score, ensemble_score, final_score, 
                                recipe_name, user_input, filename="all_metrics.png"):
    """Generate a comprehensive visualization with all metrics."""
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle(f'Comprehensive Analysis: "{user_input}" → {recipe_name}', 
                 fontsize=16, fontweight='bold', y=0.995)
    
    # 1. Score Breakdown (Bar Chart)
    metrics = list(score_breakdown.keys())
    scores = [score_breakdown[m] * 100 for m in metrics]
    colors1 = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A']
    bars1 = ax1.bar(metrics, scores, color=colors1, edgecolor='black', linewidth=1.5)
    for bar in bars1:
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height, f'{height:.1f}%',
                ha='center', va='bottom', fontweight='bold', fontsize=9)
    ax1.set_ylabel('Score (%)', fontweight='bold')
    ax1.set_title('Individual Metric Scores', fontweight='bold', pad=10)
    ax1.set_ylim(0, 105)
    ax1.grid(axis='y', alpha=0.3, linestyle='--')
    ax1.tick_params(axis='x', rotation=15)
    
    # 2. Score Comparison (Bar Chart)
    categories = ['TF-IDF', 'Ensemble', 'Final']
    comparison_scores = [tfidf_score * 100, ensemble_score * 100, final_score * 100]
    colors2 = ['#3498db', '#e74c3c', '#2ecc71']
    bars2 = ax2.bar(categories, comparison_scores, color=colors2, edgecolor='black', linewidth=2)
    for bar in bars2:
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2., height, f'{height:.1f}%',
                ha='center', va='bottom', fontweight='bold', fontsize=10)
    ax2.set_ylabel('Score (%)', fontweight='bold')
    ax2.set_title('Score Type Comparison', fontweight='bold', pad=10)
    ax2.set_ylim(0, 105)
    ax2.grid(axis='y', alpha=0.3, linestyle='--')
    
    # 3. Metric Weights (Pie Chart)
    weights = {'Levenshtein': 0.25, 'Jaro-Winkler': 0.30, 'N-gram': 0.25, 'Subsequence': 0.20}
    labels = list(weights.keys())
    sizes = [w * 100 for w in weights.values()]
    colors3 = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A']
    wedges, texts, autotexts = ax3.pie(sizes, labels=labels, colors=colors3,
                                        autopct='%1.1f%%', startangle=90)
    for autotext in autotexts:
        autotext.set_color('white')
        autotext.set_fontsize(10)
        autotext.set_fontweight('bold')
    ax3.set_title('Ensemble Weights', fontweight='bold', pad=10)
    
    # 4. Score Contribution (Stacked Bar)
    tfidf_contribution = tfidf_score * 0.4 * 100
    ensemble_contribution = ensemble_score * 0.6 * 100
    ax4.barh(['Final Score'], [tfidf_contribution], color='#3498db', edgecolor='black', 
             linewidth=2, label=f'TF-IDF (40%): {tfidf_contribution:.1f}%')
    ax4.barh(['Final Score'], [ensemble_contribution], left=[tfidf_contribution], 
             color='#e74c3c', edgecolor='black', linewidth=2, 
             label=f'Ensemble (60%): {ensemble_contribution:.1f}%')
    ax4.set_xlabel('Score Contribution (%)', fontweight='bold')
    ax4.set_title(f'Final Score Composition: {final_score:.2%}', fontweight='bold', pad=10)
    ax4.set_xlim(0, 105)
    ax4.legend(loc='upper right', fontsize=9)
    ax4.grid(axis='x', alpha=0.3, linestyle='--')
    
    plt.tight_layout()
    filepath = IMAGES_FOLDER / filename
    plt.savefig(filepath, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"✅ Saved: {filepath}")


# ------------------------------
# Main
# ------------------------------
def main():
    print("\n" + "🍳"*25)
    print("   OPTIMIZED RECIPE RECOMMENDATION SYSTEM")
    print("   (Enhanced ML with Mathematical Optimization)")
    print("🍳"*25)
    
    # Get all available conditions
    available_conditions = get_all_available_conditions(recipe_data)
    
    # Get recipe name from user
    print("\n📝 Step 1: Enter Recipe Name")
    print("-"*50)
    user_input = input("Enter recipe name: ").strip()
    
    if len(user_input) < 2:
        print("❌ Please enter a longer recipe name.")
        return
    
    # Predict recipe using optimized ensemble method
    print("\n🔍 Analyzing with multiple ML algorithms...")
    matches = predict_recipe_optimized(user_input, threshold=0.25, top_n=5)
    
    if not matches:
        print("\n❌ No confident recipe match found.")
        print("💡 Try using different keywords or check spelling.")
        return
    
    # Automatically select the highest-scoring recipe
    recipe_key, final_score, tfidf_score, ensemble_score, score_breakdown = matches[0]
    
    # Show what was matched
    recipe_name = recipe_key.replace("_", " ").title()
    print(f"\n✅ Matched Recipe: {recipe_name}")
    print(f"   📊 Final Score: {final_score:.2%}")
    print(f"   🔤 TF-IDF Score: {tfidf_score:.2%}")
    print(f"   🎲 Ensemble Score: {ensemble_score:.2%}")
    
    # Generate all visualizations
    print("\n📊 Generating visualization images...")
    print("-"*50)
    
    # Generate individual charts
    plot_score_breakdown(score_breakdown, recipe_name, user_input, final_score, 
                        filename=f"score_breakdown_{recipe_key}.png")
    
    plot_score_comparison(tfidf_score, ensemble_score, final_score, recipe_name,
                         filename=f"score_comparison_{recipe_key}.png")
    
    plot_top_matches(matches, user_input, 
                    filename=f"top_matches_{user_input.replace(' ', '_')}.png")
    
    plot_metric_weights_pie(filename="metric_weights.png")
    
    plot_all_metrics_comparison(score_breakdown, tfidf_score, ensemble_score, final_score,
                               recipe_name, user_input, 
                               filename=f"comprehensive_analysis_{recipe_key}.png")
    
    print("-"*50)
    print(f"✅ All images saved to '{IMAGES_FOLDER}' folder!")
    
    # Get user's condition choice
    print("\n📝 Step 2: Select Health Condition / Dietary Preference")
    print("-"*50)
    condition = get_condition_choice(available_conditions)
    
    # Get recipe variant
    variant, variant_type = get_recipe_variant(recipe_data, recipe_key, condition)
    
    # Display results
    display_recipe(recipe_key, variant, variant_type, final_score, 
                   show_breakdown=True, breakdown=score_breakdown)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
    except Exception as e:
        print(f"\n❌ An error occurred: {e}")
        import traceback
        traceback.print_exc()
