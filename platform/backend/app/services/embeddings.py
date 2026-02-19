"""Document chunking, embedding, and vector search service.

Handles:
- Text extraction from various file types (TXT, PDF, DOCX)
- Chunking text into overlapping segments
- Generating embeddings via OpenAI's text-embedding API
- Vector search for RAG context injection during calls
"""

from __future__ import annotations

import io
import re
from typing import Any

from loguru import logger

from app.config import settings


# ──────────────────────────────────────────────────────────────────
# Text extraction
# ──────────────────────────────────────────────────────────────────

def extract_text(content: bytes, content_type: str, filename: str = "") -> str:
    """Extract plain text from various document formats.

    Args:
        content: Raw file bytes.
        content_type: MIME type (e.g., "text/plain", "application/pdf").
        filename: Original filename (used for type inference fallback).

    Returns:
        Extracted plain text.
    """
    # Plain text
    if content_type.startswith("text/") or filename.endswith(".txt") or filename.endswith(".md"):
        return content.decode("utf-8", errors="replace")

    # PDF
    if content_type == "application/pdf" or filename.endswith(".pdf"):
        return _extract_pdf(content)

    # DOCX
    if (
        content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        or filename.endswith(".docx")
    ):
        return _extract_docx(content)

    # CSV / TSV
    if content_type == "text/csv" or filename.endswith(".csv"):
        return content.decode("utf-8", errors="replace")

    # Fallback: try as text
    try:
        return content.decode("utf-8", errors="replace")
    except Exception:
        raise ValueError(f"Unsupported content type: {content_type}")


def _extract_pdf(content: bytes) -> str:
    """Extract text from a PDF file."""
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(content))
        text_parts = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)
        return "\n\n".join(text_parts)
    except ImportError:
        logger.warning("pypdf not installed, using basic PDF text extraction")
        # Basic fallback: extract text between stream markers
        text = content.decode("latin-1", errors="replace")
        # Simple heuristic extraction
        return re.sub(r'[^\x20-\x7E\n]', '', text)


def _extract_docx(content: bytes) -> str:
    """Extract text from a DOCX file."""
    try:
        import docx
        doc = docx.Document(io.BytesIO(content))
        return "\n\n".join(para.text for para in doc.paragraphs if para.text.strip())
    except ImportError:
        logger.warning("python-docx not installed, cannot extract DOCX")
        raise ValueError("DOCX support requires python-docx: pip install python-docx")


# ──────────────────────────────────────────────────────────────────
# Chunking
# ──────────────────────────────────────────────────────────────────

def chunk_text(
    text: str,
    chunk_size: int = 512,
    chunk_overlap: int = 50,
) -> list[dict[str, Any]]:
    """Split text into overlapping chunks for embedding.

    Uses sentence-aware chunking to avoid splitting mid-sentence.

    Args:
        text: The full text to chunk.
        chunk_size: Target chunk size in characters.
        chunk_overlap: Overlap between consecutive chunks.

    Returns:
        List of chunk dicts with "content", "chunk_index", "token_count".
    """
    if not text.strip():
        return []

    # Split into sentences (rough heuristic)
    sentences = re.split(r'(?<=[.!?])\s+', text)
    sentences = [s.strip() for s in sentences if s.strip()]

    chunks = []
    current_chunk = ""
    chunk_index = 0

    for sentence in sentences:
        # If adding this sentence exceeds chunk_size, save current and start new
        if current_chunk and len(current_chunk) + len(sentence) + 1 > chunk_size:
            chunks.append({
                "content": current_chunk.strip(),
                "chunk_index": chunk_index,
                "token_count": _estimate_tokens(current_chunk),
            })
            chunk_index += 1

            # Keep overlap from end of previous chunk
            if chunk_overlap > 0:
                overlap_text = current_chunk[-chunk_overlap:]
                current_chunk = overlap_text + " " + sentence
            else:
                current_chunk = sentence
        else:
            if current_chunk:
                current_chunk += " " + sentence
            else:
                current_chunk = sentence

    # Don't forget the last chunk
    if current_chunk.strip():
        chunks.append({
            "content": current_chunk.strip(),
            "chunk_index": chunk_index,
            "token_count": _estimate_tokens(current_chunk),
        })

    return chunks


def _estimate_tokens(text: str) -> int:
    """Rough token count estimation (avg 4 chars per token for English)."""
    return max(1, len(text) // 4)


# ──────────────────────────────────────────────────────────────────
# Embedding
# ──────────────────────────────────────────────────────────────────

async def generate_embeddings(
    texts: list[str],
    model: str = "text-embedding-3-small",
) -> list[list[float]]:
    """Generate embeddings for a list of texts using OpenAI.

    Args:
        texts: List of text strings to embed.
        model: OpenAI embedding model name.

    Returns:
        List of embedding vectors (list of floats).
    """
    if not texts:
        return []

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.openai_api_key)

        # OpenAI embeddings API supports batches up to 2048
        all_embeddings = []
        batch_size = 100

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            response = await client.embeddings.create(
                model=model,
                input=batch,
            )
            batch_embeddings = [item.embedding for item in response.data]
            all_embeddings.extend(batch_embeddings)

        await client.close()
        return all_embeddings

    except ImportError:
        logger.warning("OpenAI not installed, generating mock embeddings")
        # Return zero vectors for development
        return [[0.0] * 1536 for _ in texts]
    except Exception as e:
        logger.error(f"Embedding generation error: {e}")
        raise


async def generate_query_embedding(
    query: str,
    model: str = "text-embedding-3-small",
) -> list[float]:
    """Generate embedding for a single search query."""
    embeddings = await generate_embeddings([query], model=model)
    if embeddings:
        return embeddings[0]
    return [0.0] * 1536


# ──────────────────────────────────────────────────────────────────
# RAG Context Builder
# ──────────────────────────────────────────────────────────────────

def build_rag_context(search_results: list[dict], max_chars: int = 3000) -> str:
    """Build a context string from vector search results for LLM injection.

    Args:
        search_results: Results from vector_search().
        max_chars: Maximum context length.

    Returns:
        Formatted context string to prepend to the system prompt.
    """
    if not search_results:
        return ""

    context_parts = []
    total_chars = 0

    for result in search_results:
        content = result.get("content", "")
        if total_chars + len(content) > max_chars:
            break
        context_parts.append(content)
        total_chars += len(content)

    if not context_parts:
        return ""

    return (
        "\n\n---\nRelevant knowledge base context:\n"
        + "\n---\n".join(context_parts)
        + "\n---\n\nUse the above context to answer the caller's questions when relevant."
    )
