"""文本处理：分块 / 预处理"""

import re
from typing import List
from ..utils.file_parser import FileParser, split_text_into_chunks


class TextProcessor:
    @staticmethod
    def extract_from_files(file_paths: List[str]) -> str:
        return FileParser.extract_from_multiple(file_paths)

    @staticmethod
    def split_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        return split_text_into_chunks(text, chunk_size, overlap)

    @staticmethod
    def preprocess_text(text: str) -> str:
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        text = re.sub(r'\n{3,}', '\n\n', text)
        lines = [line.strip() for line in text.split('\n')]
        return '\n'.join(lines).strip()
