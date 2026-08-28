from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


@dataclass(frozen=True)
class Chunk:
    document: str
    section: str
    text: str
    kind: str


class KnowledgeBase:
    """Local retrieval index over the supplied knowledge base only."""

    def __init__(self, kb_dir: Path) -> None:
        self.chunks = self._load(kb_dir)
        if not self.chunks:
            raise ValueError(f"Knowledge base contains no Markdown documents: {kb_dir}")
        self._texts = [self._retrieval_text(c) for c in self.chunks]
        self._vectorizer = TfidfVectorizer(
            lowercase=True,
            ngram_range=(1, 2),
            sublinear_tf=True,
            token_pattern=r"(?u)\b[\w:-]+\b",
        )
        self._matrix = self._vectorizer.fit_transform(self._texts)

    @staticmethod
    def _load(kb_dir: Path) -> list[Chunk]:
        if not kb_dir.exists():
            raise FileNotFoundError(f"Knowledge-base directory not found: {kb_dir}")
        chunks: list[Chunk] = []
        for path in sorted(kb_dir.rglob("*.md")):
            text = path.read_text(encoding="utf-8")
            parts = re.split(r"\n\s*---\s*\n", text)
            for part in parts:
                lines = part.strip().splitlines()
                if not lines:
                    continue
                headings = [ln.lstrip("#").strip() for ln in lines if ln.startswith("#")]
                section = headings[-1] if headings else path.stem
                chunks.append(
                    Chunk(
                        document=path.relative_to(kb_dir).as_posix(),
                        section=section,
                        text=part.strip(),
                        kind="table" if _contains_table(part) else "section",
                    )
                )
        return chunks

    @staticmethod
    def _retrieval_text(chunk: Chunk) -> str:
        return f"{chunk.document} {chunk.section} {chunk.text}"

    def search(self, query: str, top_k: int = 4) -> list[tuple[Chunk, float]]:
        if top_k <= 0:
            return []
        query = query.strip()
        if not query:
            return []
        scores = cosine_similarity(self._vectorizer.transform([query]), self._matrix)[0]
        ranked = sorted(enumerate(scores), key=lambda x: float(x[1]), reverse=True)
        return [(self.chunks[i], float(score)) for i, score in ranked[:top_k] if score > 0]


def _contains_table(text: str) -> bool:
    return any("|" in line and re.search(r"\|\s*:?-{3,}", line) for line in text.splitlines())
