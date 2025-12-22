"""FastAPI web application for Public Pain Archive."""

from datetime import datetime

from fastapi import FASTAPI, Form
from fastapi.responses import HTMLResponse

from .config import get_settings
from .store import AsyncStore

app = FASTAPI(title="Pain Radar Public Archive")
settings = get_settings()

# We might not have a templates dir, so let's use a simple HTML generator or inline templates
# For a proper GTM, we'd want nice UI.
# Let's create a minimalistic HTML styled with something simple (e.g. Simple.css or Tailwind CDN)

HTML_BS = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Public Pain Archive</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-50 text-gray-900 font-sans">
    <div class="max-w-4xl mx-auto py-12 px-4 sm:px-6 lg:px-8">
        {content}
    </div>
</body>
</html>
"""


async def get_store():
    store = AsyncStore(settings.db_path)
    await store.connect()
    try:
        yield store
    finally:
        await store.close()


@app.get("/", response_class=HTMLResponse)
async def read_root():
    # Show list of weeks available
    # For now, just show a placeholder or latest week
    return HTML_BS.format(
        content="""
        <div class="text-center">
            <h1 class="text-4xl font-bold mb-4">Public Pain Archive</h1>
            <p class="text-xl text-gray-600 mb-8">
                I track recurring pain points in niche subreddits. 
                No scraping private data, no spam. Just clusters of public problems.
            </p>
            <div class="bg-white shadow overflow-hidden sm:rounded-lg p-6">
                <h3 class="text-lg leading-6 font-medium text-gray-900">Latest Reports</h3>
                <ul class="divide-y divide-gray-200 mt-4">
                    <li class="py-4">
                        <a href="/archive/latest" class="text-indigo-600 hover:text-indigo-900">
                            Latest Weekly Digest
                        </a>
                    </li>
                </ul>
            </div>
            
            <div class="mt-12">
                <h3 class="text-lg font-medium text-gray-900">Get Alerts</h3>
                <form action="/alerts" method="post" class="mt-4 flex justify-center">
                    <input type="email" name="email" placeholder="you@example.com" required 
                           class="shadow-sm focus:ring-indigo-500 focus:border-indigo-500 block w-64 sm:text-sm border-gray-300 rounded-md p-2 border mr-2">
                    <input type="text" name="keyword" placeholder="keyword (e.g. 'stripe')" required 
                           class="shadow-sm focus:ring-indigo-500 focus:border-indigo-500 block w-48 sm:text-sm border-gray-300 rounded-md p-2 border mr-2">
                    <button type="submit" class="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500">
                        Subscribe
                    </button>
                </form>
                <p class="text-sm text-gray-500 mt-2">I only look for the exact keyword. No spam.</p>
            </div>
        </div>
    """
    )


@app.post("/alerts", response_class=HTMLResponse)
async def create_alert(email: str = Form(...), keyword: str = Form(...)):
    # Save to DB
    store = AsyncStore(settings.db_path)
    await store.connect()

    # Simple insert
    async with store.connection() as conn:
        await conn.execute(
            "INSERT INTO alerts (email, keyword, created_at) VALUES (?, ?, ?)",
            (email, keyword, datetime.now().isoformat()),
        )
        await conn.commit()

    await store.close()

    return HTML_BS.format(
        content=f"""
        <div class="text-center">
            <h1 class="text-2xl font-bold text-green-600 mb-4">Subscribed!</h1>
            <p>You'll get an email when I spot "<strong>{keyword}</strong>" in a pain cluster.</p>
            <div class="mt-8">
                <a href="/" class="text-indigo-600 hover:text-indigo-900">Back to Archive</a>
            </div>
        </div>
    """
    )


@app.get("/archive/latest", response_class=HTMLResponse)
async def read_latest_archive():
    # Fetch clusters from DB (requires get_clusters method or raw query)
    store = AsyncStore(settings.db_path)
    await store.connect()

    # Get clusters from last 7 days
    async with store.connection() as conn:
        cursor = await conn.execute("SELECT * FROM clusters ORDER BY created_at DESC LIMIT 10")
        rows = await cursor.fetchall()

    await store.close()

    if not rows:
        return HTML_BS.format(content="<p class='text-center'>No reports found yet.</p>")

    # Render minimalist report
    clusters_html = ""
    for row in rows:
        clusters_html += f"""
        <div class="mb-12">
            <h2 class="text-2xl font-bold text-gray-900 mb-2">{row['title']}</h2>
            <p class="text-lg text-gray-700 mb-4">{row['summary']}</p>
            <div class="bg-yellow-50 border-l-4 border-yellow-400 p-4 mb-4">
                <p class="text-sm text-yellow-700"><strong>Why it matters:</strong> {row['why_it_matters']}</p>
                <p class="text-sm text-yellow-700 mt-1"><strong>Target:</strong> {row['target_audience']}</p>
            </div>
        </div>
        <hr class="my-8 border-gray-200">
        """

    return HTML_BS.format(
        content=f"""
        <div class="prose prose-indigo mx-auto">
            <h1 class="text-3xl font-bold mb-8">Latest Pain Clusters ({rows[0]['week_start']})</h1>
            {clusters_html}
            <div class="mt-8 text-center bg-gray-100 p-6 rounded">
                <p class="font-medium">Want to know when these change? <a href="/" class="text-indigo-600">Get alerts</a>.</p>
            </div>
        </div>
    """
    )
