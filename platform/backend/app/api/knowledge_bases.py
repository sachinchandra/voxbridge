"""Knowledge Base management API routes.

CRUD for knowledge bases + document upload with automatic
chunking, embedding, and vector indexing for RAG.
"""

from __future__ import annotations

import asyncio
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from loguru import logger

from app.middleware.auth import get_current_customer
from app.models.database import (
    Customer,
    DocumentResponse,
    DocumentStatus,
    DocumentUploadResponse,
    KnowledgeBaseCreate,
    KnowledgeBaseResponse,
    KnowledgeBaseUpdate,
)
from app.services.database import (
    create_document,
    create_knowledge_base,
    delete_document,
    delete_knowledge_base,
    get_knowledge_base,
    list_documents,
    list_knowledge_bases,
    store_document_chunks,
    update_document_status,
    update_knowledge_base,
    update_knowledge_base_counts,
)

router = APIRouter(prefix="/knowledge-bases", tags=["Knowledge Bases"])

# Plan-based KB limits
_KB_LIMITS = {
    "free": 1,
    "pro": 5,
    "enterprise": 50,
}

_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
_ALLOWED_TYPES = {
    "text/plain",
    "text/markdown",
    "text/csv",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def _kb_to_response(kb) -> KnowledgeBaseResponse:
    """Convert KB model to response."""
    return KnowledgeBaseResponse(
        id=kb.id,
        name=kb.name,
        description=kb.description,
        embedding_model=kb.embedding_model,
        chunk_size=kb.chunk_size,
        chunk_overlap=kb.chunk_overlap,
        document_count=kb.document_count,
        total_chunks=kb.total_chunks,
        status=kb.status,
        created_at=kb.created_at,
        updated_at=kb.updated_at,
    )


def _doc_to_response(doc) -> DocumentResponse:
    """Convert Document model to response."""
    return DocumentResponse(
        id=doc.id,
        knowledge_base_id=doc.knowledge_base_id,
        filename=doc.filename,
        content_type=doc.content_type,
        source_url=doc.source_url,
        file_size_bytes=doc.file_size_bytes,
        chunk_count=doc.chunk_count,
        status=doc.status,
        error_message=doc.error_message,
        created_at=doc.created_at,
    )


# ──────────────────────────────────────────────────────────────────
# Knowledge Base CRUD
# ──────────────────────────────────────────────────────────────────

@router.post("", response_model=KnowledgeBaseResponse, status_code=status.HTTP_201_CREATED)
async def create_new_knowledge_base(
    body: KnowledgeBaseCreate,
    customer: Customer = Depends(get_current_customer),
):
    """Create a new knowledge base."""
    # Check limits
    existing = list_knowledge_bases(customer.id)
    limit = _KB_LIMITS.get(customer.plan.value, 1)
    if len(existing) >= limit:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Knowledge base limit reached ({limit}) for your {customer.plan.value} plan.",
        )

    kb = create_knowledge_base(customer.id, body.model_dump())
    return _kb_to_response(kb)


@router.get("", response_model=list[KnowledgeBaseResponse])
async def list_all_knowledge_bases(
    customer: Customer = Depends(get_current_customer),
):
    """List all knowledge bases."""
    kbs = list_knowledge_bases(customer.id)
    return [_kb_to_response(kb) for kb in kbs]


@router.get("/{kb_id}", response_model=KnowledgeBaseResponse)
async def get_knowledge_base_by_id(
    kb_id: str,
    customer: Customer = Depends(get_current_customer),
):
    """Get a knowledge base by ID."""
    kb = get_knowledge_base(kb_id, customer.id)
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    return _kb_to_response(kb)


@router.patch("/{kb_id}", response_model=KnowledgeBaseResponse)
async def update_knowledge_base_by_id(
    kb_id: str,
    body: KnowledgeBaseUpdate,
    customer: Customer = Depends(get_current_customer),
):
    """Update a knowledge base."""
    existing = get_knowledge_base(kb_id, customer.id)
    if not existing:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    updated = update_knowledge_base(
        kb_id, customer.id, body.model_dump(exclude_unset=True)
    )
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update knowledge base")
    return _kb_to_response(updated)


@router.delete("/{kb_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_base_by_id(
    kb_id: str,
    customer: Customer = Depends(get_current_customer),
):
    """Delete a knowledge base and all its documents."""
    success = delete_knowledge_base(kb_id, customer.id)
    if not success:
        raise HTTPException(status_code=404, detail="Knowledge base not found")


# ──────────────────────────────────────────────────────────────────
# Document upload + management
# ──────────────────────────────────────────────────────────────────

@router.get("/{kb_id}/documents", response_model=list[DocumentResponse])
async def list_kb_documents(
    kb_id: str,
    customer: Customer = Depends(get_current_customer),
):
    """List all documents in a knowledge base."""
    kb = get_knowledge_base(kb_id, customer.id)
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    docs = list_documents(kb_id, customer.id)
    return [_doc_to_response(doc) for doc in docs]


@router.post(
    "/{kb_id}/documents",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    kb_id: str,
    file: UploadFile = File(...),
    customer: Customer = Depends(get_current_customer),
):
    """Upload a document to a knowledge base.

    Accepts: .txt, .md, .csv, .pdf, .docx (max 10MB).
    The document is automatically chunked, embedded, and indexed.
    """
    # Verify KB exists
    kb = get_knowledge_base(kb_id, customer.id)
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    # Validate file type
    content_type = file.content_type or ""
    filename = file.filename or "document.txt"

    if content_type not in _ALLOWED_TYPES and not any(
        filename.endswith(ext) for ext in [".txt", ".md", ".csv", ".pdf", ".docx"]
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {content_type}. Allowed: .txt, .md, .csv, .pdf, .docx",
        )

    # Read content
    content = await file.read()
    if len(content) > _MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size: {_MAX_FILE_SIZE // (1024*1024)}MB",
        )

    # Create document record
    doc = create_document({
        "knowledge_base_id": kb_id,
        "customer_id": customer.id,
        "filename": filename,
        "content_type": content_type,
        "file_size_bytes": len(content),
        "status": "processing",
    })

    # Process in background
    asyncio.create_task(
        _process_document(
            doc_id=doc.id,
            kb_id=kb_id,
            content=content,
            content_type=content_type,
            filename=filename,
            chunk_size=kb.chunk_size,
            chunk_overlap=kb.chunk_overlap,
            embedding_model=kb.embedding_model,
        )
    )

    return DocumentUploadResponse(
        id=doc.id,
        filename=filename,
        status=DocumentStatus.PROCESSING,
        message="Document uploaded and queued for processing",
    )


@router.delete("/{kb_id}/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_kb_document(
    kb_id: str,
    doc_id: str,
    customer: Customer = Depends(get_current_customer),
):
    """Delete a document from a knowledge base."""
    kb = get_knowledge_base(kb_id, customer.id)
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    success = delete_document(doc_id, customer.id)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")

    # Update KB counts
    update_knowledge_base_counts(kb_id)


# ──────────────────────────────────────────────────────────────────
# Background document processing
# ──────────────────────────────────────────────────────────────────

async def _process_document(
    doc_id: str,
    kb_id: str,
    content: bytes,
    content_type: str,
    filename: str,
    chunk_size: int,
    chunk_overlap: int,
    embedding_model: str,
) -> None:
    """Process a document: extract text, chunk, embed, and store.

    Runs as a background task after upload.
    """
    from app.services.embeddings import (
        chunk_text,
        extract_text,
        generate_embeddings,
    )

    try:
        logger.info(f"Processing document {doc_id}: {filename}")

        # 1. Extract text
        text = extract_text(content, content_type, filename)
        if not text.strip():
            update_document_status(doc_id, "failed", error_message="No text could be extracted")
            return

        logger.info(f"Extracted {len(text)} chars from {filename}")

        # 2. Chunk text
        chunks = chunk_text(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        if not chunks:
            update_document_status(doc_id, "failed", error_message="No chunks generated")
            return

        logger.info(f"Created {len(chunks)} chunks from {filename}")

        # 3. Generate embeddings
        chunk_texts = [c["content"] for c in chunks]
        embeddings = await generate_embeddings(chunk_texts, model=embedding_model)

        # 4. Store chunks with embeddings
        chunk_records = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            chunk_records.append({
                "id": f"{doc_id}-{i:04d}",
                "document_id": doc_id,
                "knowledge_base_id": kb_id,
                "chunk_index": chunk["chunk_index"],
                "content": chunk["content"],
                "embedding": embedding,
                "token_count": chunk["token_count"],
                "metadata": {"filename": filename, "chunk_index": i},
            })

        stored = store_document_chunks(chunk_records)
        logger.info(f"Stored {stored} chunks for {filename}")

        # 5. Update document status
        update_document_status(doc_id, "ready", chunk_count=stored)

        # 6. Update KB counts
        update_knowledge_base_counts(kb_id)

        logger.info(f"Document {doc_id} processing complete: {stored} chunks")

    except Exception as e:
        logger.error(f"Document processing error for {doc_id}: {e}")
        update_document_status(doc_id, "failed", error_message=str(e))
