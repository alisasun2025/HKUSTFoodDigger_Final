import streamlit as st
import random
import os
import time
import base64
from PIL import Image
from io import BytesIO
# Note: backend_logic.py must be in the same directory as app.py
import backend_logic as backend

# Try importing playwright, provide prompt if failed
try:
    from playwright.sync_api import sync_playwright

    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

# ============ PAGE SETTINGS ============
st.set_page_config(
    page_title="HKUST Food Digger",
    layout="wide"
)

# ============ RANDOM HINTS ============
HINTS = [
    "I want some spicy noodle...",
    "Good burger near UST...",
    "Something healthy and vegetarian...",
    "Hot pot for cold days...",
    "Economic Cantonese cafe...",
    "Coffee shop with study space...",
    "Japanese ramen nearby...",
    "Quick fast food option..."
]


def get_random_hint():
    return random.choice(HINTS)


MATCH_SCORE = 85


def get_match_label(score):
    return "Excellent" if score >= 80 else "Good" if score >= 60 else "Not Good"


SCREENSHOT_PATH = "restaurant_screenshot.png"
PROXY = ""  # For mainland China: set proxy (e.g., "http://127.0.0.1:7890")
CACHE_EXPIRE_HOURS = 24
UNIFORM_IMAGE_HEIGHT = 300  # Uniform image height


# ============ CORE UTILITY FUNCTIONS ============
def take_page_screenshot(url):
    """Take a screenshot of the image page (bypasses URL extraction)"""
    if not HAS_PLAYWRIGHT or not url:
        return None

    try:
        screenshot_file = f"temp_{hash(url)}.png"
        with sync_playwright() as p:
            launch_args = ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
            if PROXY:
                launch_args.append(f"--proxy-server={PROXY}")
            browser = p.chromium.launch(headless=True, args=launch_args, timeout=60000)
            context = browser.new_context(viewport={"width": 1200, "height": 900})
            page = context.new_page()
            page.goto(url, wait_until="networkidle", timeout=60000)
            main_img = page.wait_for_selector("img[src*='googleusercontent']", timeout=10000)
            if main_img:
                img_bbox = main_img.bounding_box()
                if img_bbox:
                    page.screenshot(
                        path=screenshot_file,
                        clip={
                            "x": img_bbox["x"],
                            "y": img_bbox["y"],
                            "width": img_bbox["width"],
                            "height": img_bbox["height"]
                        },
                        type="png"
                    )
            browser.close()
        if os.path.exists(screenshot_file):
            with open(screenshot_file, "rb") as f:
                img_bytes = f.read()
            os.remove(screenshot_file)
            return img_bytes
        return None
    except Exception as e:
        return None


def resize_image_keep_ratio(img_bytes, target_height=UNIFORM_IMAGE_HEIGHT):
    try:
        img = Image.open(BytesIO(img_bytes))
        ratio = target_height / img.height
        new_width = int(img.width * ratio)
        resized_img = img.resize((new_width, target_height), Image.Resampling.LANCZOS)
        buf = BytesIO()
        resized_img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception as e:
        return img_bytes


def capture_restaurant_screenshot(url, save_path):
    if not HAS_PLAYWRIGHT or not url:
        return None

    if os.path.exists(save_path):
        file_mtime = os.path.getmtime(save_path)
        if (time.time() - file_mtime) < (CACHE_EXPIRE_HOURS * 3600):
            return save_path
    try:
        with sync_playwright() as p:
            launch_args = ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
            if PROXY:
                launch_args.append(f"--proxy-server={PROXY}")
            browser = p.chromium.launch(headless=True, args=launch_args, timeout=60000)
            context = browser.new_context()
            page = context.new_page()
            page.set_viewport_size({"width": 1200, "height": 800})
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(3000)
            page.screenshot(path=save_path, full_page=False, type="png")
            browser.close()
        return save_path if os.path.exists(save_path) else None
    except Exception as e:
        return None


def image_to_base64(image_path):
    if not os.path.exists(image_path):
        return None
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode()


# ============ RESTAURANT CATEGORY OPTIONS ============
from backend_logic import CATEGORY_MAPPING

CATEGORIES = ["All Categories"] + list(CATEGORY_MAPPING.keys())
REGIONS_LIST = ["HKUST", "Po Lam", "Hang Hau", "Tseung Kwan O"]

# ============ CUSTOM STYLES ============
st.markdown("""
<style>
    .main-title { text-align: center; font-size: 42px; font-weight: bold; color: #1E3A8A; margin-bottom: 0; padding-top: 30px; }
    .sub-title { text-align: center; font-size: 22px; color: #6B7280; margin-top: -10px; margin-bottom: 40px; }
    .search-hint { color: #7B8794; font-size: 14px; font-style: italic; margin-top: 8px; margin-bottom: 15px; }
    .result-card { background-color: #FFFFFF; border-radius: 10px; padding: 20px; margin-bottom: 20px; border: 1px solid #E5E7EB; box-shadow: 0 2px 6px rgba(0,0,0,0.05); transition: transform 0.2s; }
    .result-card:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
    .sidebar-title { font-size: 16px; font-weight: 600; color: #374151; margin-bottom: 15px; }
    .restaurant-title { color: #2E86AB; margin-bottom: 10px; }
    .match-score { text-align: center; padding: 25px; background: #F18F01; border-radius: 12px; margin-top: 30px; }
    .match-score h2 { color: white; margin: 0; font-size: 36px; }
    .match-score p { color: white; font-size: 20px; margin: 10px 0 0 0; }
</style>
""", unsafe_allow_html=True)

# ============ APPLICATION STATE MANAGEMENT ============
if 'current_page' not in st.session_state:
    st.session_state.current_page = "search"
if 'selected_restaurant' not in st.session_state:
    st.session_state.selected_restaurant = None

# Region States
if 'region_states' not in st.session_state:
    st.session_state.region_states = {r: True for r in REGIONS_LIST}
if 'all_regions_selected' not in st.session_state:
    st.session_state.all_regions_selected = True

# Category States (使用 selected_categories 作为实际搜索用的值)
if 'selected_categories' not in st.session_state:
    st.session_state.selected_categories = ["All Categories"]
# 新增：用来记录上一次选择状态，以便比较变化
if 'previous_categories' not in st.session_state:
    st.session_state.previous_categories = ["All Categories"]

if 'current_hint' not in st.session_state:
    st.session_state.current_hint = get_random_hint()

# Search States
if 'search_results' not in st.session_state:
    st.session_state.search_results = []
if 'has_searched' not in st.session_state:
    st.session_state.has_searched = False
if 'last_search_query' not in st.session_state:
    st.session_state.last_search_query = ""


# ============ CALLBACKS (LOGIC CORE) ============

# 1. 地区全选逻辑
def toggle_all_regions():
    new_state = st.session_state.all_regions_check
    st.session_state.all_regions_selected = new_state
    for r in REGIONS_LIST:
        st.session_state.region_states[r] = new_state
        st.session_state[f"region_{r}"] = new_state


# 2. 地区单选逻辑
def update_region_state():
    for r in REGIONS_LIST:
        st.session_state.region_states[r] = st.session_state[f"region_{r}"]
    all_checked = all(st.session_state.region_states.values())
    st.session_state.all_regions_selected = all_checked
    st.session_state.all_regions_check = all_checked


# 3. [修复] 分类全选互斥逻辑
def update_categories_logic():
    # 获取用户刚刚在 Multiselect 做出的最新选择
    current_selection = st.session_state.cat_select_widget
    # 获取上一次的选择
    previous_selection = st.session_state.previous_categories

    final_selection = current_selection

    # 逻辑 A: 用户刚点击了 "All Categories" (之前没有，现在有了) -> 清空其他
    if "All Categories" in current_selection and "All Categories" not in previous_selection:
        final_selection = ["All Categories"]

    # 逻辑 B: 用户在已有 "All Categories" 的情况下选了别的 -> 去掉 "All Categories"
    elif "All Categories" in current_selection and len(current_selection) > 1:
        final_selection = [c for c in current_selection if c != "All Categories"]

    # 逻辑 C: 用户取消了所有选择 -> 强制回滚到 "All Categories"
    elif not current_selection:
        final_selection = ["All Categories"]

    # 逻辑 D: 用户手动选了所有具体选项 -> 自动变成 "All Categories"
    # 获取所有具体选项集合
    all_specific = set(CATEGORIES[1:])
    if set(final_selection) == all_specific:
        final_selection = ["All Categories"]

    # 将最终决定的值写回 Widget 和 State
    st.session_state.cat_select_widget = final_selection
    st.session_state.selected_categories = final_selection
    # 更新历史记录
    st.session_state.previous_categories = final_selection


# ============ PAGE FUNCTIONS ============
def show_search_page():
    """Display search page"""
    st.markdown('<h1 class="main-title">HKUST Food Digger</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-title">Only the right picks.</p>', unsafe_allow_html=True)

    col1, col2 = st.columns([1, 3])

    with col1:
        # ===== LEFT SIDEBAR FUNCTIONALITY =====
        st.markdown('<div class="sidebar-title">Region Selection</div>', unsafe_allow_html=True)

        st.checkbox("Select All",
                    value=st.session_state.all_regions_selected,
                    key="all_regions_check",
                    on_change=toggle_all_regions)

        for region in REGIONS_LIST:
            st.checkbox(region,
                        value=st.session_state.region_states.get(region, True),
                        key=f"region_{region}",
                        on_change=update_region_state)

        selected_count = sum(1 for r in REGIONS_LIST if st.session_state.region_states.get(r, False))
        st.caption(f"Selected: {selected_count} region(s)")

        if st.session_state.selected_restaurant:
            if st.button("← Back to Details", type="secondary", use_container_width=True):
                st.session_state.current_page = "details"
                st.rerun()

    with col2:
        # ===== RIGHT MAIN CONTENT AREA =====
        st.markdown('<div style="margin-bottom: 10px; font-size: 14px; color: #5d6d7e;">Restaurant Type</div>',
                    unsafe_allow_html=True)

        # [修复] Multiselect 使用回调函数处理逻辑
        st.multiselect(
            "",
            options=CATEGORIES,
            default=st.session_state.selected_categories,
            label_visibility="collapsed",
            key="cat_select_widget",  # 绑定的key
            on_change=update_categories_logic  # 绑定的回调
        )

        st.markdown('<div style="margin-top: 25px;"></div>', unsafe_allow_html=True)
        st.markdown('<div style="margin-bottom: 5px; font-size: 14px; color: #5d6d7e;">Search for restaurants</div>',
                    unsafe_allow_html=True)

        search_col1, search_col2 = st.columns([4, 1])
        with search_col1:
            search_query = st.text_input("",
                                         placeholder="What are you looking for?",
                                         label_visibility="collapsed",
                                         key="search_input")
        with search_col2:
            search_clicked = st.button("Search", type="primary", use_container_width=True)

        hint_text = f"**Hints:** {st.session_state.current_hint}"
        st.markdown(f'<div class="search-hint">{hint_text}</div>', unsafe_allow_html=True)

        if st.button("🔄 New Hint", key="refresh_hint"):
            st.session_state.current_hint = get_random_hint()
            st.rerun()

        st.markdown("---")

        # ===== SEARCH LOGIC =====
        if search_clicked and search_query:
            st.session_state.last_search_query = search_query

            search_regions = [r for r in REGIONS_LIST if st.session_state.region_states.get(r, False)]
            # 确保使用 session_state 中的最新值
            search_cats = [] if "All Categories" in st.session_state.selected_categories else st.session_state.selected_categories

            with st.spinner("🔍 Digging deep into our database..."):
                real_results = backend.perform_search(
                    query_text=search_query,
                    region_filter=search_regions,
                    category_filters=search_cats,
                    limit_count=3
                )

            st.session_state.search_results = real_results
            st.session_state.has_searched = True

        # ===== RENDER RESULTS =====
        if st.session_state.has_searched:
            current_display_query = st.session_state.last_search_query
            st.markdown(f"### Results for: **'{current_display_query}'**")

            results_to_show = st.session_state.search_results

            if results_to_show:
                st.markdown(f"**Found {len(results_to_show)} restaurant(s)**")

                for rest in results_to_show:
                    review_snippet = rest['suggestions'][0] if rest['suggestions'] else "No review snippet available."
                    if len(review_snippet) > 150:
                        review_snippet = review_snippet[:150] + "..."

                    st.markdown(f"""
                    <div class="result-card">
                        <h4 style="margin: 0 0 10px 0; color: #2c3e50;">{rest['name']}</h4>
                        <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                            <div><span style="color: #e74c3c; font-weight: 500;">⭐ {rest['rating']}</span></div>
                            <div><span style="color: #27ae60; font-weight: 500;">{rest['price_range']}</span></div>
                        </div>
                        <div style="margin-bottom: 8px; color: #34495e; font-size: 14px;">📍 {rest['place_url']}</div>
                        <div style="margin-bottom: 10px;">
                            <span style="background-color: #4a6fa5; color: white; padding: 3px 10px; border-radius: 12px; font-size: 12px; margin-right: 8px;">
                                {rest['match_label']} ({rest['match_percentage']})
                            </span>
                            <span style="color: #7f8c8d; font-size: 13px;">{rest['food_type']}</span>
                        </div>
                        <div style="color: #5d6d7e; font-size: 14px;">" {review_snippet} "</div>
                    </div>
                    """, unsafe_allow_html=True)

                    if st.button(f"View {rest['name']} Details", key=f"btn_{rest['name']}", use_container_width=True):
                        st.session_state.selected_restaurant = rest
                        st.session_state.current_query = current_display_query
                        st.session_state.current_page = "details"
                        st.rerun()
            else:
                st.warning("No restaurants found. Try adjusting your filters.")

        else:
            st.markdown("""
            <div style="text-align: center; padding: 60px 20px; color: #7f8c8d;">
                <div style="font-size: 48px; margin-bottom: 20px;">🔍</div>
                <h3 style="color: #5d6d7e; margin-bottom: 15px;">Search for your perfect meal</h3>
            </div>
            """, unsafe_allow_html=True)


def show_details_page():
    """Display restaurant details page"""
    if not st.session_state.selected_restaurant:
        st.session_state.current_page = "search"
        st.rerun()
        return

    rest = st.session_state.selected_restaurant

    if st.button("← Back to Search", type="secondary"):
        st.session_state.current_page = "search"
        st.rerun()

    st.divider()

    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"<h1 class='restaurant-title'>{rest['name']}</h1>", unsafe_allow_html=True)
        if rest['place_url'] and rest['place_url'].startswith("http"):
            st.markdown(
                f"<a href='{rest['place_url']}' target='_blank' style='font-size:16px;'>📍 View on Google Maps</a>",
                unsafe_allow_html=True)
        else:
            st.markdown(f"<p style='font-size:16px;'>📍 {rest['place_url']}</p>", unsafe_allow_html=True)

    with col2:
        match_score = int(rest['match_percentage'].replace('%', ''))
        match_label = rest['match_label']
        st.markdown(
            f"<div class='match-score'>"
            f"<h2>{match_score}%</h2>"
            f"<p>{match_label}</p>"
            f"</div>", unsafe_allow_html=True
        )

    st.divider()

    col3, col4, col5 = st.columns(3)
    with col3:
        st.markdown(f"<h4 style='color:#2E86AB; margin-bottom:10px;'>Rating</h4>", unsafe_allow_html=True)
        st.markdown(f"<p style='font-size:32px; color:#F18F01; font-weight:bold; margin:0;'>{rest['rating']}/5.0</p>",
                    unsafe_allow_html=True)
    with col4:
        st.markdown(f"<h4 style='color:#2E86AB; margin-bottom:10px;'>Price Range</h4>", unsafe_allow_html=True)
        st.markdown(f"<p style='font-size:24px; color:#333; margin:0;'>{rest['price_range']}</p>",
                    unsafe_allow_html=True)
    with col5:
        st.markdown(f"<h4 style='color:#2E86AB; margin-bottom:10px;'>Food Type</h4>", unsafe_allow_html=True)
        st.markdown(f"<p style='font-size:20px; color:#333; margin:0;'>{rest['food_type']}</p>", unsafe_allow_html=True)

    st.divider()

    st.markdown(f"<h3 style='color:#2E86AB; margin-bottom:15px;'>AI Suggestions</h3>", unsafe_allow_html=True)

    with st.spinner("Our AI is digging food for you..."):
        user_query = st.session_state.get("current_query", "good food")
        ai_summary = backend.generate_ai_summary(rest['name'], rest['suggestions'], user_query)

        st.info(ai_summary)

        with st.expander("See original reviews"):
            for s in rest['suggestions']:
                st.markdown(f"- *{s}*")

    st.divider()

    st.markdown(f"<h3 style='color:#2E86AB; margin-bottom:15px;'>Reference Photos</h3>", unsafe_allow_html=True)

    photos_to_show = []
    if rest['image_pool']:
        photos_to_show.extend(rest['image_pool'])
    if rest['featured_photo']:
        photos_to_show.append(rest['featured_photo'])

    unique_photos = list(set(photos_to_show))[:3]

    if unique_photos:
        cols = st.columns(len(unique_photos))
        for col, img_url in zip(cols, unique_photos):
            with col:
                if HAS_PLAYWRIGHT:
                    img_bytes = take_page_screenshot(img_url)
                    if img_bytes:
                        resized = resize_image_keep_ratio(img_bytes)
                        st.image(resized, use_container_width=True)
                    else:
                        st.image(img_url, use_container_width=True)
                else:
                    st.image(img_url, use_container_width=True)
    else:
        st.info("No photos available for this restaurant.")

    st.divider()

    st.markdown(f"<h3 style='color:#2E86AB; margin-bottom:20px;'>User Feedback</h3>", unsafe_allow_html=True)
    feedback = st.radio("Do you like our recommendation?", ("", "✅ Yes", "❌ No"), horizontal=True)

    if feedback == "✅ Yes":
        backend.save_feedback(f"Liked: {rest['name']}", True)
        st.success("We like it too! Thank you 😊")
    elif feedback == "❌ No":
        suggestion = st.text_area("Got suggestions?")
        if st.button("Submit"):
            backend.save_feedback(f"Disliked: {rest['name']} - {suggestion}", False)
            st.success("Thank you! We will improve.")


# ============ MAIN APPLICATION LOGIC ============
def main():
    if st.session_state.current_page == "search":
        show_search_page()
    else:
        show_details_page()

    st.markdown("---")
    st.markdown("<div style='text-align: center; color: #6B7280; padding: 20px;'>HKUST Food Digger • Since 2025</div>",
                unsafe_allow_html=True)


if __name__ == "__main__":
    main()