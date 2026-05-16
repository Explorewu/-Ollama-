"""
函数调用 & 技能管理 API 模块

提供函数调用和技能管理相关接口
"""

import logging
from flask import request, jsonify

from utils.auth import require_api_key
from utils.helpers import success_response, error_response

logger = logging.getLogger(__name__)

function_registry = None


def init_functions_service():
    global function_registry
    try:
        from function_engine import create_function_registry
        function_registry = create_function_registry()
        logger.info("函数调用服务初始化成功")
    except Exception as e:
        logger.warning(f"函数调用服务初始化失败: {e}")


def register_functions_routes(app):

    @app.route('/api/functions/list', methods=['GET'])
    def list_functions_api():
        try:
            from function_engine import list_functions
            functions = list_functions(enabled_only=True)
            return jsonify(success_response(data={
                'functions': functions,
                'count': len(functions)
            }))
        except Exception as e:
            logger.error(f"获取函数列表失败: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route('/api/functions/execute', methods=['POST'])
    @require_api_key
    def execute_function_api():
        try:
            data = request.json or {}
            function_name = data.get('function', '')
            arguments = data.get('arguments', {})
            if not function_name:
                return jsonify(error_response("缺少 function 参数", 400)), 400

            from function_engine import execute_function, function_registry
            func_def = function_registry.get(function_name)
            require_confirmation = data.get('require_confirmation', False)

            if func_def and func_def.require_confirmation and not require_confirmation:
                return jsonify(error_response(
                    message=f'函数 "{function_name}" 需要用户确认才能执行',
                    code=403,
                    data={'require_confirmation': True, 'function': function_name, 'description': func_def.description}
                )), 403

            result = execute_function(function_name, arguments)
            if result.get('success'):
                return jsonify(success_response(data=result.get('data'), message=result.get('message', '函数执行成功')))
            else:
                return jsonify(error_response(
                    message=result.get('message', result.get('error', '函数执行失败')),
                    code=result.get('code', 500)
                )), result.get('code', 500)
        except Exception as e:
            logger.error(f"函数执行失败: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route('/api/functions/history', methods=['GET'])
    @require_api_key
    def function_history_api():
        try:
            from function_engine import get_execution_history
            limit = request.args.get('limit', 50, type=int)
            history = get_execution_history(limit)
            return jsonify(success_response(data={'history': history, 'count': len(history)}))
        except Exception as e:
            logger.error(f"获取历史失败: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route('/api/assistant/computer', methods=['POST'])
    def computer_assist():
        try:
            data = request.get_json() or {}
            instruction = data.get('instruction', '')
            safe_mode = data.get('safe_mode', True)
            return jsonify(success_response(data={
                "message": "电脑协助功能暂未启用",
                "instruction": instruction,
                "safe_mode": safe_mode,
                "control_session": None,
                "operation_ticket": [],
                "steps": []
            }, message="电脑协助功能需要额外配置才能使用"))
        except Exception as e:
            logger.error(f"电脑协助请求失败: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route('/api/assistant/computer/execute', methods=['POST'])
    def computer_assist_execute():
        try:
            data = request.get_json() or {}
            session_id = data.get('session_id', '')
            return jsonify(success_response(data={
                "message": "电脑协助执行功能暂未启用",
                "session_id": session_id,
                "executed": False
            }, message="电脑协助功能需要额外配置才能使用"))
        except Exception as e:
            logger.error(f"电脑协助执行失败: {e}")
            return jsonify(error_response(str(e), 500)), 500

    # ─── 技能管理 API ───

    @app.route('/api/skills/list', methods=['GET'])
    def list_skills_api():
        try:
            from function_engine import list_skills, skill_registry
            tier = request.args.get('tier', None)
            include_details = request.args.get('details', 'false').lower() == 'true'
            include_beta = request.args.get('beta', 'true').lower() == 'true'
            skills = list_skills(tier=tier, include_beta=include_beta, include_details=include_details)
            stats = {
                'total': skill_registry.count_skills(),
                'atomic': skill_registry.count_skills('atomic'),
                'logic': skill_registry.count_skills('logic'),
                'workflow': skill_registry.count_skills('workflow'),
            }
            return jsonify(success_response(data={'skills': skills, 'count': len(skills), 'stats': stats}))
        except Exception as e:
            logger.error(f"获取技能列表失败: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route('/api/skills/get/<skill_name>', methods=['GET'])
    def get_skill_api(skill_name):
        try:
            from function_engine import get_skill
            skill = get_skill(skill_name)
            if not skill:
                return jsonify(error_response(f"技能 '{skill_name}' 不存在", 404)), 404
            return jsonify(success_response(data=skill.to_api_dict(include_details=True)))
        except Exception as e:
            logger.error(f"获取技能详情失败: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route('/api/skills/execute', methods=['POST'])
    @require_api_key
    def execute_skill_api():
        try:
            data = request.json or {}
            skill_name = data.get('skill', data.get('function', ''))
            arguments = data.get('arguments', {})
            require_confirmation = data.get('require_confirmation', False)
            if not skill_name:
                return jsonify(error_response("缺少 skill 参数", 400)), 400

            from function_engine import execute_skill
            result = execute_skill(skill_name, arguments, require_confirmation)
            if result.get('success'):
                return jsonify(success_response(data=result.get('data'), message=result.get('message', '技能执行成功')))
            else:
                return jsonify(error_response(
                    message=result.get('message', '技能执行失败'),
                    code=result.get('code', 500)
                )), result.get('code', 500)
        except Exception as e:
            logger.error(f"技能执行失败: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route('/api/skills/register', methods=['POST'])
    @require_api_key
    def register_skill_api():
        try:
            data = request.json or {}
            from function_engine import SkillDefinition, SkillTier, FunctionCategory, FunctionParameter, register_skill

            name = data.get('name', '')
            description = data.get('description', '')
            if not name or not description:
                return jsonify(error_response("name 和 description 为必填项", 400)), 400

            tier_str = data.get('tier', 'workflow')
            try:
                tier = SkillTier(tier_str)
            except ValueError:
                tier = SkillTier.WORKFLOW

            params_data = data.get('parameters', [])
            parameters = [FunctionParameter.from_dict(p) for p in params_data]

            skill = SkillDefinition(
                name=name,
                description=description,
                category=FunctionCategory.UTILITY,
                parameters=parameters,
                tier=tier,
                usage_example=data.get('usage_example', ''),
                pseudo_code=data.get('pseudo_code', ''),
                confidence=data.get('confidence', 0.7),
                is_beta=data.get('is_beta', True),
            )
            register_skill(skill)
            return jsonify(success_response(data=skill.to_api_dict(include_details=True), message=f"技能 '{name}' 注册成功"))
        except Exception as e:
            logger.error(f"注册技能失败: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route('/api/skills/delete/<skill_name>', methods=['DELETE'])
    @require_api_key
    def delete_skill_api(skill_name):
        try:
            from function_engine import skill_registry
            if skill_registry.delete_skill(skill_name):
                return jsonify(success_response(message=f"技能 '{skill_name}' 已删除"))
            return jsonify(error_response(f"技能 '{skill_name}' 不存在", 404)), 404
        except Exception as e:
            logger.error(f"删除技能失败: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route('/api/skills/history', methods=['GET'])
    @require_api_key
    def skill_history_api():
        try:
            from function_engine import skill_registry
            skill_name = request.args.get('skill', None)
            limit = request.args.get('limit', 50, type=int)
            history = skill_registry.get_history(skill_name, limit)
            return jsonify(success_response(data={'history': history, 'count': len(history)}))
        except Exception as e:
            logger.error(f"获取技能历史失败: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route('/api/skills/search', methods=['POST'])
    def search_skills_api():
        try:
            data = request.json or {}
            query = data.get('query', '')
            limit = data.get('limit', 10)
            if not query:
                return jsonify(error_response("缺少 query 参数", 400)), 400

            from function_engine import skill_registry
            results = skill_registry.search_by_description(query, limit)
            return jsonify(success_response(data={
                'skills': [s.to_api_dict(include_details=True) for s in results],
                'count': len(results)
            }))
        except Exception as e:
            logger.error(f"技能搜索失败: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route('/api/skills/retrieve', methods=['POST'])
    def retrieve_skills_api():
        try:
            data = request.json or {}
            query = data.get('query', '')
            top_k = data.get('top_k', 7)
            max_tokens = data.get('max_tokens', 1500)
            context_skills = data.get('context_skills', None)
            if not query:
                return jsonify(error_response("缺少 query 参数", 400)), 400

            from skill_retriever import retrieve_skills
            results = retrieve_skills(query, top_k, max_tokens, context_skills)
            return jsonify(success_response(data={'skills': results, 'count': len(results)}))
        except Exception as e:
            logger.error(f"技能语义检索失败: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route('/api/skills/detail/<skill_name>', methods=['GET'])
    def skill_detail_api(skill_name):
        try:
            from skill_retriever import get_skill_detail
            detail = get_skill_detail(skill_name)
            if not detail:
                return jsonify(error_response(f"技能 '{skill_name}' 不存在", 404)), 404
            return jsonify(success_response(data=detail))
        except Exception as e:
            logger.error(f"获取技能详情失败: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route('/api/skills/retriever/stats', methods=['GET'])
    def retriever_stats_api():
        try:
            from skill_retriever import get_skill_retriever
            retriever = get_skill_retriever()
            return jsonify(success_response(data=retriever.get_stats()))
        except Exception as e:
            logger.error(f"获取检索器统计失败: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route('/api/skills/execute-loop', methods=['POST'])
    @require_api_key
    def execute_skill_loop_api():
        try:
            data = request.json or {}
            skill_name = data.get('skill', '')
            arguments = data.get('arguments', {})
            context = data.get('context', None)
            if not skill_name:
                return jsonify(error_response("缺少 skill 参数", 400)), 400

            from skill_execution import execute_skill_loop
            result = execute_skill_loop(skill_name, arguments, context)
            if result.get('success'):
                return jsonify(success_response(data=result.get('data'), message=result.get('message', '技能执行成功')))
            else:
                return jsonify(error_response(
                    message=result.get('message', '技能执行失败'),
                    code=result.get('code', 500)
                )), result.get('code', 500)
        except Exception as e:
            logger.error(f"技能执行环路失败: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route('/api/skills/parse-call', methods=['POST'])
    def parse_skill_call_api():
        try:
            data = request.json or {}
            text = data.get('text', '')
            if not text:
                return jsonify(error_response("缺少 text 参数", 400)), 400

            from skill_execution import parse_skill_call, parse_need_details
            call = parse_skill_call(text)
            need = parse_need_details(text)
            return jsonify(success_response(data={
                'call': call,
                'need_details': need,
            }))
        except Exception as e:
            logger.error(f"解析技能调用失败: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route('/api/skills/validate', methods=['POST'])
    def validate_skill_params_api():
        try:
            data = request.json or {}
            skill_name = data.get('skill', '')
            arguments = data.get('arguments', {})
            if not skill_name:
                return jsonify(error_response("缺少 skill 参数", 400)), 400

            from skill_execution import validate_skill_params
            validated, error = validate_skill_params(skill_name, arguments)
            return jsonify(success_response(data={
                'validated': validated,
                'validation_error': error,
                'valid': error is None,
            }))
        except Exception as e:
            logger.error(f"参数校验失败: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route('/api/skills/execution-log', methods=['GET'])
    @require_api_key
    def execution_log_api():
        try:
            from skill_execution import get_execution_engine
            limit = request.args.get('limit', 50, type=int)
            engine = get_execution_engine()
            log = engine.get_execution_log(limit)
            return jsonify(success_response(data={'log': log, 'count': len(log)}))
        except Exception as e:
            logger.error(f"获取执行日志失败: {e}")
            return jsonify(error_response(str(e), 500)), 500

    # ─── 自进化 API ───

    @app.route('/api/skills/evolution/detect', methods=['POST'])
    def detect_evolution_api():
        try:
            data = request.json or {}
            user_message = data.get('message', '')
            conversation = data.get('conversation', [])
            execution_trace = data.get('execution_trace', None)
            was_successful = data.get('was_successful', True)
            if not user_message:
                return jsonify(error_response("缺少 message 参数", 400)), 400

            from skill_evolution import detect_evolution_trigger
            result = detect_evolution_trigger(user_message, conversation, execution_trace, was_successful)
            return jsonify(success_response(data={'trigger': result}))
        except Exception as e:
            logger.error(f"进化触发检测失败: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route('/api/skills/evolution/evolve', methods=['POST'])
    @require_api_key
    def evolve_skill_api():
        try:
            from skill_evolution import evolve_skill
            result = evolve_skill()
            if result:
                return jsonify(success_response(data=result))
            return jsonify(success_response(data=None, message="无可进化的种子"))
        except Exception as e:
            logger.error(f"技能进化失败: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route('/api/skills/evolution/teach', methods=['POST'])
    @require_api_key
    def teach_skill_api():
        try:
            data = request.json or {}
            name = data.get('name', '')
            description = data.get('description', '')
            if not name or not description:
                return jsonify(error_response("name 和 description 为必填项", 400)), 400

            from skill_evolution import teach_new_skill
            result = teach_new_skill(
                name=name,
                description=description,
                pseudo_code=data.get('pseudo_code', ''),
                parameters=data.get('parameters', None),
                usage_example=data.get('usage_example', ''),
            )
            if result.get('success'):
                return jsonify(success_response(data=result, message=f"技能 '{name}' 学习成功"))
            else:
                return jsonify(error_response(
                    message=result.get('message', '技能验证未通过'),
                    code=400,
                    data=result
                )), 400
        except Exception as e:
            logger.error(f"技能教学失败: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route('/api/skills/evolution/log', methods=['GET'])
    def evolution_log_api():
        try:
            from skill_evolution import get_evolution_manager
            limit = request.args.get('limit', 50, type=int)
            manager = get_evolution_manager()
            log = manager.get_evolution_log(limit)
            return jsonify(success_response(data={'log': log, 'count': len(log)}))
        except Exception as e:
            logger.error(f"获取进化日志失败: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route('/api/skills/evolution/seeds', methods=['GET'])
    def evolution_seeds_api():
        try:
            from skill_evolution import get_evolution_manager
            manager = get_evolution_manager()
            seeds = manager.get_pending_seeds()
            return jsonify(success_response(data={'seeds': seeds, 'count': len(seeds)}))
        except Exception as e:
            logger.error(f"获取进化种子失败: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route('/api/skills/evolution/candidates', methods=['GET'])
    def evolution_candidates_api():
        try:
            from skill_evolution import get_evolution_manager
            manager = get_evolution_manager()
            candidates = manager.get_candidates()
            return jsonify(success_response(data={'candidates': candidates, 'count': len(candidates)}))
        except Exception as e:
            logger.error(f"获取进化候选失败: {e}")
            return jsonify(error_response(str(e), 500)), 500

    # ─── 治理 API ───

    @app.route('/api/skills/governance/run', methods=['POST'])
    @require_api_key
    def run_governance_api():
        try:
            from skill_governor import run_governance
            result = run_governance()
            return jsonify(success_response(data=result))
        except Exception as e:
            logger.error(f"治理执行失败: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route('/api/skills/governance/status', methods=['GET'])
    def governance_status_api():
        try:
            from skill_governor import get_governance_status
            status = get_governance_status()
            return jsonify(success_response(data=status))
        except Exception as e:
            logger.error(f"获取治理状态失败: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route('/api/skills/governance/dedup', methods=['POST'])
    @require_api_key
    def dedup_skills_api():
        try:
            from skill_governor import get_governor
            governor = get_governor()
            results = governor.run_deduplication()
            return jsonify(success_response(data={'duplicates': results, 'count': len(results)}))
        except Exception as e:
            logger.error(f"去重执行失败: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route('/api/skills/governance/vitality', methods=['POST'])
    @require_api_key
    def update_vitality_api():
        try:
            from skill_governor import update_vitality_scores
            update_vitality_scores()
            return jsonify(success_response(message="生命力分数已更新"))
        except Exception as e:
            logger.error(f"生命力更新失败: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route('/api/skills/governance/evict', methods=['POST'])
    @require_api_key
    def evict_skills_api():
        try:
            from skill_governor import get_governor
            governor = get_governor()
            result = governor.run_eviction()
            return jsonify(success_response(data=result))
        except Exception as e:
            logger.error(f"淘汰执行失败: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route('/api/skills/governance/log', methods=['GET'])
    def governance_log_api():
        try:
            from skill_governor import get_governor
            limit = request.args.get('limit', 50, type=int)
            governor = get_governor()
            log = governor.get_governance_log(limit)
            return jsonify(success_response(data={'log': log, 'count': len(log)}))
        except Exception as e:
            logger.error(f"获取治理日志失败: {e}")
            return jsonify(error_response(str(e), 500)), 500

    @app.route('/api/skills/governance/metrics', methods=['POST'])
    def record_retrieval_metric_api():
        try:
            data = request.json or {}
            from skill_governor import get_governor
            governor = get_governor()
            governor.record_retrieval_metric(
                was_accurate=data.get('was_accurate', True),
                latency_ms=data.get('latency_ms', 0),
                skill_token_ratio=data.get('skill_token_ratio', 0),
            )
            return jsonify(success_response(message="指标已记录"))
        except Exception as e:
            logger.error(f"记录指标失败: {e}")
            return jsonify(error_response(str(e), 500)), 500

    logger.info("✓ 函数调用 & 技能管理 API 路由已注册")
