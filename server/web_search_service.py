"""
Lightweight web search service.
"""

from __future__ import annotations

import html
import logging
import re
import time
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)

try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    requests = None
    REQUESTS_AVAILABLE = False
    logger.warning("requests not available")


def _response(success: bool, message: str, data: Optional[Dict[str, Any]] = None, code: int = 200) -> Dict[str, Any]:
    return {
        "success": success,
        "message": message,
        "code": code,
        "data": data or {},
    }


class WebSearchService:
    """Small DDG-backed search wrapper with in-memory caching."""

    def __init__(self, cache_ttl_seconds: int = 900):
        self.cache_ttl_seconds = cache_ttl_seconds
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._session = requests.Session() if REQUESTS_AVAILABLE else None
        self._headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/123.0 Safari/537.36"
        }

    def search(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        query = (query or "").strip()
        if not query:
            return _response(False, "query is required", code=400)

        cache_key = f"search:{query}:{max_results}"
        cached = self._get_cache(cache_key)
        if cached is not None:
            return _response(True, "search completed", cached)

        results = self._duckduckgo_html_search(query, max_results=max_results)
        data = {"query": query, "results": results, "count": len(results)}
        self._set_cache(cache_key, data)
        return _response(True, "search completed", data)

    def search_news(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        query = (query or "").strip()
        if not query:
            return _response(False, "query is required", code=400)

        cache_key = f"news:{query}:{max_results}"
        cached = self._get_cache(cache_key)
        if cached is not None:
            return _response(True, "news search completed", cached)

        results = self._duckduckgo_html_search(f"{query} news", max_results=max_results)
        data = {"query": query, "results": results, "count": len(results)}
        self._set_cache(cache_key, data)
        return _response(True, "news search completed", data)

    def get_instant_answer(self, question: str) -> Dict[str, Any]:
        question = (question or "").strip()
        if not question:
            return _response(False, "question is required", code=400)

        cache_key = f"instant:{question}"
        cached = self._get_cache(cache_key)
        if cached is not None:
            return _response(True, "instant answer completed", cached)

        answer = ""
        abstract_url = ""
        related: List[Dict[str, str]] = []

        if REQUESTS_AVAILABLE:
            try:
                response = self._session.get(
                    "https://api.duckduckgo.com/",
                    params={"q": question, "format": "json", "no_html": 1, "no_redirect": 1},
                    headers=self._headers,
                    timeout=12,
                )
                response.raise_for_status()
                payload = response.json()
                answer = (
                    payload.get("Answer")
                    or payload.get("AbstractText")
                    or payload.get("Definition")
                    or ""
                ).strip()
                abstract_url = payload.get("AbstractURL", "")
                for item in payload.get("RelatedTopics", [])[:5]:
                    if isinstance(item, dict) and item.get("Text"):
                        related.append({
                            "text": item.get("Text", ""),
                            "url": item.get("FirstURL", ""),
                        })
            except Exception as e:
                logger.warning(f"instant answer lookup failed: {e}")

        if not answer:
            search_result = self.search(question, max_results=3)
            search_data = search_result.get("data") or {}
            results = search_data.get("results") or []
            if results:
                answer = results[0].get("snippet", "")
                related = [{"text": item.get("title", ""), "url": item.get("url", "")} for item in results[:3]]

        data = {
            "question": question,
            "answer": answer,
            "source_url": abstract_url,
            "related": related,
        }
        self._set_cache(cache_key, data)
        return _response(True, "instant answer completed", data)

    def clear_cache(self, older_than_hours: int = 24) -> Dict[str, Any]:
        threshold = time.time() - max(0, older_than_hours) * 3600
        removed = 0
        for key in list(self._cache.keys()):
            if self._cache[key]["timestamp"] < threshold:
                removed += 1
                del self._cache[key]
        return _response(True, "cache cleared", {"removed": removed, "remaining": len(self._cache)})

    def _duckduckgo_html_search(self, query: str, max_results: int) -> List[Dict[str, str]]:
        if not REQUESTS_AVAILABLE:
            return []

        try:
            response = self._session.get(
                f"https://html.duckduckgo.com/html/?q={quote_plus(query)}",
                headers=self._headers,
                timeout=12,
            )
            response.raise_for_status()
            return self._parse_results(response.text, max_results)
        except Exception as e:
            logger.warning(f"web search failed: {e}")
            return []

    def _parse_results(self, html_text: str, max_results: int) -> List[Dict[str, str]]:
        pattern = re.compile(
            r'<a[^>]*class="result__a"[^>]*href="(?P<url>[^"]+)"[^>]*>(?P<title>.*?)</a>.*?'
            r'<a[^>]*class="result__snippet"[^>]*>(?P<snippet>.*?)</a>',
            re.S,
        )
        results: List[Dict[str, str]] = []

        for match in pattern.finditer(html_text):
            title = self._clean_html(match.group("title"))
            snippet = self._clean_html(match.group("snippet"))
            url = html.unescape(match.group("url"))
            results.append({"title": title, "snippet": snippet, "url": url})
            if len(results) >= max_results:
                break

        if results:
            return results

        fallback_pattern = re.compile(
            r'<a[^>]*class="result-link"[^>]*href="(?P<url>[^"]+)"[^>]*>(?P<title>.*?)</a>',
            re.S,
        )
        for match in fallback_pattern.finditer(html_text):
            results.append({
                "title": self._clean_html(match.group("title")),
                "snippet": "",
                "url": html.unescape(match.group("url")),
            })
            if len(results) >= max_results:
                break
        return results

    def _clean_html(self, value: str) -> str:
        cleaned = re.sub(r"<[^>]+>", " ", value or "")
        return " ".join(html.unescape(cleaned).split())

    def _get_cache(self, key: str) -> Optional[Dict[str, Any]]:
        entry = self._cache.get(key)
        if not entry:
            return None
        if time.time() - entry["timestamp"] > self.cache_ttl_seconds:
            del self._cache[key]
            return None
        return entry["data"]

    def _set_cache(self, key: str, data: Dict[str, Any]) -> None:
        self._cache[key] = {"timestamp": time.time(), "data": data}


class SecureSearchService(WebSearchService):
    """Compatibility alias for older imports."""

    pass
