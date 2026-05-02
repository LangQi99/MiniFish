"""LLM 客户端封装（OpenAI 兼容）"""

import json
import re
from typing import Optional, Dict, Any, List
from openai import OpenAI

from ..config import Config


class LLMClient:
    @staticmethod
    def _normalize_base_url(url: str) -> str:
        if not url:
            return url
        u = url.strip().rstrip("/")
        if re.search(r"/v1$", u):
            return u
        return f"{u}/v1"

    @staticmethod
    def _extract_json_object(text: str) -> Optional[str]:
        if not text:
            return None
        s = text.strip()
        if (s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]")):
            return s
        start = s.find("{")
        end = s.rfind("}")
        if start != -1 and end != -1 and end > start:
            return s[start:end + 1]
        start = s.find("[")
        end = s.rfind("]")
        if start != -1 and end != -1 and end > start:
            return s[start:end + 1]
        return None

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.api_key = api_key or Config.LLM_API_KEY
        self.base_url = self._normalize_base_url(base_url or Config.LLM_BASE_URL)
        self.model = model or Config.LLM_MODEL_NAME

        if not self.api_key:
            raise ValueError("LLM_API_KEY 未配置")

        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        self._embedding_client = OpenAI(
            api_key=Config.EMBEDDING_API_KEY,
            base_url=self._normalize_base_url(Config.EMBEDDING_BASE_URL),
        )

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: Optional[Dict] = None,
    ) -> str:
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            kwargs["response_format"] = response_format
        response = self.client.chat.completions.create(**kwargs)
        return response.choices[0].message.content

    def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> Dict[str, Any]:
        response = self.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        try:
            parsed = json.loads(response)
            if isinstance(parsed, dict):
                return parsed
            if isinstance(parsed, str):
                maybe = self._extract_json_object(parsed)
                if maybe:
                    parsed2 = json.loads(maybe)
                    if isinstance(parsed2, dict):
                        return parsed2
        except Exception:
            pass

        fallback_messages = [
            {
                "role": "system",
                "content": "你必须只输出一个合法的 JSON 对象（以 { 开始，以 } 结束）。不要输出任何解释、前后缀、代码块标记。",
            },
            *messages,
        ]
        response2 = self.chat(
            messages=fallback_messages,
            temperature=max(0.0, temperature),
            max_tokens=max_tokens,
            response_format=None,
        )
        maybe = self._extract_json_object(response2)
        if not maybe:
            raise ValueError(f"模型未返回可解析的JSON对象: {response2[:200]}")
        parsed = json.loads(maybe)
        if not isinstance(parsed, dict):
            raise ValueError(f"JSON解析结果不是对象: {type(parsed).__name__}")
        return parsed

    def embed_texts(self, texts: List[str], model: Optional[str] = None) -> List[List[float]]:
        embed_model = model or Config.EMBEDDING_MODEL_NAME
        resp = self._embedding_client.embeddings.create(model=embed_model, input=texts)
        return [d.embedding for d in resp.data]
