"""Agent 人设生成器：基于图谱实体节点并行生成详细人设

裁剪自 MiroFish 的 OasisProfileGenerator，仅保留人设生成核心逻辑：
- 区分个人 / 群体实体
- LLM 详细人设 + 规则兜底
- 并行加速 + 实时落盘
"""

from __future__ import annotations

import json
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock
from typing import Any, Callable, Dict, List, Optional

from openai import OpenAI

from ..config import Config
from ..utils.logger import get_logger
from .local_entity_reader import EntityNode

logger = get_logger("minifish.persona_generator")


@dataclass
class AgentPersona:
    user_id: int
    user_name: str
    name: str
    bio: str
    persona: str

    age: Optional[int] = None
    gender: Optional[str] = None
    mbti: Optional[str] = None
    country: Optional[str] = None
    profession: Optional[str] = None
    interested_topics: List[str] = field(default_factory=list)

    source_entity_uuid: Optional[str] = None
    source_entity_type: Optional[str] = None

    created_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "user_name": self.user_name,
            "name": self.name,
            "bio": self.bio,
            "persona": self.persona,
            "age": self.age,
            "gender": self.gender,
            "mbti": self.mbti,
            "country": self.country,
            "profession": self.profession,
            "interested_topics": self.interested_topics,
            "source_entity_uuid": self.source_entity_uuid,
            "source_entity_type": self.source_entity_type,
            "created_at": self.created_at,
        }


class PersonaGenerator:
    MBTI_TYPES = [
        "INTJ", "INTP", "ENTJ", "ENTP",
        "INFJ", "INFP", "ENFJ", "ENFP",
        "ISTJ", "ISFJ", "ESTJ", "ESFJ",
        "ISTP", "ISFP", "ESTP", "ESFP",
    ]
    COUNTRIES = [
        "中国", "美国", "英国", "日本", "德国", "法国",
        "加拿大", "澳大利亚", "巴西", "印度", "韩国",
    ]

    INDIVIDUAL_ENTITY_TYPES = {
        "student", "alumni", "professor", "person", "publicfigure",
        "expert", "faculty", "official", "journalist", "activist",
    }
    GROUP_ENTITY_TYPES = {
        "university", "governmentagency", "organization", "ngo",
        "mediaoutlet", "company", "institution", "group", "community",
    }

    @staticmethod
    def _normalize_base_url(url: str) -> str:
        if not url:
            return url
        u = url.strip().rstrip("/")
        if re.search(r"/v1$", u):
            return u
        return f"{u}/v1"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        self.api_key = api_key or Config.LLM_API_KEY
        self.base_url = self._normalize_base_url(base_url or Config.LLM_BASE_URL)
        self.model_name = model_name or Config.LLM_MODEL_NAME

        if not self.api_key:
            raise ValueError("LLM_API_KEY 未配置")

        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    # ---------- 单实体生成 ----------

    def generate_profile_from_entity(
        self,
        entity: EntityNode,
        user_id: int,
        use_llm: bool = True,
    ) -> AgentPersona:
        entity_type = entity.get_entity_type() or "Entity"
        name = entity.name
        user_name = self._generate_username(name)
        context = self._build_entity_context(entity)

        if use_llm:
            data = self._generate_with_llm(
                entity_name=name,
                entity_type=entity_type,
                entity_summary=entity.summary,
                entity_attributes=entity.attributes,
                context=context,
            )
        else:
            data = self._generate_rule_based(name, entity_type, entity.summary, entity.attributes)

        return AgentPersona(
            user_id=user_id,
            user_name=user_name,
            name=name,
            bio=data.get("bio", f"{entity_type}: {name}"),
            persona=data.get("persona", entity.summary or f"{name} 是一个 {entity_type}。"),
            age=data.get("age"),
            gender=data.get("gender"),
            mbti=data.get("mbti"),
            country=data.get("country"),
            profession=data.get("profession"),
            interested_topics=data.get("interested_topics", []),
            source_entity_uuid=entity.uuid,
            source_entity_type=entity_type,
        )

    def _generate_username(self, name: str) -> str:
        username = name.lower().replace(" ", "_")
        username = ''.join(c for c in username if c.isalnum() or c == '_')
        return f"{username}_{random.randint(100, 999)}"

    def _is_individual(self, entity_type: str) -> bool:
        return entity_type.lower() in self.INDIVIDUAL_ENTITY_TYPES

    def _build_entity_context(self, entity: EntityNode) -> str:
        parts = []
        if entity.attributes:
            attrs = [f"- {k}: {v}" for k, v in entity.attributes.items() if v and str(v).strip()]
            if attrs:
                parts.append("### 实体属性\n" + "\n".join(attrs))

        if entity.related_edges:
            relationships = []
            for edge in entity.related_edges:
                fact = edge.get("fact", "")
                edge_name = edge.get("name") or edge.get("fact_type", "")
                if fact:
                    relationships.append(f"- {fact}")
                elif edge_name:
                    relationships.append(f"- {entity.name} --[{edge_name}]--> (相关实体)")
            if relationships:
                parts.append("### 相关事实和关系\n" + "\n".join(relationships))

        if entity.related_nodes:
            related_info = []
            for node in entity.related_nodes:
                node_name = node.get("name", "")
                labels = [l for l in (node.get("labels") or []) if l not in ["Entity", "Node"]]
                label_str = f" ({', '.join(labels)})" if labels else ""
                summary = node.get("summary", "")
                if summary:
                    related_info.append(f"- **{node_name}**{label_str}: {summary}")
                else:
                    related_info.append(f"- **{node_name}**{label_str}")
            if related_info:
                parts.append("### 关联实体信息\n" + "\n".join(related_info))

        return "\n\n".join(parts)

    # ---------- LLM 生成 ----------

    def _generate_with_llm(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any],
        context: str,
    ) -> Dict[str, Any]:
        is_individual = self._is_individual(entity_type)
        prompt = (
            self._build_individual_prompt(entity_name, entity_type, entity_summary, entity_attributes, context)
            if is_individual
            else self._build_group_prompt(entity_name, entity_type, entity_summary, entity_attributes, context)
        )
        system_prompt = (
            "你是社交媒体用户画像生成专家。生成详细、真实的人设用于舆论模拟，最大程度还原已有现实情况。"
            "必须返回有效的JSON格式，所有字符串值不能包含未转义的换行符。使用中文。"
        )

        max_attempts = 3
        last_err = None
        for attempt in range(max_attempts):
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.7 - attempt * 0.1,
                )
                content = response.choices[0].message.content
                if response.choices[0].finish_reason == "length":
                    content = self._fix_truncated_json(content)
                try:
                    result = json.loads(content)
                except json.JSONDecodeError:
                    result = self._try_fix_json(content, entity_name, entity_type, entity_summary)
                if not result.get("bio"):
                    result["bio"] = entity_summary[:200] if entity_summary else f"{entity_type}: {entity_name}"
                if not result.get("persona"):
                    result["persona"] = entity_summary or f"{entity_name} 是一个 {entity_type}。"
                return result
            except Exception as e:
                last_err = e
                logger.warning(f"LLM 生成人设失败 (attempt {attempt+1}): {str(e)[:120]}")
                time.sleep(1 * (attempt + 1))

        logger.warning(f"LLM 三次尝试仍失败，回退到规则生成: {last_err}")
        return self._generate_rule_based(entity_name, entity_type, entity_summary, entity_attributes)

    @staticmethod
    def _fix_truncated_json(content: str) -> str:
        content = content.strip()
        open_braces = content.count('{') - content.count('}')
        open_brackets = content.count('[') - content.count(']')
        if content and content[-1] not in '",}]':
            content += '"'
        content += ']' * open_brackets
        content += '}' * open_braces
        return content

    def _try_fix_json(self, content: str, entity_name: str, entity_type: str, entity_summary: str = "") -> Dict[str, Any]:
        content = self._fix_truncated_json(content)
        m = re.search(r'\{[\s\S]*\}', content)
        if m:
            json_str = m.group()
            json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', json_str)
            json_str = re.sub(r'\s+', ' ', json_str)
            try:
                return json.loads(json_str)
            except Exception:
                pass

        bio_match = re.search(r'"bio"\s*:\s*"([^"]*)"', content)
        persona_match = re.search(r'"persona"\s*:\s*"([^"]*)', content)
        return {
            "bio": bio_match.group(1) if bio_match else (entity_summary[:200] if entity_summary else f"{entity_type}: {entity_name}"),
            "persona": persona_match.group(1) if persona_match else (entity_summary or f"{entity_name} 是一个 {entity_type}。"),
        }

    def _build_individual_prompt(self, entity_name, entity_type, entity_summary, entity_attributes, context):
        attrs_str = json.dumps(entity_attributes, ensure_ascii=False) if entity_attributes else "无"
        context_str = context[:3000] if context else "无额外上下文"
        return f"""为实体生成详细的社交媒体用户人设，最大程度还原已有现实情况。

实体名称: {entity_name}
实体类型: {entity_type}
实体摘要: {entity_summary}
实体属性: {attrs_str}

上下文信息:
{context_str}

请生成 JSON，包含以下字段：

1. bio: 社交媒体简介，200字
2. persona: 详细人设描述（约 1500 字），需包含：
   - 基本信息（年龄、职业、教育背景、所在地）
   - 人物背景（重要经历、与事件的关联、社会关系）
   - 性格特征（MBTI、核心性格、情绪表达方式）
   - 社交媒体行为（发帖频率、内容偏好、互动风格）
   - 立场观点（对话题的态度）
   - 个人记忆（个体与事件的关联与已有动作）
3. age: 年龄整数
4. gender: "male" 或 "female"
5. mbti: MBTI 类型
6. country: 国家（中文）
7. profession: 职业
8. interested_topics: 感兴趣话题数组

要求：所有字段值是字符串或数字；persona 一段连贯文字；除 gender 用英文外其余使用中文。
"""

    def _build_group_prompt(self, entity_name, entity_type, entity_summary, entity_attributes, context):
        attrs_str = json.dumps(entity_attributes, ensure_ascii=False) if entity_attributes else "无"
        context_str = context[:3000] if context else "无额外上下文"
        return f"""为机构/群体实体生成详细的社交媒体账号设定，最大程度还原已有现实情况。

实体名称: {entity_name}
实体类型: {entity_type}
实体摘要: {entity_summary}
实体属性: {attrs_str}

上下文信息:
{context_str}

请生成 JSON，包含以下字段：

1. bio: 官方账号简介，200 字
2. persona: 详细账号设定描述（约 1500 字），需包含：
   - 机构基本信息
   - 账号定位与目标受众
   - 发言风格
   - 发布内容特点
   - 立场态度
   - 机构记忆（机构与事件的关联）
3. age: 整数 30
4. gender: 字符串 "other"
5. mbti: MBTI 类型
6. country: 中文国家名
7. profession: 机构职能描述
8. interested_topics: 关注领域数组
"""

    # ---------- 规则兜底 ----------

    def _generate_rule_based(self, entity_name, entity_type, entity_summary, entity_attributes):
        t = (entity_type or "").lower()
        if t in {"student", "alumni"}:
            return {
                "bio": f"{entity_type}，关注学术与社会话题。",
                "persona": f"{entity_name} 是一名 {entity_type}，活跃于学术与社会议题讨论。",
                "age": random.randint(18, 30),
                "gender": random.choice(["male", "female"]),
                "mbti": random.choice(self.MBTI_TYPES),
                "country": random.choice(self.COUNTRIES),
                "profession": "学生",
                "interested_topics": ["教育", "社会议题", "科技"],
            }
        if t in {"publicfigure", "expert", "faculty"}:
            return {
                "bio": "在所在领域具有影响力的专家与意见领袖。",
                "persona": f"{entity_name} 是 {entity_type}，以专业洞察影响公共讨论。",
                "age": random.randint(35, 60),
                "gender": random.choice(["male", "female"]),
                "mbti": random.choice(["ENTJ", "INTJ", "ENTP", "INTP"]),
                "country": random.choice(self.COUNTRIES),
                "profession": entity_attributes.get("occupation", "专家"),
                "interested_topics": ["政治", "经济", "文化与社会"],
            }
        if t in {"mediaoutlet", "socialmediaplatform"}:
            return {
                "bio": f"{entity_name} 官方账号，发布资讯与动态。",
                "persona": f"{entity_name} 是媒体机构，发布及时资讯并促进公共讨论。",
                "age": 30,
                "gender": "other",
                "mbti": "ISTJ",
                "country": "中国",
                "profession": "媒体",
                "interested_topics": ["综合资讯", "时事", "公共事务"],
            }
        if t in {"university", "governmentagency", "ngo", "organization"}:
            return {
                "bio": f"{entity_name} 官方账号。",
                "persona": f"{entity_name} 是机构主体，发布官方立场并与利益相关方互动。",
                "age": 30,
                "gender": "other",
                "mbti": "ISTJ",
                "country": "中国",
                "profession": entity_type,
                "interested_topics": ["公共政策", "社区", "官方公告"],
            }
        return {
            "bio": entity_summary[:150] if entity_summary else f"{entity_type}: {entity_name}",
            "persona": entity_summary or f"{entity_name} 是 {entity_type}，参与社交讨论。",
            "age": random.randint(25, 50),
            "gender": random.choice(["male", "female"]),
            "mbti": random.choice(self.MBTI_TYPES),
            "country": random.choice(self.COUNTRIES),
            "profession": entity_type,
            "interested_topics": ["综合", "社会议题"],
        }

    # ---------- 批量并行 ----------

    def generate_profiles(
        self,
        entities: List[EntityNode],
        use_llm: bool = True,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        parallel_count: Optional[int] = None,
        realtime_output_path: Optional[str] = None,
    ) -> List[AgentPersona]:
        total = len(entities)
        profiles: List[Optional[AgentPersona]] = [None] * total
        completed = [0]
        lock = Lock()
        parallel_count = parallel_count or Config.PERSONA_CONCURRENCY

        def save_realtime():
            if not realtime_output_path:
                return
            with lock:
                existing = [p for p in profiles if p is not None]
                if not existing:
                    return
                try:
                    with open(realtime_output_path, 'w', encoding='utf-8') as f:
                        json.dump([p.to_dict() for p in existing], f, ensure_ascii=False, indent=2)
                except Exception as e:
                    logger.warning(f"实时落盘失败: {e}")

        def gen_single(idx: int, entity: EntityNode):
            try:
                p = self.generate_profile_from_entity(entity=entity, user_id=idx, use_llm=use_llm)
                return idx, p, None
            except Exception as e:
                logger.error(f"生成 {entity.name} 人设失败: {e}")
                fallback = AgentPersona(
                    user_id=idx,
                    user_name=self._generate_username(entity.name),
                    name=entity.name,
                    bio=f"{entity.get_entity_type() or 'Entity'}: {entity.name}",
                    persona=entity.summary or "社交媒体参与者。",
                    source_entity_uuid=entity.uuid,
                    source_entity_type=entity.get_entity_type() or "Entity",
                )
                return idx, fallback, str(e)

        logger.info(f"开始并行生成 {total} 个人设（并行数: {parallel_count}）")

        with ThreadPoolExecutor(max_workers=parallel_count) as executor:
            futures = {executor.submit(gen_single, idx, entity): (idx, entity) for idx, entity in enumerate(entities)}
            for future in as_completed(futures):
                idx, entity = futures[future]
                try:
                    result_idx, profile, error = future.result()
                    profiles[result_idx] = profile
                    with lock:
                        completed[0] += 1
                        current = completed[0]
                    save_realtime()
                    if progress_callback:
                        progress_callback(current, total, f"已完成 {current}/{total}: {entity.name}")
                    if error:
                        logger.warning(f"[{current}/{total}] {entity.name} 使用兜底人设: {error}")
                    else:
                        logger.info(f"[{current}/{total}] 已生成: {entity.name}")
                except Exception as e:
                    logger.error(f"处理 {entity.name} 异常: {e}")

        return [p for p in profiles if p is not None]
