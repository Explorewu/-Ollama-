"""
Search API routes.
"""

import logging

from flask import jsonify, request

from utils.auth import require_api_key
from utils.helpers import error_response, success_response

logger = logging.getLogger(__name__)


def _service():
    from web_search_service import SecureSearchService

    return SecureSearchService()


def register_search_routes(app):
    """Register search routes."""

    @app.route("/api/search/web", methods=["POST"])
    @require_api_key
    def web_search_api():
        try:
            data = request.json or {}
            query = str(data.get("query", "")).strip()
            max_results = int(data.get("max_results", 10))

            if not query:
                return jsonify(error_response("query is required", 400)), 400

            result = _service().search(query, max_results)
            if not result.get("success"):
                code = int(result.get("code", 400))
                return jsonify(error_response(result.get("message", "search failed"), code)), code

            return jsonify(success_response(data=result.get("data"), message=result.get("message", "search completed")))
        except Exception as e:
            logger.error(f"web search failed: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route("/api/search/instant", methods=["POST"])
    @require_api_key
    def instant_answer_api():
        try:
            data = request.json or {}
            question = str(data.get("question") or data.get("query") or "").strip()

            if not question:
                return jsonify(error_response("question is required", 400)), 400

            result = _service().get_instant_answer(question)
            if not result.get("success"):
                code = int(result.get("code", 400))
                return jsonify(error_response(result.get("message", "instant answer failed"), code)), code

            return jsonify(
                success_response(
                    data=result.get("data"),
                    message=result.get("message", "instant answer completed"),
                )
            )
        except Exception as e:
            logger.error(f"instant answer failed: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route("/api/search/news", methods=["POST"])
    @require_api_key
    def news_search_api():
        try:
            data = request.json or {}
            query = str(data.get("query", "")).strip()
            max_results = int(data.get("max_results", 5))

            if not query:
                return jsonify(error_response("query is required", 400)), 400

            result = _service().search_news(query, max_results)
            if not result.get("success"):
                code = int(result.get("code", 400))
                return jsonify(error_response(result.get("message", "news search failed"), code)), code

            return jsonify(success_response(data=result.get("data"), message=result.get("message", "news search completed")))
        except Exception as e:
            logger.error(f"news search failed: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route("/api/search/clear-cache", methods=["POST"])
    @require_api_key
    def clear_search_cache_api():
        try:
            older_than_hours = request.args.get("older_than_hours", 24, type=int)
            result = _service().clear_cache(older_than_hours)
            return jsonify(success_response(data=result.get("data"), message=result.get("message", "cache cleared")))
        except Exception as e:
            logger.error(f"clear search cache failed: {e}")
            return jsonify(error_response(str(e), 500)), 500
