from __future__ import annotations

import json
import logging
import sqlite3
import time
import threading
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

_DB_DIR = Path(__file__).resolve().parent.parent / "data" / "selss"
_DB_PATH = _DB_DIR / "skill_registry.db"


class FunctionCategory(str, Enum):
    TIME = "time"
    UTILITY = "utility"


class SkillTier(str, Enum):
    ATOMIC = "atomic"
    LOGIC = "logic"
    WORKFLOW = "workflow"


@dataclass
class FunctionParameter:
    name: str
    type: str
    description: str
    required: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "type": self.type, "description": self.description, "required": self.required}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "FunctionParameter":
        return cls(name=d["name"], type=d["type"], description=d.get("description", ""), required=d.get("required", False))


@dataclass
class FunctionDefinition:
    name: str
    description: str
    category: FunctionCategory
    parameters: List[FunctionParameter]
    handler: Callable[..., Dict[str, Any]]
    require_confirmation: bool = False


@dataclass
class SkillDefinition:
    name: str
    description: str
    category: FunctionCategory = FunctionCategory.UTILITY
    parameters: List[FunctionParameter] = field(default_factory=list)
    handler: Optional[Callable[..., Dict[str, Any]]] = None
    require_confirmation: bool = False
    tier: SkillTier = SkillTier.ATOMIC
    usage_example: str = ""
    pseudo_code: str = ""
    vitality: float = 0.5
    confidence: float = 1.0
    call_count: int = 0
    success_count: int = 0
    last_used_at: float = 0.0
    created_at: float = field(default_factory=time.time)
    is_beta: bool = False
    alias_for: Optional[str] = None
    embedding: Optional[bytes] = None

    def to_storage_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "tier": self.tier.value,
            "parameters": json.dumps([p.to_dict() for p in self.parameters], ensure_ascii=False),
            "usage_example": self.usage_example,
            "pseudo_code": self.pseudo_code,
            "vitality": self.vitality,
            "confidence": self.confidence,
            "call_count": self.call_count,
            "success_count": self.success_count,
            "last_used_at": self.last_used_at,
            "created_at": self.created_at,
            "is_beta": 1 if self.is_beta else 0,
            "alias_for": self.alias_for,
            "require_confirmation": 1 if self.require_confirmation else 0,
        }

    @classmethod
    def from_storage_row(cls, row: sqlite3.Row) -> "SkillDefinition":
        params_raw = row["parameters"] or "[]"
        params = [FunctionParameter.from_dict(p) for p in json.loads(params_raw)]
        return cls(
            name=row["name"],
            description=row["description"],
            category=FunctionCategory(row["category"]) if row["category"] else FunctionCategory.UTILITY,
            parameters=params,
            tier=SkillTier(row["tier"]) if row["tier"] else SkillTier.ATOMIC,
            usage_example=row["usage_example"] or "",
            pseudo_code=row["pseudo_code"] or "",
            vitality=row["vitality"] if row["vitality"] is not None else 0.5,
            confidence=row["confidence"] if row["confidence"] is not None else 1.0,
            call_count=row["call_count"] or 0,
            success_count=row["success_count"] or 0,
            last_used_at=row["last_used_at"] or 0.0,
            created_at=row["created_at"] or time.time(),
            is_beta=bool(row["is_beta"]),
            alias_for=row["alias_for"],
            require_confirmation=bool(row["require_confirmation"]),
        )

    def to_api_dict(self, include_details: bool = False) -> Dict[str, Any]:
        base = {
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "tier": self.tier.value,
            "vitality": round(self.vitality, 3),
            "confidence": round(self.confidence, 3),
            "call_count": self.call_count,
            "success_count": self.success_count,
            "is_beta": self.is_beta,
        }
        if include_details:
            base.update({
                "parameters": [p.to_dict() for p in self.parameters],
                "usage_example": self.usage_example,
                "pseudo_code": self.pseudo_code,
                "require_confirmation": self.require_confirmation,
                "alias_for": self.alias_for,
            })
        return base

    def success_rate(self) -> float:
        if self.call_count == 0:
            return 1.0
        return self.success_count / self.call_count


class FunctionRegistry:
    def __init__(self):
        self._registry: Dict[str, FunctionDefinition] = {}
        self._history: List[Dict[str, Any]] = []

    def register(self, func: FunctionDefinition) -> None:
        self._registry[func.name] = func

    def get(self, name: str) -> Optional[FunctionDefinition]:
        return self._registry.get(name)

    def list_all(self, enabled_only: bool = True) -> List[Dict[str, Any]]:
        return [
            {
                "name": f.name,
                "description": f.description,
                "category": f.category.value,
                "parameters": [p.__dict__ for p in f.parameters],
                "require_confirmation": f.require_confirmation,
            }
            for f in self._registry.values()
        ]

    def execute(self, name: str, arguments: Dict[str, Any], require_confirmation: bool = False) -> Dict[str, Any]:
        func = self.get(name)
        if not func:
            return {"success": False, "message": "function not found", "code": 404, "data": None}

        if func.require_confirmation and not require_confirmation:
            return {
                "success": False,
                "message": "confirmation required",
                "code": 403,
                "data": {"function": name, "description": func.description, "require_confirmation": True},
            }

        try:
            result = func.handler(**(arguments or {}))
            if not isinstance(result, dict):
                result = {"value": result}
            payload = {"success": True, "message": "ok", "code": 200, "data": result}
        except Exception as e:
            payload = {"success": False, "message": str(e), "code": 500, "data": None}

        self._history.append({
            "function": name,
            "arguments": arguments or {},
            "result": payload,
            "timestamp": datetime.now().isoformat(),
        })
        return payload

    def get_execution_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self._history[-limit:]


class _SkillDB:
    _SCHEMA = """
    CREATE TABLE IF NOT EXISTS skills (
        name TEXT PRIMARY KEY,
        description TEXT NOT NULL,
        category TEXT DEFAULT 'utility',
        tier TEXT DEFAULT 'atomic',
        parameters TEXT DEFAULT '[]',
        usage_example TEXT DEFAULT '',
        pseudo_code TEXT DEFAULT '',
        vitality REAL DEFAULT 0.5,
        confidence REAL DEFAULT 1.0,
        call_count INTEGER DEFAULT 0,
        success_count INTEGER DEFAULT 0,
        last_used_at REAL DEFAULT 0,
        created_at REAL DEFAULT 0,
        updated_at REAL DEFAULT 0,
        is_beta INTEGER DEFAULT 0,
        alias_for TEXT DEFAULT NULL,
        require_confirmation INTEGER DEFAULT 0,
        embedding BLOB DEFAULT NULL
    );
    CREATE TABLE IF NOT EXISTS skill_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        skill_name TEXT NOT NULL,
        arguments TEXT DEFAULT '{}',
        result_code INTEGER DEFAULT 0,
        result_message TEXT DEFAULT '',
        timestamp REAL DEFAULT 0
    );
    CREATE INDEX IF NOT EXISTS idx_skill_tier ON skills(tier);
    CREATE INDEX IF NOT EXISTS idx_skill_vitality ON skills(vitality);
    CREATE INDEX IF NOT EXISTS idx_skill_history_name ON skill_history(skill_name);
    CREATE TABLE IF NOT EXISTS archived_skills (
        name TEXT PRIMARY KEY,
        description TEXT DEFAULT '',
        category TEXT DEFAULT 'utility',
        parameters TEXT DEFAULT '[]',
        tier TEXT DEFAULT 'atomic',
        usage_example TEXT DEFAULT '',
        pseudo_code TEXT DEFAULT '',
        vitality REAL DEFAULT 0.5,
        confidence REAL DEFAULT 1.0,
        call_count INTEGER DEFAULT 0,
        success_count INTEGER DEFAULT 0,
        last_used_at REAL DEFAULT 0,
        created_at REAL DEFAULT 0,
        is_beta INTEGER DEFAULT 0,
        alias_for TEXT DEFAULT NULL,
        require_confirmation INTEGER DEFAULT 0,
        embedding BLOB DEFAULT NULL,
        archived_at REAL DEFAULT 0
    );
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or _DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._lock:
            with self._connect() as conn:
                conn.executescript(self._SCHEMA)

    def upsert_skill(self, skill: SkillDefinition):
        with self._lock:
            d = skill.to_storage_dict()
            with self._connect() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO skills
                    (name, description, category, tier, parameters, usage_example, pseudo_code,
                     vitality, confidence, call_count, success_count, last_used_at, created_at,
                     updated_at, is_beta, alias_for, require_confirmation, embedding)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    d["name"], d["description"], d["category"], d["tier"],
                    d["parameters"], d["usage_example"], d["pseudo_code"],
                    d["vitality"], d["confidence"], d["call_count"], d["success_count"],
                    d["last_used_at"], d["created_at"], time.time(),
                    d["is_beta"], d["alias_for"], d["require_confirmation"],
                    skill.embedding,
                ))

    def get_skill(self, name: str) -> Optional[SkillDefinition]:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute("SELECT * FROM skills WHERE name = ?", (name,)).fetchone()
                if not row:
                    return None
                skill = SkillDefinition.from_storage_row(row)
                skill.embedding = row["embedding"]
                return skill

    def list_skills(self, tier: Optional[str] = None, include_beta: bool = True) -> List[SkillDefinition]:
        with self._lock:
            with self._connect() as conn:
                if tier:
                    rows = conn.execute("SELECT * FROM skills WHERE tier = ? ORDER BY vitality DESC", (tier,)).fetchall()
                elif not include_beta:
                    rows = conn.execute("SELECT * FROM skills WHERE is_beta = 0 ORDER BY vitality DESC").fetchall()
                else:
                    rows = conn.execute("SELECT * FROM skills ORDER BY vitality DESC").fetchall()
                return [SkillDefinition.from_storage_row(r) for r in rows]

    def delete_skill(self, name: str) -> bool:
        with self._lock:
            with self._connect() as conn:
                cursor = conn.execute("DELETE FROM skills WHERE name = ?", (name,))
                return cursor.rowcount > 0

    def update_stats(self, name: str, success: bool):
        with self._lock:
            with self._connect() as conn:
                conn.execute("""
                    UPDATE skills SET
                        call_count = call_count + 1,
                        success_count = success_count + ?,
                        last_used_at = ?
                    WHERE name = ?
                """, (1 if success else 0, time.time(), name))

    def update_vitality(self, name: str, vitality: float):
        with self._lock:
            with self._connect() as conn:
                conn.execute("UPDATE skills SET vitality = ? WHERE name = ?", (vitality, name))

    def update_embedding(self, name: str, embedding: bytes):
        with self._lock:
            with self._connect() as conn:
                conn.execute("UPDATE skills SET embedding = ? WHERE name = ?", (embedding, name))

    def record_history(self, skill_name: str, arguments: Dict, result_code: int, result_message: str):
        with self._lock:
            with self._connect() as conn:
                conn.execute("""
                    INSERT INTO skill_history (skill_name, arguments, result_code, result_message, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                """, (skill_name, json.dumps(arguments, ensure_ascii=False), result_code, result_message, time.time()))

    def get_history(self, skill_name: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            with self._connect() as conn:
                if skill_name:
                    rows = conn.execute(
                        "SELECT * FROM skill_history WHERE skill_name = ? ORDER BY timestamp DESC LIMIT ?",
                        (skill_name, limit)
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT * FROM skill_history ORDER BY timestamp DESC LIMIT ?", (limit,)
                    ).fetchall()
                return [dict(r) for r in rows]

    def get_all_embeddings(self) -> List[Tuple[str, Optional[bytes]]]:
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute("SELECT name, embedding FROM skills").fetchall()
                return [(r["name"], r["embedding"]) for r in rows]

    def count_skills(self, tier: Optional[str] = None) -> int:
        with self._lock:
            with self._connect() as conn:
                if tier:
                    return conn.execute("SELECT COUNT(*) FROM skills WHERE tier = ?", (tier,)).fetchone()[0]
                return conn.execute("SELECT COUNT(*) FROM skills").fetchone()[0]

    def archive_skill(self, name: str):
        with self._lock:
            with self._connect() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO archived_skills 
                    SELECT *, ? as archived_at FROM skills WHERE name = ?
                """, (time.time(), name))
                conn.execute("DELETE FROM skills WHERE name = ?", (name,))


class SkillRegistry:
    CAPACITY_THRESHOLD = 2000

    def __init__(self, db_path: Optional[Path] = None):
        self._memory_skills: Dict[str, SkillDefinition] = {}
        self._db = _SkillDB(db_path)
        self._lock = threading.RLock()
        self._load_from_db()

    def _load_from_db(self):
        for skill in self._db.list_skills(include_beta=True):
            self._memory_skills[skill.name] = skill
        logger.info(f"[SkillRegistry] 从数据库加载 {len(self._memory_skills)} 个技能")

    def register_skill(self, skill: SkillDefinition, persist: bool = True) -> None:
        with self._lock:
            self._memory_skills[skill.name] = skill
            if persist:
                self._db.upsert_skill(skill)
            logger.info(f"[SkillRegistry] 注册技能: {skill.name} (tier={skill.tier.value})")

    def register_atomic_from_function(self, func: FunctionDefinition) -> SkillDefinition:
        skill = SkillDefinition(
            name=func.name,
            description=func.description,
            category=func.category,
            parameters=func.parameters,
            handler=func.handler,
            require_confirmation=func.require_confirmation,
            tier=SkillTier.ATOMIC,
            confidence=1.0,
            vitality=0.5,
        )
        self.register_skill(skill)
        return skill

    def get_skill(self, name: str) -> Optional[SkillDefinition]:
        with self._lock:
            skill = self._memory_skills.get(name)
            if skill:
                return skill
            skill = self._db.get_skill(name)
            if skill:
                self._memory_skills[name] = skill
            return skill

    def delete_skill(self, name: str) -> bool:
        with self._lock:
            self._memory_skills.pop(name, None)
            return self._db.delete_skill(name)

    def list_skills(self, tier: Optional[str] = None, include_beta: bool = True) -> List[SkillDefinition]:
        with self._lock:
            skills = list(self._memory_skills.values())
            if tier:
                skills = [s for s in skills if s.tier.value == tier]
            if not include_beta:
                skills = [s for s in skills if not s.is_beta]
            return sorted(skills, key=lambda s: s.vitality, reverse=True)

    def list_skills_api(self, include_details: bool = False) -> List[Dict[str, Any]]:
        return [s.to_api_dict(include_details=include_details) for s in self.list_skills()]

    def execute_skill(self, name: str, arguments: Dict[str, Any], require_confirmation: bool = False) -> Dict[str, Any]:
        skill = self.get_skill(name)
        if not skill:
            return {"success": False, "message": f"skill '{name}' not found", "code": 404, "data": None}

        if skill.alias_for:
            target = self.get_skill(skill.alias_for)
            if target:
                return self.execute_skill(skill.alias_for, arguments, require_confirmation)

        if skill.require_confirmation and not require_confirmation:
            return {
                "success": False,
                "message": "confirmation required",
                "code": 403,
                "data": {"skill": name, "description": skill.description, "require_confirmation": True},
            }

        if not skill.handler:
            if skill.pseudo_code:
                return {"success": False, "message": "composite skill requires execution engine", "code": 501, "data": None}
            return {"success": False, "message": "skill has no handler", "code": 500, "data": None}

        try:
            result = skill.handler(**(arguments or {}))
            if not isinstance(result, dict):
                result = {"value": result}
            payload = {"success": True, "message": "ok", "code": 200, "data": result}
            self._update_stats(name, True)
        except Exception as e:
            payload = {"success": False, "message": str(e), "code": 500, "data": None}
            self._update_stats(name, False)

        self._db.record_history(name, arguments, payload["code"], payload.get("message", ""))
        return payload

    def _update_stats(self, name: str, success: bool):
        with self._lock:
            skill = self._memory_skills.get(name)
            if skill:
                skill.call_count += 1
                if success:
                    skill.success_count += 1
                skill.last_used_at = time.time()
            self._db.update_stats(name, success)

    def update_vitality(self, name: str, vitality: float):
        with self._lock:
            skill = self._memory_skills.get(name)
            if skill:
                skill.vitality = vitality
            self._db.update_vitality(name, vitality)

    def update_embedding(self, name: str, embedding: bytes):
        with self._lock:
            skill = self._memory_skills.get(name)
            if skill:
                skill.embedding = embedding
            self._db.update_embedding(name, embedding)

    def get_history(self, skill_name: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        return self._db.get_history(skill_name, limit)

    def count_skills(self, tier: Optional[str] = None) -> int:
        return self._db.count_skills(tier)

    def get_skills_by_tier(self, tier: SkillTier, include_beta: bool = True) -> List[SkillDefinition]:
        return self.list_skills(tier=tier.value, include_beta=include_beta)

    def search_by_description(self, query: str, limit: int = 10) -> List[SkillDefinition]:
        query_lower = query.lower()
        scored = []
        for skill in self._memory_skills.values():
            desc_lower = skill.description.lower()
            name_lower = skill.name.lower()
            score = 0.0
            if query_lower in name_lower:
                score += 0.5
            if query_lower in desc_lower:
                score += 0.3
            for kw in query_lower.split():
                if kw in desc_lower:
                    score += 0.1
            if score > 0:
                scored.append((skill, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [s for s, _ in scored[:limit]]

    def save_skill(self, skill: SkillDefinition):
        self._memory_skills[skill.name] = skill
        self._db.upsert_skill(skill)

    def archive_skill(self, name: str) -> bool:
        skill = self.get_skill(name)
        if not skill:
            return False
        self._db.archive_skill(name)
        if name in self._memory_skills:
            del self._memory_skills[name]
        return True

    def get_skill_by_name(self, name: str) -> Optional[SkillDefinition]:
        return self.get_skill(name)


class DateTimeFunctions:
    @staticmethod
    def get_current_time(format_type: str = "datetime") -> Dict[str, Any]:
        now = datetime.now()
        if format_type == "date":
            value = now.strftime("%Y-%m-%d")
        elif format_type == "time":
            value = now.strftime("%H:%M:%S")
        elif format_type == "timestamp":
            value = int(now.timestamp())
        else:
            value = now.strftime("%Y-%m-%d %H:%M:%S")
        return {"value": value}


class UtilityFunctions:
    @staticmethod
    def calculate(expression: str) -> Dict[str, Any]:
        import ast

        if not expression or not isinstance(expression, str):
            return {"error": "invalid expression"}

        expression = expression.strip()
        if not expression:
            return {"error": "empty expression"}

        allowed_chars = set("0123456789+-*/(). ")
        if not all(c in allowed_chars for c in expression):
            return {"error": "invalid characters in expression"}

        try:
            tree = ast.parse(expression, mode='eval')

            def safe_eval(node):
                if isinstance(node, ast.Constant):
                    if isinstance(node.value, (int, float)):
                        return node.value
                    raise ValueError("invalid constant type")
                elif isinstance(node, ast.BinOp):
                    left = safe_eval(node.left)
                    right = safe_eval(node.right)
                    if isinstance(node.op, ast.Add):
                        return left + right
                    elif isinstance(node.op, ast.Sub):
                        return left - right
                    elif isinstance(node.op, ast.Mult):
                        return left * right
                    elif isinstance(node.op, ast.Div):
                        if right == 0:
                            raise ValueError("division by zero")
                        return left / right
                    else:
                        raise ValueError("unsupported operator")
                elif isinstance(node, ast.UnaryOp):
                    operand = safe_eval(node.operand)
                    if isinstance(node.op, ast.USub):
                        return -operand
                    elif isinstance(node.op, ast.UAdd):
                        return operand
                    else:
                        raise ValueError("unsupported unary operator")
                elif isinstance(node, ast.Expression):
                    return safe_eval(node.body)
                else:
                    raise ValueError(f"unsupported node type: {type(node).__name__}")

            result = safe_eval(tree)
            return {"result": result}
        except SyntaxError:
            return {"error": "invalid expression syntax"}
        except ValueError as e:
            return {"error": str(e)}
        except Exception as e:
            return {"error": f"calculation error: {str(e)}"}


function_registry = FunctionRegistry()
skill_registry = SkillRegistry()


def create_function_registry() -> FunctionRegistry:
    registry = FunctionRegistry()

    registry.register(FunctionDefinition(
        name="get_current_time",
        description="Get current time",
        category=FunctionCategory.TIME,
        parameters=[FunctionParameter("format_type", "string", "datetime|date|time|timestamp", required=False)],
        handler=DateTimeFunctions.get_current_time,
    ))

    registry.register(FunctionDefinition(
        name="calculate",
        description="Evaluate a math expression",
        category=FunctionCategory.UTILITY,
        parameters=[FunctionParameter("expression", "string", "Math expression", required=True)],
        handler=UtilityFunctions.calculate,
    ))

    return registry


def _init_skill_registry():
    fr = create_function_registry()
    for func_def in fr._registry.values():
        skill_registry.register_atomic_from_function(func_def)


function_registry = create_function_registry()
_init_skill_registry()


def list_functions(enabled_only: bool = True) -> List[Dict[str, Any]]:
    return function_registry.list_all(enabled_only)


def execute_function(name: str, arguments: Dict[str, Any], require_confirmation: bool = False) -> Dict[str, Any]:
    return function_registry.execute(name, arguments, require_confirmation)


def get_execution_history(limit: int = 50) -> List[Dict[str, Any]]:
    return function_registry.get_execution_history(limit)


def list_skills(tier: Optional[str] = None, include_beta: bool = True, include_details: bool = False) -> List[Dict[str, Any]]:
    if tier:
        return [
            s.to_api_dict(include_details=include_details)
            for s in skill_registry.get_skills_by_tier(SkillTier(tier), include_beta=include_beta)
        ]
    return skill_registry.list_skills_api(include_details=include_details)


def execute_skill(name: str, arguments: Dict[str, Any], require_confirmation: bool = False) -> Dict[str, Any]:
    return skill_registry.execute_skill(name, arguments, require_confirmation)


def register_skill(skill: SkillDefinition) -> None:
    skill_registry.register_skill(skill)


def get_skill(name: str) -> Optional[SkillDefinition]:
    return skill_registry.get_skill(name)
