"""
Memory API routes.
"""

import logging

from flask import jsonify, request

from utils.helpers import error_response, success_response

logger = logging.getLogger(__name__)

memory_service = None
OLLAMA_BASE_URL = "http://localhost:11434"


def init_memory_service(ollama_url):
    """Initialize the shared memory service."""
    global memory_service, OLLAMA_BASE_URL
    OLLAMA_BASE_URL = ollama_url
    try:
        from memory_service import get_memory_service

        memory_service = get_memory_service(ollama_url)
        logger.info("memory service initialized")
    except Exception as e:
        logger.warning(f"memory service init failed: {e}")


def _require_service():
    if memory_service is None:
        return jsonify(error_response("memory service not initialized", 503)), 503
    return None


def register_memory_routes(app):
    """Register memory routes."""

    @app.route("/api/memory", methods=["GET"])
    @app.route("/api/memory/list", methods=["GET"])
    def list_memories():
        missing = _require_service()
        if missing:
            return missing

        try:
            category = request.args.get("category")
            memories = memory_service.list_memories(category)
            return jsonify(
                success_response(
                    data=[memory.to_dict() for memory in memories],
                    message="memory list loaded",
                )
            )
        except Exception as e:
            logger.error(f"list memories failed: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route("/api/memory", methods=["POST"])
    def add_memory():
        missing = _require_service()
        if missing:
            return missing

        try:
            data = request.json or {}
            content = str(data.get("content", "")).strip()
            category = str(data.get("category", "general")).strip() or "general"
            tags = data.get("tags")
            metadata = data.get("metadata")
            importance = int(data.get("importance", 5))

            if not content:
                return jsonify(error_response("content must not be empty", 400)), 400

            if tags is None and isinstance(metadata, dict):
                tags = [f"{k}:{v}" for k, v in metadata.items()]
            if not isinstance(tags, list):
                tags = []

            memory = memory_service.add_memory(
                content=content,
                category=category,
                tags=tags,
                importance=importance,
            )
            return jsonify(success_response(data=memory.to_dict(), message="memory created")), 201
        except Exception as e:
            logger.error(f"add memory failed: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route("/api/memory/<memory_id>", methods=["GET"])
    def get_memory(memory_id):
        missing = _require_service()
        if missing:
            return missing

        try:
            memory = memory_service.get_memory(memory_id)
            if memory is None:
                return jsonify(error_response("memory not found", 404)), 404
            return jsonify(success_response(data=memory.to_dict()))
        except Exception as e:
            logger.error(f"get memory failed: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route("/api/memory/<memory_id>", methods=["PUT"])
    def update_memory(memory_id):
        missing = _require_service()
        if missing:
            return missing

        try:
            data = request.json or {}
            updates = {}
            for field in ("content", "category", "tags", "importance"):
                if field in data:
                    updates[field] = data[field]

            memory = memory_service.update_memory(memory_id, **updates)
            if memory is None:
                return jsonify(error_response("memory not found", 404)), 404
            return jsonify(success_response(data=memory.to_dict(), message="memory updated"))
        except Exception as e:
            logger.error(f"update memory failed: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route("/api/memory/<memory_id>", methods=["DELETE"])
    @app.route("/api/memory/<memory_id>/delete", methods=["POST"])
    def delete_memory(memory_id):
        missing = _require_service()
        if missing:
            return missing

        try:
            deleted = memory_service.delete_memory(memory_id)
            if not deleted:
                return jsonify(error_response("memory not found", 404)), 404
            return jsonify(success_response(data={"id": memory_id}, message="memory deleted"))
        except Exception as e:
            logger.error(f"delete memory failed: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route("/api/memory/search", methods=["GET", "POST"])
    @app.route("/api/memory/related", methods=["GET", "POST"])
    def search_memories():
        missing = _require_service()
        if missing:
            return missing

        try:
            data = request.json or {} if request.is_json else {}
            query = (
                data.get("query")
                or data.get("q")
                or request.args.get("query")
                or request.args.get("q")
                or ""
            ).strip()
            top_k = int(data.get("top_k") or request.args.get("top_k") or 5)
            min_similarity = float(data.get("min_similarity") or request.args.get("min_similarity") or 0.4)

            if not query:
                return jsonify(error_response("query must not be empty", 400)), 400

            memories = memory_service.search_memories(query, top_k=top_k, min_similarity=min_similarity)
            return jsonify(
                success_response(
                    data=[memory.to_dict() for memory in memories],
                    message="memory search completed",
                )
            )
        except Exception as e:
            logger.error(f"search memories failed: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route("/api/memory/clear", methods=["POST"])
    def clear_memories():
        missing = _require_service()
        if missing:
            return missing

        try:
            memory_service.clear_all()
            return jsonify(success_response(message="all memories cleared"))
        except Exception as e:
            logger.error(f"clear memories failed: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route("/api/memory/stats", methods=["GET"])
    def memory_stats():
        missing = _require_service()
        if missing:
            return missing

        try:
            return jsonify(success_response(data=memory_service.get_statistics()))
        except Exception as e:
            logger.error(f"memory stats failed: {e}")
            return jsonify(error_response(str(e), 500)), 500
