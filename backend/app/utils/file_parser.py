"""文件解析工具：PDF / Markdown / TXT"""

import os
from pathlib import Path
from typing import List


class FileParser:
    SUPPORTED_EXTENSIONS = {'.pdf', '.md', '.markdown', '.txt'}

    @classmethod
    def extract_text(cls, file_path: str) -> str:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        suffix = path.suffix.lower()
        if suffix not in cls.SUPPORTED_EXTENSIONS:
            raise ValueError(f"不支持的文件格式: {suffix}")

        if suffix == '.pdf':
            return cls._extract_from_pdf(file_path)
        if suffix in {'.md', '.markdown'}:
            return cls._extract_from_md(file_path)
        if suffix == '.txt':
            return cls._extract_from_txt(file_path)
        raise ValueError(f"无法处理的文件格式: {suffix}")

    @staticmethod
    def _extract_from_pdf(file_path: str) -> str:
        import fitz  # PyMuPDF
        text_parts = []
        with fitz.open(file_path) as doc:
            for page in doc:
                text = page.get_text()
                if text.strip():
                    text_parts.append(text)
        return "\n\n".join(text_parts)

    @staticmethod
    def _extract_from_md(file_path: str) -> str:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()

    @staticmethod
    def _extract_from_txt(file_path: str) -> str:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()

    @classmethod
    def extract_from_multiple(cls, file_paths: List[str]) -> str:
        all_texts = []
        for i, file_path in enumerate(file_paths, 1):
            try:
                text = cls.extract_text(file_path)
                all_texts.append(f"=== 文档 {i}: {Path(file_path).name} ===\n{text}")
            except Exception as e:
                all_texts.append(f"=== 文档 {i}: {file_path} (提取失败: {str(e)}) ===")
        return "\n\n".join(all_texts)


def split_text_into_chunks(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    if len(text) <= chunk_size:
        return [text] if text.strip() else []

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        if end < len(text):
            for sep in ['。', '！', '？', '.\n', '!\n', '?\n', '\n\n', '. ', '! ', '? ']:
                last_sep = text[start:end].rfind(sep)
                if last_sep != -1 and last_sep > chunk_size * 0.3:
                    end = start + last_sep + len(sep)
                    break
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap if end < len(text) else len(text)
    return chunks
