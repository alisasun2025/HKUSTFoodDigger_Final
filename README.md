# HKUST Food Digger

HKUST Food Digger is a Streamlit app for discovering restaurants around the Hong Kong University of Science and Technology. Describe what you feel like eating in your own words, then narrow the search by location or cuisine.

## Features

- Search in natural language using Pinecone's multilingual embeddings.
- Filter by cuisine and by area: HKUST, Po Lam, Hang Hau, or Tseung Kwan O.
- Compare up to three restaurants by search relevance, rating, price range, and review excerpts.
- Open a restaurant's detail page to see an English AI summary based on retrieved reviews, reference photos, and a Google Maps link when available.
- Give feedback on recommendations. The app appends feedback to a local `feedback_log.txt` file.

## Local setup

You need Python 3, a Pinecone API key with access to a populated restaurant index and Pinecone Inference, and a DeepSeek API key for review summaries.

From the extracted project directory, create a virtual environment and install the dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

On Windows PowerShell, activate the environment with `.\.venv\Scripts\Activate.ps1`. For Playwright-based photo capture, install Chromium with `python -m playwright install chromium`. The app falls back to displaying image URLs when capture fails.

### Configure credentials

The archive contains empty, commented-out API key placeholders. To load credentials from the environment, replace those two placeholders in `backend_logic.py` with the lines below. The module already imports `os`.

```python
PINECONE_API_KEY = os.environ["PINECONE_API_KEY"]
DEEPSEEK_API_KEY = os.environ["DEEPSEEK_API_KEY"]
```

Set the corresponding environment variables in the terminal session you use to launch the app. Keep real credentials out of source control.

### Connect the restaurant index

By default, the app queries the `restaurants` namespace in the Pinecone index `semantic-multilingual-e5-large-index`. If your index has a different name, update `INDEX_NAME` in `backend_logic.py`.

The project archive contains the app source and dependency list. Restaurant vectors and an ingestion script are separate prerequisites. The index needs restaurant or review vectors compatible with the `multilingual-e5-large` query embeddings. The app uses `parent_id` or `google_id` to group records by restaurant, `region` and `categories` for filters, and `text` for review excerpts. Display metadata can include `name`, `rating`, `price_range`, `place_url`, `featured_photo`, and `image_url` or `review_image_url`.

### Start the app

```bash
python -m streamlit run frontend.py
```

Open the local URL printed in the terminal. Try a search such as “Affordable ramen near Hang Hau,” then select **View Details** on a result to see the review summary and original excerpts.

## How search works

The backend embeds the query with Pinecone's `multilingual-e5-large` model and retrieves matching records from the restaurant index. It groups records by restaurant and ranks each restaurant by its highest vector similarity score. The percentage shown in the UI is derived from that score. On the detail page, the app sends the search query, restaurant name, and up to three retrieved excerpts to DeepSeek's `deepseek-chat` model to generate the English summary.

## Project files

- `frontend.py` renders the Streamlit search and detail pages and handles photo display.
- `backend_logic.py` handles Pinecone retrieval, restaurant ranking, DeepSeek summaries, and feedback logging.
- `requirements.txt` lists the Python dependencies.
