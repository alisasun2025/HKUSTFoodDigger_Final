import pinecone
import streamlit as st
import os
from openai import OpenAI

# ======================================================
# 🔑 CONFIGURATION
# ======================================================
PINECONE_API_KEY = "pcsk_2B4gJF_3FqPEuFMpAUSEpSmhaBREXNN2RvNVxS2dTrzLcivSPnSJ1cbGBCGPhwgU5ANMnM"
INDEX_NAME = "semantic-multilingual-e5-large-index"
DEEPSEEK_API_KEY = "sk-c42c5bc28ff04873bbfcd3e3f8703d35"

# ======================================================
# 📂 CATEGORY MAPPING
# ======================================================
CATEGORY_MAPPING = {
    "Chinese": [
        "Chinese restaurant", "Cantonese restaurant", "Dim sum restaurant",
        "Shanghainese restaurant", "Sichuan restaurant", "Mandarin restaurant",
        "Chinese noodle restaurant", "Noodle shop", "Dumpling restaurant",
        "Steamed bun shop", "Porridge restaurant", "Wok restaurant",
        "Seafood restaurant", "Taiwanese restaurant"
    ],
    "Cha Chaan Teng (HK Style)": [
        "Cha chaan teng (Hong Kong-style cafe)",
        "Hong Kong style fast food restaurant",
        "Breakfast restaurant",
        "Syokudo and Teishoku restaurant"
    ],
    "Japanese / Korean": [
        "Japanese restaurant", "Authentic Japanese restaurant", "Sushi restaurant",
        "Conveyor belt sushi restaurant", "Sushi takeaway", "Ramen restaurant",
        "Udon noodle restaurant", "Japanese curry restaurant", "Seafood donburi restaurant",
        "Tempura donburi restaurant", "Gyudon restaurant", "Kushiyaki restaurant",
        "Izakaya restaurant", "Korean restaurant", "Yakiniku restaurant"
    ],
    "Southeast Asian / Thai / Indian": [
        "Asian restaurant", "Southeast Asian restaurant",
        "Thai restaurant", "Vietnamese restaurant", "Pho restaurant",
        "Singaporean restaurant", "Malaysian restaurant",
        "Indian restaurant", "Indian takeaway", "Biryani restaurant",
        "Middle Eastern restaurant", "Lebanese restaurant", "Turkish restaurant",
        "Falafel restaurant", "Kebab shop"
    ],
    "Western": [
        "Western restaurant", "Italian restaurant", "French restaurant",
        "American restaurant", "German restaurant", "Belgian restaurant",
        "European restaurant", "Scandinavian restaurant", "Mediterranean restaurant",
        "Pizza restaurant", "Pizza takeaway", "Pizza delivery",
        "Steak house", "Grill", "Pasta shop"
    ],
    "Fast Food": [
        "Fast food restaurant", "Takeout restaurant",
        "Hamburger restaurant", "Sandwich shop", "Hoagie restaurant",
        "Chicken restaurant", "Chicken shop",
        "Chinese takeaway", "Self service restaurant", "Food court"
    ],
    "Cafe / Dessert / Bakery": [
        "Cafe", "Coffee shop", "Coffee store", "Snack bar",
        "Bakery", "Pastry shop", "Dessert restaurant"
    ],
    "Hot Pot / BBQ": [
        "Hot pot restaurant", "Buffet restaurant",
        "Shabu-shabu restaurant",
        "Yakiniku restaurant"
    ]
}

# ======================================================
# 🧠 CORE LOGIC (Manual Drive Mode)
# ======================================================

# Initialize Pinecone client (global, for embedding)
pc = pinecone.Pinecone(api_key=PINECONE_API_KEY)


@st.cache_resource
def init_index():
    """Initialize Index connection"""
    try:
        index = pc.Index(INDEX_NAME)
        return index
    except Exception as e:
        st.error(f"Failed to connect to Index: {e}")
        return None


def perform_search(query_text, region_filter, category_filters=None, limit_count=3):
    index = init_index()
    if not index:
        return []

    # --- 1. Prepare Filters ---
    target_regions = set(region_filter) if region_filter and len(region_filter) < 4 else set()

    target_categories = set()
    if category_filters:
        for cat in category_filters:
            target_categories.update(CATEGORY_MAPPING.get(cat, []))

    conditions = []
    if target_regions:
        conditions.append({"region": {"$in": list(target_regions)}})
    if target_categories:
        conditions.append({"categories": {"$in": list(target_categories)}})

    pinecone_filter = {}
    if len(conditions) == 1:
        pinecone_filter = conditions[0]
    elif len(conditions) > 1:
        pinecone_filter = {"$and": conditions}

    # Search Text (Default to "food")
    search_input = query_text if query_text.strip() else "food"

    # --- 2. MANUAL STEP A: Generate Embedding ---
    # This was the only successful path tested previously
    try:
        embeddings = pc.inference.embed(
            model="multilingual-e5-large",
            inputs=[search_input],
            parameters={"input_type": "query"}
        )
        query_vector = embeddings[0]['values']
    except Exception as e:
        print(f"❌ Embed Error: {e}")
        return []

    # --- 3. MANUAL STEP B: Query Index ---
    # Use the underlying query method, guaranteed to work
    try:
        results = index.query(
            namespace="restaurants",
            vector=query_vector,
            top_k=100,  # Fetch enough for deduplication
            filter=pinecone_filter if pinecone_filter else None,
            include_metadata=True  # Must be set to True
        )

        matches = results.get('matches', [])
        if not matches:
            return []

    except Exception as e:
        print(f"❌ Query Error: {e}")
        return []

    # --- 4. Process, Group & Deduplicate ---
    unique_restaurants = {}

    for match in matches:
        meta = match.get('metadata', {})
        if not meta:
            continue

        score = match.get('score', 0)
        rest_id = meta.get('parent_id') or meta.get('google_id')
        if not rest_id:
            continue

        # Initialize
        if rest_id not in unique_restaurants:
            unique_restaurants[rest_id] = {
                "name": meta.get('name', 'Unknown'),
                "rating": meta.get('rating', 0),
                "price_range": meta.get('price_range', 'N/A'),
                "place_url": meta.get('place_url', ''),
                "featured_photo": meta.get('featured_photo', ''),
                "categories": meta.get('categories', []),
                "region": meta.get('region', ''),

                "max_score": score,
                "suggestions": [],
                "image_pool": []
            }

        # Update Score
        if score > unique_restaurants[rest_id]['max_score']:
            unique_restaurants[rest_id]['max_score'] = score

        # Deduplicate Text
        chunk_text = meta.get('text', '')
        if chunk_text and chunk_text not in unique_restaurants[rest_id]['suggestions']:
            if len(unique_restaurants[rest_id]['suggestions']) < 3:
                unique_restaurants[rest_id]['suggestions'].append(chunk_text)

        # Collect Images
        img_url = meta.get('image_url') or meta.get('review_image_url')
        if img_url:
            unique_restaurants[rest_id]['image_pool'].append(img_url)

    # --- 5. Sort & Format ---
    sorted_rests = sorted(
        unique_restaurants.values(),
        key=lambda x: x['max_score'],
        reverse=True
    )
    final_list = sorted_rests[:limit_count]

    formatted_results = []
    for rest in final_list:
        match_pct = int(rest['max_score'] * 100)

        if match_pct >= 85:
            label = "Excellent Match"
        elif match_pct >= 80:
            label = "Good Match"
        else:
            label = "Fair Match"

        display_image = ""
        if rest['image_pool']:
            display_image = rest['image_pool'][0]
        elif rest['featured_photo']:
            display_image = rest['featured_photo']

        cats = rest.get('categories', [])
        if isinstance(cats, list):
            food_type_str = " / ".join(cats[:2])
        else:
            food_type_str = str(cats)

        formatted_results.append({
            "name": rest['name'],
            "match_percentage": f"{match_pct}%",
            "match_label": label,
            "rating": rest['rating'],
            "price_range": rest['price_range'],
            "food_type": food_type_str,
            "suggestions": rest['suggestions'],
            "image_url": display_image,
            "place_url": rest['place_url'],
            "image_pool": rest['image_pool'],  # Needed for frontend detail page gallery
            "featured_photo": rest['featured_photo'],  # Needed as fallback image
            "region": rest['region']
        })

    return formatted_results


def generate_ai_summary(restaurant_name, suggestions, user_query):
    if not suggestions:
        return "Not enough reviews for AI summary."
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

    context_text = "\n".join([f"- {s}" for s in suggestions])
    system_prompt = """
    You are a seasoned senior student and experienced food reviewer at HKUST.
    Your task is to generate a comprehensive, structured summary of the restaurant based on the provided real user reviews.

    The response MUST be in English only. No Emojis.

    Output Format (STRICTLY adhere to this):
    1. The final response MUST consist of exactly two natural-sounding paragraphs, separated by a single newline.
    2. DO NOT include any structural labels, headers, or bullet points in your final output (e.g., AVOID "Paragraph 1:", "Tip:", or "Summary:").

    Content Guidelines:

    First Paragraph (User Focus & Relevance):
    - **Length:** Target 75 words (between 50 and 100 words).
    - Directly assess how well the restaurant's offerings (food, price, value) meet the specific needs expressed in the "User Search" query.
    - Use the restaurant's name and details from the reviews to clearly state the recommendation or warning related to the user's intent.

    Second Paragraph (General Vibe, Service & Tips):
    - **Length:** Target 75 words (between 50 and 100 words).
    - Summarize the general atmosphere, service quality, overall experience, and common recommendations (like signature dishes).
    - Include one clear and actionable piece of advice or warning mentioned in the reviews (e.g., be prepared for slow service, must-try dish, peak hours to avoid).

    Total word count for the entire summary must be less than 200 words (aim for around 150 words).
    """
    user_prompt = f"Search: {user_query}\nRestaurant: {restaurant_name}\nReviews:\n{context_text}\n\nSummary:"

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            temperature=0.7, stream=False
        )
        return response.choices[0].message.content.strip()
    except:
        return "AI is taking a nap. Check reviews below."


def save_feedback(text, is_positive=False):
    try:
        with open("feedback_log.txt", "a", encoding="utf-8") as f:
            status = "POSITIVE" if is_positive else "NEGATIVE"
            f.write(f"[{status}] {text}\n")
        return True
    except:
        return False


# ======================================================
# 🧪 BACKEND HEALTH CHECK (Manual Mode)
# ======================================================
if __name__ == "__main__":
    print("🏥 Starting Backend Health Check (Manual Mode)...\n")

    # 1. Test raw search
    print("Test 1: Search 'food' (No Filter)")
    res1 = perform_search("food", [], [], 1)
    if res1:
        print(f"✅ Pass (Found: {res1[0]['name']})")
    else:
        print("❌ FAIL")

    # 2. Test filtered search
    print("\nTest 2: Search 'food' + Category [Chinese]")
    res2 = perform_search("food", [], ["Chinese"], 1)
    if res2:
        print(f"✅ Pass (Found: {res2[0]['name']} - {res2[0]['food_type']})")
    else:
        print("❌ FAIL")
