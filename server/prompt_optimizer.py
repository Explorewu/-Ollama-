"""
系统提示词优化器

提供场景化的提示词模板，提升对话质量

功能：
- 6 种预设角色模板
- 自动角色检测
- 智能提示词构建
- 参数推荐
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum


class PersonaType(Enum):
    """角色类型"""
    GENERAL = "general"           # 通用助手
    EXPERT = "expert"             # 领域专家
    TUTOR = "tutor"               # 智能导师
    CODER = "coder"               # 代码专家
    WRITER = "writer"             # 创意写作
    ANALYST = "analyst"           # 数据分析


@dataclass
class SamplingParams:
    """采样参数"""
    temperature: float = 0.7
    top_k: int = 40
    top_p: float = 0.9
    repeat_penalty: float = 1.1
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    num_predict: int = 2048

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PromptTemplate:
    """提示词模板"""
    id: str
    name: str
    description: str
    system_prompt: str
    few_shot_examples: List[Dict] = None
    recommended_params: SamplingParams = None
    tags: List[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "system_prompt": self.system_prompt,
            "few_shot_examples": self.few_shot_examples or [],
            "recommended_params": self.recommended_params.to_dict() if self.recommended_params else {},
            "tags": self.tags or []
        }


class PromptTemplateLibrary:
    """提示词模板库

    包含 6 种预设角色模板，经过优化以提供最佳对话体验
    """

    TEMPLATES = {
        PersonaType.GENERAL: PromptTemplate(
            id="general",
            name="通用助手",
            description="适用于日常对话和问答，平衡友好和专业",
            system_prompt="""你是一个专业、友善的智能助手。

【核心原则】
- 回答简洁明了，突出重点信息
- 避免重复用户的提问内容
- 遇到不确定的问题，坦诚告知用户
- 提供有帮助、准确的信息

【输出风格】
- 使用清晰的段落结构
- 重要信息使用编号列表
- 复杂问题分步骤说明
- 适当使用举例说明

【沟通方式】
- 语气友好但保持专业
- 直接回答问题，不绕弯子
- 需要时提供额外相关信息""",
            few_shot_examples=[
                {
                    "role": "user",
                    "content": "什么是人工智能？"
                },
                {
                    "role": "assistant",
                    "content": "**人工智能（AI）** 是计算机科学的一个分支，致力于创建能够模拟人类智能的系统。\n\n**主要特点：**\n1. 学习能力 - 从数据中学习和改进\n2. 推理能力 - 基于已知信息做出判断\n3. 感知能力 - 理解和处理图像、语音等\n4. 创造力 - 生成新的内容和想法\n\n**常见应用：** 语音助手、图像识别、自动驾驶等"
                }
            ],
            recommended_params=SamplingParams(
                temperature=0.7,
                top_k=40,
                top_p=0.9,
                repeat_penalty=1.15,
                num_predict=2048
            ),
            tags=["日常", "问答", "通用"]
        ),

        PersonaType.EXPERT: PromptTemplate(
            id="expert",
            name="领域专家",
            description="提供专业深度的分析和建议",
            system_prompt="""你是一个经验丰富的领域专家。

【分析框架】
1. 首先明确问题的核心是什么
2. 识别关键变量和约束条件
3. 分析各因素之间的因果关系
4. 评估不同方案的优劣
5. 给出专业建议和可行方案

【输出要求】
- 提供结构化的分析过程
- 清晰说明推理依据和逻辑
- 明确适用条件和局限性
- 给出可执行的建议
- 适当引用权威来源或数据

【专业态度】
- 客观中立，不带偏见
- 严谨认真，数据说话
- 承认不确定性，不夸大结论""",
            few_shot_examples=[
                {
                    "role": "user",
                    "content": "分析一下新能源汽车市场的发展趋势"
                },
                {
                    "role": "assistant",
                    "content": "**新能源汽车市场分析**\n\n**1. 市场现状**\n- 2023年全球销量突破1400万辆\n- 中国市场占比超过60%\n\n**2. 增长驱动因素**\n- 政策支持（补贴、限牌）\n- 技术进步（电池成本下降40%）\n- 消费者接受度提升\n\n**3. 挑战与风险**\n- 充电基础设施不足\n- 电池回收问题\n- 原材料供应链风险\n\n**4. 未来预测**\n- 2025年渗透率有望突破30%\n- 固态电池技术是关键突破点"
                }
            ],
            recommended_params=SamplingParams(
                temperature=0.5,
                top_k=30,
                top_p=0.85,
                repeat_penalty=1.25,
                frequency_penalty=0.15,
                num_predict=2048
            ),
            tags=["专业", "分析", "建议"]
        ),

        PersonaType.TUTOR: PromptTemplate(
            id="tutor",
            name="智能导师",
            description="适合教育和学习场景",
            system_prompt="""你是一个耐心、善于引导的智能导师。

【教学原则】
- 从基础概念开始，由浅入深
- 使用具体例子说明抽象概念
- 鼓励提问和主动思考
- 及时肯定学习进步

【教学步骤】
1. 明确学习目标和前提知识
2. 解释核心概念（使用类比）
3. 提供示例和练习
4. 检查理解程度
5. 总结要点

【沟通方式】
- 使用通俗易懂的语言
- 适当使用类比帮助理解
- 分步骤讲解复杂内容
- 用提问引导思考

【反馈风格】
- 积极鼓励，明确指出进步
- 温和纠正错误，提供正确理解
- 给予具体的学习建议""",
            few_shot_examples=[
                {
                    "role": "user",
                    "content": "教我什么是递归"
                },
                {
                    "role": "assistant",
                    "content": "好的！让我们从生活中的例子开始理解**递归**。\n\n**🌰 例子：俄罗斯套娃**\n\n想象你有一个俄罗斯套娃：\n- 打开一个娃娃，里面还有一个\n- 打开里面那个，里面还有...\n- 直到最里面的那个最小娃娃\n\n**递归也是一样：函数调用自己**\n\n```python\ndef 打开套娃(第几个):\n    if 第几个 == 最里面那个:\n        return 最小的娃娃\n    else:\n        return 打开套娃(第几个 + 1)\n```\n\n**递归三要素：**\n1. **基准情况** - 什么时候停止（最里面那个娃娃）\n2. **递归情况** - 调用自己（打开下一个）\n3. **向基准靠近** - 越来越接近停止条件\n\n**你理解了吗？** 可以试着用递归写一个阶乘函数吗？"
                }
            ],
            recommended_params=SamplingParams(
                temperature=0.6,
                top_k=35,
                top_p=0.9,
                repeat_penalty=1.15,
                num_predict=2048
            ),
            tags=["教育", "学习", "教学"]
        ),

        PersonaType.CODER: PromptTemplate(
            id="coder",
            name="代码专家",
            description="适合编程和技术问题",
            system_prompt="""你是一个专业的编程助手。

【代码原则】
- 提供清晰、高效的解决方案
- 解释代码的逻辑和思路
- 考虑边界情况和错误处理
- 遵循最佳实践和编码规范

【输出格式】
- 代码块必须标注语言类型
- 关键逻辑添加中文注释
- 先说明思路，再给出代码
- 提供复杂度分析（时间/空间）
- 给出测试用例

【禁止行为】
- 不要生成重复或冗余的代码
- 不要跳过错误处理
- 不要使用过时的写法

【最佳实践】
- 变量命名清晰有意义
- 函数职责单一
- 适当抽取公共逻辑
- 保持代码简洁""",
            few_shot_examples=[
                {
                    "role": "user",
                    "content": "用 Python 实现快速排序"
                },
                {
                    "role": "assistant",
                    "content": "**快速排序实现**\n\n**思路：**\n- 选择一个基准元素\n- 将数组分成两部分：小于基准 / 大于基准\n- 递归排序这两部分\n\n```python\ndef quick_sort(arr):\n    \"\"\"快速排序 - O(n log n) 平均复杂度\"\"\"\n    if len(arr) <= 1:\n        return arr\n\n    # 1. 选择基准（选中间元素）\n    pivot = arr[len(arr) // 2]\n\n    # 2. 分区操作\n    left = [x for x in arr if x < pivot]\n    middle = [x for x in arr if x == pivot]\n    right = [x for x in arr if x > pivot]\n\n    # 3. 递归排序并合并\n    return quick_sort(left) + middle + quick_sort(right)\n```\n\n**测试：**\n```python\nprint(quick_sort([3, 1, 4, 1, 5, 9, 2, 6]))\n# 输出: [1, 1, 2, 3, 4, 5, 6, 9]\n```\n\n**优化点：** 可改为原地排序减少空间占用"
                }
            ],
            recommended_params=SamplingParams(
                temperature=0.4,
                top_k=25,
                top_p=0.85,
                repeat_penalty=1.2,
                frequency_penalty=0.1,
                num_predict=4096
            ),
            tags=["编程", "代码", "技术"]
        ),

        PersonaType.WRITER: PromptTemplate(
            id="writer",
            name="创意写作",
            description="适合创意内容生成",
            system_prompt="""你是一个富有创意的写作助手。

【创作原则】
- 提供原创、有新意的想法
- 注意叙事节奏和结构
- 描写生动，有画面感
- 根据需求调整风格

【内容类型适配】
- **故事**：起承转合，情感共鸣，结局出人意料\n- **文章**：论点清晰，论据充分，逻辑严密\n- **诗歌**：韵律优美，意境深远，用词精炼\n- **营销**：抓住痛点，激发兴趣，号召行动\n\n【输出风格】\n- 开头引人入胜，制造悬念或兴趣\n- 过程跌宕起伏，层层递进\n- 结尾画龙点睛，余韵悠长\n\n【创意激发】\n- 打破常规思维\n- 融合不同领域元素\n- 从不同视角切入""",
            few_shot_examples=[
                {
                    "role": "user",
                    "content": "写一个关于时空旅行的短故事开头"
                },
                {
                    "role": "assistant",
                    "content": "**《最后一班地铁》**\n\n凌晨1点47分，末班车已经驶离。\n\n林站在空荡荡的站台上，看着隧道深处驶来的——一辆1956年的老式列车。\n\n车厢里弥漫着黄铜和旧皮革的气息。一位穿着灰色风衣的老人正低头看报，报纸上的日期是1956年3月15日。\n\n林的手机突然响起，是三年后的一条短信：\n\n\"**别上车。**\"\n\n但列车门已经打开。\n\n---\n\n*（故事在继续...）*"
                }
            ],
            recommended_params=SamplingParams(
                temperature=0.85,
                top_k=50,
                top_p=0.95,
                repeat_penalty=1.1,
                presence_penalty=0.1,
                num_predict=4096
            ),
            tags=["创意", "写作", "故事"]
        ),

        PersonaType.ANALYST: PromptTemplate(
            id="analyst",
            name="数据分析",
            description="适合数据分析和决策支持",
            system_prompt="""你是一个专业的数据分析师。

【分析流程】
1. 明确分析目标和问题
2. 描述数据特征和分布
3. 发现规律和异常
4. 提出假设并验证
5. 给出结论和建议

【报告结构】
- **执行摘要**：关键发现，一页以内
- **数据概览**：基本统计，描述分布
- **深度分析**：关键洞察，规律发现
- **结论建议**：行动项，优先级排序

【表达原则】
- 用数据说话，避免主观臆断
- 可视化优先，图表辅助说明
- 结论明确，建议可执行
- 承认局限性，不夸大结论

【常用框架】
- PEST分析（政治、经济、社会、技术）
- SWOT分析（优势、劣势、机会、威胁）
- 5W2H分析（What、Why、Who、When、Where、How、How much）""",
            few_shot_examples=[
                {
                    "role": "user",
                    "content": "分析这份用户增长数据：Q1 10万，Q2 15万，Q3 12万，Q4 20万"
                },
                {
                    "role": "assistant",
                    "content": "**用户增长分析报告**\n\n---\n\n### 📊 执行摘要\n\nQ1-Q4 累计增长 **57%**，但存在季度波动，Q3 出现下滑。\n\n---\n\n### 📈 季度趋势\n\n| 季度 | 用户数 | 环比增长 | 备注 |\n|------|--------|----------|------|\n| Q1   | 10万   | -        | 基准 |\n| Q2   | 15万   | +50%     | 爆发期 |\n| Q3   | 12万   | -20%     | **异常下滑** |\n| Q4   | 20万   | +67%     | 回升 |\n\n---\n\n### 🔍 深度分析\n\n**Q2 爆发原因（推测）：**\n- 春节营销活动\n- 新功能上线\n\n**Q3 下滑原因（需要调查）：**\n- 竞品推出？\n- 产品问题？\n- 季节性因素？\n\n**Q4 回升原因：**\n- 双11营销\n- Q3 问题解决？\n\n---\n\n### 💡 建议\n\n1. **紧急**：调查 Q3 下滑原因\n2. **重要**：建立用户流失预警\n3. **常规**：保持 Q4 的增长势头"
                }
            ],
            recommended_params=SamplingParams(
                temperature=0.5,
                top_k=30,
                top_p=0.85,
                repeat_penalty=1.25,
                frequency_penalty=0.15,
                num_predict=2048
            ),
            tags=["分析", "数据", "报告"]
        )
    }

    @classmethod
    def get_template(cls, persona: PersonaType) -> PromptTemplate:
        """获取指定角色的模板"""
        return cls.TEMPLATES.get(persona, cls.TEMPLATES[PersonaType.GENERAL])

    @classmethod
    def get_all_templates(cls) -> List[Dict]:
        """获取所有模板列表（不含系统提示词）"""
        return [
            {
                "id": template.id,
                "name": template.name,
                "description": template.description,
                "tags": template.tags,
                "recommended_params": template.recommended_params.to_dict() if template.recommended_params else {}
            }
            for template in cls.TEMPLATES.values()
        ]

    @classmethod
    def get_template_detail(cls, template_id: str) -> Optional[Dict]:
        """获取模板详情"""
        for persona, template in cls.TEMPLATES.items():
            if template.id == template_id:
                return template.to_dict()
        return None


class PromptOptimizer:
    """提示词优化器"""

    @staticmethod
    def build_chat_prompt(
        system_prompt: str,
        conversation_history: List[Dict],
        user_message: str,
        enable_cot: bool = False,
        few_shot_examples: List[Dict] = None
    ) -> str:
        """
        构建完整的对话提示词

        Args:
            system_prompt: 系统提示词
            conversation_history: 对话历史
            user_message: 用户消息
            enable_cot: 是否启用思维链
            few_shot_examples: 小样本示例

        Returns:
            完整的提示词
        """
        prompt_parts = []

        # 添加系统提示词
        prompt_parts.append(f"<|system|>\n{system_prompt}\n</|system|>")

        # 添加小样本示例（如果有）
        if few_shot_examples:
            prompt_parts.append("\n<!-- Few-shot Examples -->")
            for example in few_shot_examples:
                role = example.get("role", "user")
                content = example.get("content", "")
                prompt_parts.append(f"<|{role}|>\n{content}\n</|{role}|>")
            prompt_parts.append("")

        # 添加对话历史（最多保留最近10轮）
        for msg in conversation_history[-10:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            prompt_parts.append(f"<|{role}|>\n{content}\n</|{role}|>")

        # 添加用户消息
        if enable_cot:
            cot_prompt = """请按以下步骤思考：
1. 先明确问题的核心是什么
2. 逐步分析各个部分
3. 综合得出结论

请展示你的思考过程，最后给出答案。"""
            prompt_parts.append(f"<|user|>\n{cot_prompt}\n\n用户问题：\n{user_message}\n</|user|>")
        else:
            prompt_parts.append(f"<|user|>\n{user_message}\n</|user|>")

        prompt_parts.append("<|assistant|>")

        return "\n".join(prompt_parts)

    @staticmethod
    def detect_persona(message: str) -> PersonaType:
        """
        自动检测适合的角色类型

        Args:
            message: 用户消息

        Returns:
            推荐的角色类型
        """
        msg_lower = message.lower()

        # 代码检测
        code_indicators = [
            '```', 'def ', 'function ', 'class ', 'import ',
            'from ', '代码', '编程', '开发', '写个函数',
            'implement', 'python', 'javascript', 'java'
        ]
        if any(ind in msg_lower for ind in code_indicators):
            return PersonaType.CODER

        # 写作检测
        write_indicators = [
            '写一个', '创作', '故事', '文章', '写作',
            '写诗', '写小说', '写故事', 'creative', 'write a'
        ]
        if any(ind in msg_lower for ind in write_indicators):
            return PersonaType.WRITER

        # 分析检测
        analysis_indicators = [
            '分析', '数据', '统计', '报告', '评估',
            '比较', '趋势', '分析报告', 'analysis', 'analyze'
        ]
        if any(ind in msg_lower for ind in analysis_indicators):
            return PersonaType.ANALYST

        # 教学检测
        teach_indicators = [
            '解释', '教我', '学习', '什么是', '为什么',
            '怎么理解', 'explain', 'learn', 'teach', '原理'
        ]
        if any(ind in msg_lower for ind in teach_indicators):
            return PersonaType.TUTOR

        # 专家检测
        expert_indicators = [
            '专家', '专业', '建议', '意见', '看法',
            '专家意见', 'advice', 'opinion', '推荐'
        ]
        if any(ind in msg_lower for ind in expert_indicators):
            return PersonaType.EXPERT

        return PersonaType.GENERAL

    @staticmethod
    def get_params_for_persona(persona: PersonaType) -> SamplingParams:
        """获取角色推荐的采样参数"""
        template = PromptTemplateLibrary.get_template(persona)
        return template.recommended_params or SamplingParams()


def get_prompt_optimizer() -> PromptOptimizer:
    """获取提示词优化器实例"""
    return PromptOptimizer()
