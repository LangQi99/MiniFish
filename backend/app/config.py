"""配置管理 - 从项目根目录的 .env 加载"""

import os
from dotenv import load_dotenv

project_root_env = os.path.join(os.path.dirname(__file__), '../../.env')
if os.path.exists(project_root_env):
    load_dotenv(project_root_env)
else:
    load_dotenv()


class Config:
    """Flask 配置类"""

    # 存储后端固定为 local（Neo4j + Qdrant）
    GRAPH_BACKEND = 'local'
    VECTOR_BACKEND = os.environ.get('VECTOR_BACKEND', 'qdrant').lower()

    SECRET_KEY = os.environ.get('SECRET_KEY', 'minifish-secret-key')
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'

    JSON_AS_ASCII = False

    # LLM 配置（OpenAI 兼容）
    LLM_API_KEY = os.environ.get('LLM_API_KEY')
    LLM_BASE_URL = os.environ.get('LLM_BASE_URL', 'https://api.openai.com/v1')
    LLM_MODEL_NAME = os.environ.get('LLM_MODEL_NAME', 'gpt-4o-mini')

    # 结构化抽取 LLM（默认复用主 LLM 配置）
    EXTRACT_API_KEY = os.environ.get('EXTRACT_API_KEY') or LLM_API_KEY
    EXTRACT_BASE_URL = os.environ.get('EXTRACT_BASE_URL') or LLM_BASE_URL
    EXTRACT_MODEL_NAME = os.environ.get('EXTRACT_MODEL_NAME') or LLM_MODEL_NAME

    # Embedding 配置
    EMBEDDING_API_KEY = os.environ.get('EMBEDDING_API_KEY') or LLM_API_KEY
    EMBEDDING_BASE_URL = os.environ.get('EMBEDDING_BASE_URL') or LLM_BASE_URL
    EMBEDDING_MODEL_NAME = os.environ.get('EMBEDDING_MODEL_NAME', 'text-embedding-3-small')

    # Neo4j
    NEO4J_URI = os.environ.get('NEO4J_URI', 'bolt://localhost:7687')
    NEO4J_USER = os.environ.get('NEO4J_USER', 'neo4j')
    NEO4J_PASSWORD = os.environ.get('NEO4J_PASSWORD', 'minifish')
    NEO4J_DATABASE = os.environ.get('NEO4J_DATABASE', 'neo4j')

    # Qdrant
    QDRANT_URL = os.environ.get('QDRANT_URL', 'http://localhost:6333')
    QDRANT_API_KEY = os.environ.get('QDRANT_API_KEY')
    QDRANT_COLLECTION_CHUNKS = os.environ.get('QDRANT_COLLECTION_CHUNKS', 'minifish_chunks')

    # 上传
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '../uploads')
    ALLOWED_EXTENSIONS = {'pdf', 'md', 'txt', 'markdown'}

    # 文本分块
    DEFAULT_CHUNK_SIZE = 500
    DEFAULT_CHUNK_OVERLAP = 50

    # 并发：图谱抽取 / 人设生成
    EXTRACTION_CONCURRENCY = int(os.environ.get('EXTRACTION_CONCURRENCY', '8'))
    PERSONA_CONCURRENCY = int(os.environ.get('PERSONA_CONCURRENCY', '5'))

    @classmethod
    def validate(cls):
        errors = []
        if not cls.LLM_API_KEY:
            errors.append("LLM_API_KEY 未配置")
        if not cls.NEO4J_PASSWORD:
            errors.append("NEO4J_PASSWORD 未配置")
        if cls.VECTOR_BACKEND not in {"qdrant", "none"}:
            errors.append("VECTOR_BACKEND 仅支持 qdrant 或 none")
        return errors
