from dataclasses import dataclass
import re

from lingjing_ai.rag.question_type import classify_content_category


@dataclass(frozen=True)
class TextChunk:
    id: str
    document_id: str
    document_name: str
    content: str
    metadata: dict[str, str]


class TextChunker:
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 80) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split(self, document_id: str, document_name: str, text: str) -> list[TextChunk]:
        cleaned = self._clean(text)
        if not cleaned:
            return []

        sections = self._sections(cleaned)
        chunks: list[TextChunk] = []

        for section_path, section_text in sections:
            chunks.extend(
                self._split_section(
                    document_id=document_id,
                    document_name=document_name,
                    section_path=section_path,
                    text=section_text,
                    start_index=len(chunks),
                )
            )
        return chunks

    def _split_section(
        self,
        document_id: str,
        document_name: str,
        section_path: list[str],
        text: str,
        start_index: int,
    ) -> list[TextChunk]:
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
        current = ""
        chunks: list[TextChunk] = []

        for paragraph in paragraphs:
            if not current:
                current = paragraph
                continue
            if len(current) + len(paragraph) + 1 <= self.chunk_size:
                current = f"{current}\n{paragraph}"
            else:
                chunks.extend(self._window(document_id, document_name, current, start_index + len(chunks), section_path))
                current = paragraph

        if current:
            chunks.extend(self._window(document_id, document_name, current, start_index + len(chunks), section_path))
        return chunks

    def _window(
        self,
        document_id: str,
        document_name: str,
        text: str,
        start_index: int,
        section_path: list[str],
    ) -> list[TextChunk]:
        if len(text) <= self.chunk_size:
            return [self._chunk(document_id, document_name, text, start_index, section_path)]

        chunks: list[TextChunk] = []
        step = max(1, self.chunk_size - self.chunk_overlap)
        for offset in range(0, len(text), step):
            piece = text[offset : offset + self.chunk_size].strip()
            if piece:
                chunks.append(self._chunk(document_id, document_name, piece, start_index + len(chunks), section_path))
        return chunks

    def _chunk(
        self,
        document_id: str,
        document_name: str,
        content: str,
        index: int,
        section_path: list[str],
    ) -> TextChunk:
        section_text = " > ".join(section_path)
        section_title = section_path[-1] if section_path else ""
        category = classify_content_category(content, section_text)
        parent_id = self._parent_id(document_id, section_path)
        contextual_content = self._with_context(document_name, section_text, content)
        return TextChunk(
            id=f"{document_id}_chunk_{index}",
            document_id=document_id,
            document_name=document_name,
            content=contextual_content,
            metadata={
                "chunk_index": str(index),
                "section_path": section_text,
                "section_title": section_title,
                "category": category,
                "parent_id": parent_id,
            },
        )

    def _clean(self, text: str) -> str:
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        lines = []
        for line in normalized.split("\n"):
            if re.match(r"^\s{0,3}#{1,6}\s+", line):
                lines.append(line.strip())
            else:
                lines.append(re.sub(r"\s+", " ", line).strip())
        return "\n".join(line for line in lines if line)

    def _sections(self, cleaned: str) -> list[tuple[list[str], str]]:
        sections: list[tuple[list[str], str]] = []
        path_stack: list[tuple[int, str]] = []
        current_lines: list[str] = []

        def flush() -> None:
            if current_lines:
                sections.append(([title for _, title in path_stack], "\n".join(current_lines)))
                current_lines.clear()

        for line in cleaned.splitlines():
            heading = re.match(r"^(#{1,6})\s+(.+)$", line)
            if not heading:
                current_lines.append(line)
                continue

            flush()
            level = len(heading.group(1))
            title = heading.group(2).strip()
            if level == 1:
                path_stack.clear()
                continue
            while path_stack and path_stack[-1][0] >= level:
                path_stack.pop()
            path_stack.append((level, title))

        flush()
        if sections:
            return sections
        return [([], cleaned)]

    def _with_context(self, document_name: str, section_path: str, content: str) -> str:
        if section_path:
            return f"资料：{document_name} / 章节：{section_path}\n{content}"
        return f"资料：{document_name}\n{content}"

    def _parent_id(self, document_id: str, section_path: list[str]) -> str:
        if not section_path:
            return f"{document_id}_section_root"
        safe_path = "_".join(re.sub(r"\W+", "_", title).strip("_") for title in section_path)
        return f"{document_id}_section_{safe_path}"
