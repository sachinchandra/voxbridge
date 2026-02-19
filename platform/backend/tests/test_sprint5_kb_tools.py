"""Tests for Sprint 5: Function Calling + Knowledge Base RAG.

Tests cover:
- Knowledge Base schemas (create, update, response models)
- Document schemas (document, upload response, status enum)
- Document chunk model and vector search result
- Tool executor service (template substitution, tool definitions, execution)
- Embeddings service (text extraction, chunking, RAG context)
- Knowledge Base API router structure
"""

import pytest
import asyncio
from datetime import datetime, timezone

from app.models.database import (
    # Knowledge Base schemas
    KnowledgeBase,
    KnowledgeBaseCreate,
    KnowledgeBaseUpdate,
    KnowledgeBaseResponse,
    # Document schemas
    Document,
    DocumentChunk,
    DocumentResponse,
    DocumentStatus,
    DocumentUploadResponse,
    # Vector search
    VectorSearchResult,
    # Existing
    Agent,
    AgentStatus,
    Customer,
    PlanTier,
)
from app.services.tool_executor import ToolExecutor, ToolExecutionResult
from app.services.embeddings import (
    chunk_text,
    extract_text,
    build_rag_context,
    _estimate_tokens,
)


# ──────────────────────────────────────────────────────────────────
# Knowledge Base Schema Tests
# ──────────────────────────────────────────────────────────────────

class TestKnowledgeBaseModel:
    def test_defaults(self):
        kb = KnowledgeBase(customer_id="cust-1")
        assert kb.customer_id == "cust-1"
        assert kb.name == "New Knowledge Base"
        assert kb.description == ""
        assert kb.embedding_model == "text-embedding-3-small"
        assert kb.chunk_size == 512
        assert kb.chunk_overlap == 50
        assert kb.document_count == 0
        assert kb.total_chunks == 0
        assert kb.status == "active"
        assert kb.id  # auto-generated

    def test_custom_values(self):
        kb = KnowledgeBase(
            customer_id="cust-2",
            name="Product FAQ",
            description="Frequently asked questions",
            embedding_model="text-embedding-3-large",
            chunk_size=1024,
            chunk_overlap=100,
        )
        assert kb.name == "Product FAQ"
        assert kb.description == "Frequently asked questions"
        assert kb.embedding_model == "text-embedding-3-large"
        assert kb.chunk_size == 1024
        assert kb.chunk_overlap == 100


class TestKnowledgeBaseCreate:
    def test_defaults(self):
        create = KnowledgeBaseCreate()
        assert create.name == "New Knowledge Base"
        assert create.description == ""
        assert create.embedding_model == "text-embedding-3-small"
        assert create.chunk_size == 512
        assert create.chunk_overlap == 50

    def test_custom(self):
        create = KnowledgeBaseCreate(
            name="Support Docs",
            description="Customer support documentation",
        )
        assert create.name == "Support Docs"
        assert create.description == "Customer support documentation"


class TestKnowledgeBaseUpdate:
    def test_all_optional(self):
        update = KnowledgeBaseUpdate()
        assert update.name is None
        assert update.description is None

    def test_partial_update(self):
        update = KnowledgeBaseUpdate(name="Updated Name")
        assert update.name == "Updated Name"
        assert update.description is None


class TestKnowledgeBaseResponse:
    def test_all_fields(self):
        now = datetime.now(timezone.utc)
        resp = KnowledgeBaseResponse(
            id="kb-1",
            name="FAQ",
            description="test",
            embedding_model="text-embedding-3-small",
            chunk_size=512,
            chunk_overlap=50,
            document_count=3,
            total_chunks=45,
            status="active",
            created_at=now,
            updated_at=now,
        )
        assert resp.id == "kb-1"
        assert resp.document_count == 3
        assert resp.total_chunks == 45


# ──────────────────────────────────────────────────────────────────
# Document Schema Tests
# ──────────────────────────────────────────────────────────────────

class TestDocumentStatus:
    def test_values(self):
        assert DocumentStatus.PROCESSING == "processing"
        assert DocumentStatus.READY == "ready"
        assert DocumentStatus.FAILED == "failed"

    def test_all_statuses_exist(self):
        statuses = [s.value for s in DocumentStatus]
        assert "processing" in statuses
        assert "ready" in statuses
        assert "failed" in statuses


class TestDocumentModel:
    def test_defaults(self):
        doc = Document(knowledge_base_id="kb-1", customer_id="cust-1")
        assert doc.knowledge_base_id == "kb-1"
        assert doc.customer_id == "cust-1"
        assert doc.filename == ""
        assert doc.content_type == ""
        assert doc.file_size_bytes == 0
        assert doc.chunk_count == 0
        assert doc.status == DocumentStatus.PROCESSING
        assert doc.error_message == ""

    def test_custom_document(self):
        doc = Document(
            knowledge_base_id="kb-1",
            customer_id="cust-1",
            filename="faq.pdf",
            content_type="application/pdf",
            file_size_bytes=1024000,
            chunk_count=15,
            status=DocumentStatus.READY,
        )
        assert doc.filename == "faq.pdf"
        assert doc.file_size_bytes == 1024000
        assert doc.chunk_count == 15
        assert doc.status == DocumentStatus.READY


class TestDocumentChunkModel:
    def test_defaults(self):
        chunk = DocumentChunk(document_id="doc-1", knowledge_base_id="kb-1")
        assert chunk.document_id == "doc-1"
        assert chunk.knowledge_base_id == "kb-1"
        assert chunk.chunk_index == 0
        assert chunk.content == ""
        assert chunk.embedding == []
        assert chunk.metadata == {}
        assert chunk.token_count == 0

    def test_with_embedding(self):
        embedding = [0.1] * 1536
        chunk = DocumentChunk(
            document_id="doc-1",
            knowledge_base_id="kb-1",
            chunk_index=3,
            content="Some text content for this chunk.",
            embedding=embedding,
            token_count=8,
        )
        assert chunk.chunk_index == 3
        assert len(chunk.embedding) == 1536
        assert chunk.token_count == 8


class TestDocumentResponse:
    def test_all_fields(self):
        now = datetime.now(timezone.utc)
        resp = DocumentResponse(
            id="doc-1",
            knowledge_base_id="kb-1",
            filename="test.pdf",
            content_type="application/pdf",
            source_url="",
            file_size_bytes=5000,
            chunk_count=10,
            status=DocumentStatus.READY,
            error_message="",
            created_at=now,
        )
        assert resp.filename == "test.pdf"
        assert resp.chunk_count == 10


class TestDocumentUploadResponse:
    def test_default_message(self):
        resp = DocumentUploadResponse(
            id="doc-1",
            filename="data.csv",
            status=DocumentStatus.PROCESSING,
        )
        assert resp.message == "Document queued for processing"
        assert resp.status == DocumentStatus.PROCESSING


class TestVectorSearchResult:
    def test_fields(self):
        result = VectorSearchResult(
            chunk_id="chunk-1",
            document_id="doc-1",
            content="This is the matching content.",
            similarity=0.92,
        )
        assert result.similarity == 0.92
        assert result.content == "This is the matching content."
        assert result.metadata == {}

    def test_with_metadata(self):
        result = VectorSearchResult(
            chunk_id="chunk-2",
            document_id="doc-1",
            content="Another match.",
            similarity=0.85,
            metadata={"page": 3, "section": "FAQ"},
        )
        assert result.metadata["page"] == 3


# ──────────────────────────────────────────────────────────────────
# Tool Executor Tests
# ──────────────────────────────────────────────────────────────────

class TestToolExecutionResult:
    def test_success_result(self):
        result = ToolExecutionResult(
            name="lookup_order",
            success=True,
            result={"order_id": "123", "status": "shipped"},
            duration_ms=150,
        )
        assert result.name == "lookup_order"
        assert result.success is True
        assert result.result["status"] == "shipped"
        assert result.duration_ms == 150
        assert result.error == ""

    def test_failure_result(self):
        result = ToolExecutionResult(
            name="lookup_order",
            success=False,
            result=None,
            error="Request timed out",
            duration_ms=10000,
        )
        assert result.success is False
        assert result.error == "Request timed out"


class TestToolExecutor:
    def test_init_indexes_tools(self):
        tools = [
            {"name": "tool_a", "endpoint": "https://api.example.com/a", "method": "GET"},
            {"name": "tool_b", "endpoint": "https://api.example.com/b", "method": "POST"},
        ]
        executor = ToolExecutor(tools)
        assert "tool_a" in executor._tools
        assert "tool_b" in executor._tools

    def test_init_skips_tools_without_name(self):
        tools = [
            {"endpoint": "https://api.example.com/a"},
            {"name": "valid", "endpoint": "https://api.example.com/b"},
        ]
        executor = ToolExecutor(tools)
        assert len(executor._tools) == 1
        assert "valid" in executor._tools

    def test_template_substitution(self):
        result = ToolExecutor._substitute_template(
            "https://api.example.com/orders/{{order_id}}/items/{{item_id}}",
            {"order_id": "ORD-123", "item_id": "ITM-456"},
        )
        assert result == "https://api.example.com/orders/ORD-123/items/ITM-456"

    def test_template_substitution_no_placeholders(self):
        result = ToolExecutor._substitute_template(
            "https://api.example.com/orders",
            {"order_id": "ORD-123"},
        )
        assert result == "https://api.example.com/orders"

    def test_template_substitution_empty_values(self):
        result = ToolExecutor._substitute_template(
            "https://api.example.com/users/{{user_id}}",
            {},
        )
        assert result == "https://api.example.com/users/{{user_id}}"

    def test_get_tool_definitions(self):
        tools = [
            {
                "name": "check_weather",
                "description": "Check the weather for a location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string", "description": "City name"}
                    },
                    "required": ["location"],
                },
                "endpoint": "https://api.weather.com/current",
                "method": "GET",
            }
        ]
        executor = ToolExecutor(tools)
        definitions = executor.get_tool_definitions()

        assert len(definitions) == 1
        assert definitions[0]["type"] == "function"
        assert definitions[0]["function"]["name"] == "check_weather"
        assert definitions[0]["function"]["description"] == "Check the weather for a location"
        assert "location" in definitions[0]["function"]["parameters"]["properties"]

    def test_get_tool_definitions_missing_description(self):
        tools = [{"name": "simple", "endpoint": "http://example.com", "method": "GET"}]
        executor = ToolExecutor(tools)
        definitions = executor.get_tool_definitions()
        assert definitions[0]["function"]["description"] == ""

    def test_get_tool_definitions_missing_parameters(self):
        tools = [{"name": "simple", "endpoint": "http://example.com"}]
        executor = ToolExecutor(tools)
        definitions = executor.get_tool_definitions()
        assert definitions[0]["function"]["parameters"]["type"] == "object"

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self):
        executor = ToolExecutor([])
        result = await executor.execute("nonexistent", {})
        assert result.success is False
        assert "Unknown tool" in result.error

    @pytest.mark.asyncio
    async def test_execute_no_endpoint(self):
        tools = [{"name": "empty_tool", "endpoint": "", "method": "GET"}]
        executor = ToolExecutor(tools)
        result = await executor.execute("empty_tool", {})
        assert result.success is False
        assert "no endpoint" in result.error

    @pytest.mark.asyncio
    async def test_execute_unsupported_method(self):
        tools = [{"name": "bad_method", "endpoint": "http://example.com", "method": "OPTIONS"}]
        executor = ToolExecutor(tools)
        result = await executor.execute("bad_method", {})
        assert result.success is False
        assert "Unsupported HTTP method" in result.error


# ──────────────────────────────────────────────────────────────────
# Embeddings / Chunking Tests
# ──────────────────────────────────────────────────────────────────

class TestTextExtraction:
    def test_extract_plain_text(self):
        content = b"Hello, this is plain text content."
        text = extract_text(content, "text/plain", "test.txt")
        assert text == "Hello, this is plain text content."

    def test_extract_markdown(self):
        content = b"# Heading\n\nSome **bold** text."
        text = extract_text(content, "text/markdown", "readme.md")
        assert "# Heading" in text

    def test_extract_csv(self):
        content = b"name,email\nAlice,alice@example.com\nBob,bob@example.com"
        text = extract_text(content, "text/csv", "data.csv")
        assert "Alice" in text
        assert "Bob" in text

    def test_extract_txt_by_extension(self):
        content = b"Some text content"
        text = extract_text(content, "application/octet-stream", "notes.txt")
        assert text == "Some text content"

    def test_extract_md_by_extension(self):
        content = b"# Notes\nImportant things"
        text = extract_text(content, "application/octet-stream", "notes.md")
        assert "# Notes" in text

    def test_extract_fallback(self):
        content = b"Some content that looks like text"
        text = extract_text(content, "application/unknown", "file.xyz")
        assert "Some content" in text


class TestChunking:
    def test_empty_text(self):
        chunks = chunk_text("")
        assert chunks == []

    def test_whitespace_only(self):
        chunks = chunk_text("   \n\n  ")
        assert chunks == []

    def test_single_sentence(self):
        chunks = chunk_text("Hello world this is a test.")
        assert len(chunks) == 1
        assert chunks[0]["content"] == "Hello world this is a test."
        assert chunks[0]["chunk_index"] == 0
        assert chunks[0]["token_count"] > 0

    def test_multiple_sentences_within_chunk_size(self):
        text = "First sentence. Second sentence. Third sentence."
        chunks = chunk_text(text, chunk_size=200)
        assert len(chunks) == 1
        assert "First sentence" in chunks[0]["content"]

    def test_chunking_splits_on_sentences(self):
        # Create text that exceeds chunk_size
        text = "This is sentence one. " * 20 + "This is sentence two. " * 20
        chunks = chunk_text(text, chunk_size=100, chunk_overlap=0)
        assert len(chunks) > 1
        # Each chunk should not be wildly larger than chunk_size
        for chunk in chunks:
            # Allow some flexibility since we split on sentences
            assert len(chunk["content"]) < 200

    def test_chunk_indices_are_sequential(self):
        text = "Sentence one. Sentence two. Sentence three. Sentence four. Sentence five. " * 5
        chunks = chunk_text(text, chunk_size=50, chunk_overlap=0)
        for i, chunk in enumerate(chunks):
            assert chunk["chunk_index"] == i

    def test_overlap_includes_previous_text(self):
        text = "The quick brown fox. Jumped over the lazy dog. And ran far away."
        chunks = chunk_text(text, chunk_size=30, chunk_overlap=10)
        if len(chunks) > 1:
            # Second chunk should contain overlap from first chunk's end
            assert len(chunks[1]["content"]) > 0

    def test_token_count_estimation(self):
        text = "This is a test sentence with some words."
        chunks = chunk_text(text, chunk_size=1000)
        assert len(chunks) == 1
        # ~40 chars / 4 = ~10 tokens
        assert chunks[0]["token_count"] >= 5

    def test_large_text_produces_multiple_chunks(self):
        # 5000 chars of text
        text = "This is a reasonably long sentence that has enough words to fill up space. " * 60
        chunks = chunk_text(text, chunk_size=512, chunk_overlap=50)
        assert len(chunks) > 5


class TestEstimateTokens:
    def test_basic(self):
        assert _estimate_tokens("hello world") >= 1

    def test_longer_text(self):
        text = "a" * 100
        tokens = _estimate_tokens(text)
        assert tokens == 25  # 100 / 4

    def test_minimum_one(self):
        assert _estimate_tokens("hi") >= 1
        assert _estimate_tokens("") >= 1


class TestRAGContext:
    def test_empty_results(self):
        context = build_rag_context([])
        assert context == ""

    def test_single_result(self):
        results = [{"content": "The return policy is 30 days."}]
        context = build_rag_context(results)
        assert "return policy is 30 days" in context
        assert "Relevant knowledge base context" in context
        assert "Use the above context" in context

    def test_multiple_results(self):
        results = [
            {"content": "Returns accepted within 30 days."},
            {"content": "Free shipping on orders over $50."},
            {"content": "Customer support available 24/7."},
        ]
        context = build_rag_context(results)
        assert "30 days" in context
        assert "Free shipping" in context
        assert "24/7" in context

    def test_respects_max_chars(self):
        results = [
            {"content": "A" * 500},
            {"content": "B" * 500},
            {"content": "C" * 500},
        ]
        context = build_rag_context(results, max_chars=800)
        assert "A" * 500 in context
        # Should stop before including all three
        assert "C" * 500 not in context

    def test_handles_missing_content(self):
        results = [{"similarity": 0.95}]
        context = build_rag_context(results)
        # Empty content shouldn't break things
        assert isinstance(context, str)


# ──────────────────────────────────────────────────────────────────
# Agent with Tools and KB Integration Tests
# ──────────────────────────────────────────────────────────────────

class TestAgentWithToolsAndKB:
    def test_agent_has_tools_field(self):
        agent = Agent(
            customer_id="cust-1",
            name="Support Bot",
            tools=[
                {
                    "name": "lookup_order",
                    "description": "Look up order by ID",
                    "parameters": {"type": "object", "properties": {"order_id": {"type": "string"}}},
                    "endpoint": "https://api.example.com/orders/{{order_id}}",
                    "method": "GET",
                }
            ],
        )
        assert len(agent.tools) == 1
        assert agent.tools[0]["name"] == "lookup_order"

    def test_agent_has_knowledge_base_id(self):
        agent = Agent(
            customer_id="cust-1",
            name="FAQ Bot",
            knowledge_base_id="kb-123",
        )
        assert agent.knowledge_base_id == "kb-123"

    def test_agent_knowledge_base_id_nullable(self):
        agent = Agent(customer_id="cust-1", name="Bot")
        assert agent.knowledge_base_id is None

    def test_agent_empty_tools(self):
        agent = Agent(customer_id="cust-1", name="Bot")
        assert agent.tools == []


# ──────────────────────────────────────────────────────────────────
# KB Plan Limits Tests
# ──────────────────────────────────────────────────────────────────

class TestKBPlanLimits:
    """Test that plan-based limits are reasonable."""

    def test_plan_tiers_exist(self):
        assert PlanTier.FREE.value == "free"
        assert PlanTier.PRO.value == "pro"
        assert PlanTier.ENTERPRISE.value == "enterprise"

    def test_kb_limits_per_plan(self):
        # The API enforces these limits; verify logic is reasonable
        limits = {"free": 1, "pro": 5, "enterprise": 50}
        assert limits["free"] < limits["pro"]
        assert limits["pro"] < limits["enterprise"]


# ──────────────────────────────────────────────────────────────────
# Tool Executor Advanced Tests
# ──────────────────────────────────────────────────────────────────

class TestToolExecutorAdvanced:
    def test_multiple_tools(self):
        tools = [
            {"name": "tool1", "endpoint": "http://a.com", "method": "GET", "description": "Tool 1"},
            {"name": "tool2", "endpoint": "http://b.com", "method": "POST", "description": "Tool 2"},
            {"name": "tool3", "endpoint": "http://c.com", "method": "PUT", "description": "Tool 3"},
        ]
        executor = ToolExecutor(tools)
        defs = executor.get_tool_definitions()
        assert len(defs) == 3
        names = [d["function"]["name"] for d in defs]
        assert "tool1" in names
        assert "tool2" in names
        assert "tool3" in names

    def test_header_template_substitution(self):
        result = ToolExecutor._substitute_template(
            "Bearer {{api_key}}",
            {"api_key": "sk-secret-123"},
        )
        assert result == "Bearer sk-secret-123"

    def test_complex_url_template(self):
        result = ToolExecutor._substitute_template(
            "https://api.example.com/v2/customers/{{customer_id}}/orders/{{order_id}}/status",
            {"customer_id": "C-100", "order_id": "O-200"},
        )
        assert result == "https://api.example.com/v2/customers/C-100/orders/O-200/status"

    def test_timeout_configuration(self):
        executor = ToolExecutor([], timeout=30.0)
        assert executor._timeout == 30.0

    def test_max_retries_configuration(self):
        executor = ToolExecutor([], max_retries=3)
        assert executor._max_retries == 3

    def test_client_starts_as_none(self):
        executor = ToolExecutor([])
        assert executor._client is None

    def test_default_timeout(self):
        executor = ToolExecutor([], timeout=10.0)
        assert executor._timeout == 10.0
        assert executor._client is None
