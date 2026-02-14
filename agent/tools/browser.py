# agent/tools/browser.py
import webbrowser
import logging
import httpx

logger = logging.getLogger(__name__)


def open_url(url: str) -> str:
    """Open a URL in the default browser.

    Args:
        url: The URL to open

    Returns:
        Status message in Russian
    """
    try:
        webbrowser.open(url)
        return f"Открываю {url}"
    except Exception as e:
        logger.error(f"Failed to open URL {url}: {e}")
        return f"Ошибка при открытии URL: {e}"


def search_vk_video(query: str, vk_token: str, channel_id: int | None = None) -> str:
    """Search for a video on VK and open the most popular result.

    Args:
        query: Search query
        vk_token: VK API access token
        channel_id: Optional channel/group ID to search within

    Returns:
        Status message in Russian
    """
    params = {
        "q": query,
        "access_token": vk_token,
        "v": "5.199",
        "count": 10,
        "sort": 2,  # Sort by relevance
    }
    if channel_id:
        params["owner_id"] = channel_id

    try:
        with httpx.Client() as client:
            resp = client.get(
                "https://api.vk.com/method/video.search",
                params=params,
                timeout=5.0,
            )
            resp.raise_for_status()
            data = resp.json()

        items = data.get("response", {}).get("items", [])
        if not items:
            return f"Не нашла видео по запросу «{query}»"

        # Select video with most views
        best = max(items, key=lambda v: v.get("views", 0))
        url = f"https://vk.com/video{best['owner_id']}_{best['id']}"
        webbrowser.open(url)
        return f"Включаю «{best.get('title', query)}»: {url}"
    except Exception as e:
        logger.error(f"Failed to search VK video for '{query}': {e}")
        return f"Ошибка поиска видео: {e}"
