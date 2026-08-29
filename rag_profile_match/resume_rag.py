"""
1. Document Processing Pipeline
- Load resumes using file system tools from Milestone 1
- Chunk documents intelligently (preserve sections like Education, Experience)
- Generate embeddings using OpenAI/Cohere/HuggingFace models
- Store in vector database (ChromaDB, Pinecone, or Weaviate)

2. Metadata Extraction
- Extract key fields: Name, Skills, Experience Years, Education
- Store metadata alongside embeddings for filtering

This module defines the batch metadata extraction, section-aware chunking,
and hybrid dense+sparse embedding/indexing building blocks. It has no
top-level execution — see rag_analysis.ipynb for the actual pipeline run.
"""

import re
import uuid
from pathlib import Path
from typing import Literal, cast

from fastembed import SparseTextEmbedding
from langchain.chat_models import init_chat_model
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import LanguageModelInput
from langchain_core.runnables import Runnable
from langchain_openai import OpenAIEmbeddings
from pydantic import BaseModel, Field, SecretStr
from qdrant_client import models as qdrant_models

import config
from fs_tools import list_files, read_file
from utils import logger

SECTION_HEADING_PATTERN = re.compile(
    r"^\s*(SUMMARY|SKILLS|EXPERIENCE|EDUCATION)\s*$", re.MULTILINE
)

EXTRACTION_SYSTEM_PROMPT = (
    "You extract structured fields from resume sections. Normalize skills to "
    "lowercase, canonical names, deduplicated. Estimate total_experience_years "
    "from date ranges in the experience text if not stated explicitly. Infer "
    "education_level from the education text (e.g. 'M.S.' -> Masters, "
    "'B.Tech'/'B.S.' -> Bachelors, 'Ph.D.' -> PhD). Use null for unknown fields."
)


def build_extraction_messages(sections: dict[str, str]) -> list[tuple[str, str]]:
    """Builds a basic chat message array (role, content) for one resume's sections.

    Plain (role, content) tuples rather than a ChatPromptTemplate -- every
    chat model's .invoke()/.batch() accepts this directly as
    LanguageModelInput, with no prompt-template/pipe layer needed for a
    one-shot, non-reusable message per resume.
    """
    return [
        ("system", EXTRACTION_SYSTEM_PROMPT),
        (
            "user",
            f"HEADER:\n{sections['header']}\n\nSKILLS:\n{sections['skills']}\n\n"
            f"EXPERIENCE:\n{sections['experience']}\n\nEDUCATION:\n{sections['education']}",
        ),
    ]


class ResumeFields(BaseModel):
    """LLM-extracted metadata fields that require reasoning, not regex."""

    candidate_name: str | None = Field(
        default=None, description="Full name of the candidate, from the header text"
    )
    skills: list[str] = Field(
        default_factory=list,
        description=(
            "Normalized skills list extracted from skills + experience text. "
            "Lowercase, deduplicated, canonical names (e.g. 'python', 'aws', 'apache spark')."
        ),
    )
    total_experience_years: float | None = Field(
        default=None, description="Total years of professional experience, estimated from experience dates"
    )
    education_level: Literal["High School", "Diploma", "Bachelors", "Masters", "PhD", "Other"] | None = Field(
        default=None, description="Highest education level attained, inferred from education text"
    )


def split_resume_sections(text: str) -> dict[str, str]:
    """Splits resume text into header/skills/experience/education sections.

    Resumes follow a consistent all-caps heading format (SUMMARY, SKILLS,
    EXPERIENCE, EDUCATION). SUMMARY's content is folded into `header` since
    it belongs with the name/title/contact block rather than standing alone.
    If no known heading is found, everything falls into `header`.
    """
    sections = {"header": "", "skills": "", "experience": "", "education": ""}

    matches = list(SECTION_HEADING_PATTERN.finditer(text))
    if not matches:
        sections["header"] = text.strip()
        return sections

    sections["header"] = text[: matches[0].start()].strip()

    for i, match in enumerate(matches):
        heading = match.group(1)
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()

        if heading == "SUMMARY":
            sections["header"] = f"{sections['header']}\n\n{content}".strip()
        elif heading == "SKILLS":
            sections["skills"] = content
        elif heading == "EXPERIENCE":
            sections["experience"] = content
        elif heading == "EDUCATION":
            sections["education"] = content

    return sections


def infer_dept(relative_path: str) -> str:
    """Infers the department from a resume's path relative to root_dir/.

    list_files() (fs_tools.py) reports paths relative to ROOT_DIR, so a
    resume under resumes/<dept>/... arrives as ("resumes", "<dept>", ...).
    A file sitting directly under resumes/ (no subfolder), such as
    resume_john_doe.pdf, arrives as just ("resumes", "<file>") and belongs
    to no department.
    """
    parts = Path(relative_path).parts
    return parts[1] if len(parts) > 2 else "general"


def build_extraction_model() -> Runnable[LanguageModelInput, ResumeFields]:
    """Builds the OpenRouter chat model for structured metadata extraction.

    `with_structured_output` is typed as returning `Runnable[LanguageModelInput,
    dict[str, Any] | BaseModel]` regardless of the schema passed in -- it isn't
    generic over the concrete schema type. Passing the ResumeFields class (not
    include_raw=True, not a dict/JSON schema) always yields a ResumeFields
    instance at runtime, so the cast narrows that back to the real type.
    """
    model = init_chat_model(
        model=config.EXTRACTION_MODEL_NAME,
        model_provider=config.EXTRACTION_MODEL_PROVIDER,
    )
    structured_model = model.with_structured_output(ResumeFields).with_retry(
        stop_after_attempt=config.EXTRACTION_MAX_RETRIES
    )
    return cast(Runnable[LanguageModelInput, ResumeFields], structured_model)


def discover_resume_files() -> list[dict]:
    """Lists every resume file under root_dir/resumes via the sandboxed fs tool."""
    return list_files.invoke({"directory": "resumes"})


def extract_fields_batch(
    file_entries: list[dict],
    extraction_model: Runnable[LanguageModelInput, ResumeFields] | None = None,
) -> list[dict]:
    """Reads, section-splits, and batch-extracts metadata for a list of resume files.

    Processes file_entries in chunks of config.EXTRACTION_BATCH_SIZE, issuing
    one concurrent `extraction_model.batch(prompts, config={"max_concurrency": ...})`
    call per chunk rather than one LLM call at a time -- the standard
    LangChain batching interface every chat model implements, including
    OpenRouter's (`init_chat_model(model, model_provider="openrouter")`).

    `return_exceptions=True` is passed to `.batch()` so one resume's
    extraction failure surfaces as an exception object in that resume's slot
    instead of aborting the whole batch -- the other resumes in the same
    batch still get their real extracted fields.
    """
    extraction_model = extraction_model or build_extraction_model()
    records: list[dict] = []

    for batch_start in range(0, len(file_entries), config.EXTRACTION_BATCH_SIZE):
        batch = file_entries[batch_start : batch_start + config.EXTRACTION_BATCH_SIZE]
        batch_num = batch_start // config.EXTRACTION_BATCH_SIZE + 1
        logger.info(f"Extracting metadata for batch {batch_num} ({len(batch)} files)")

        readable: list[tuple[dict, dict]] = []
        for entry in batch:
            result = read_file.invoke({"filepath": entry["path"]})
            if not result["success"]:
                logger.error(f"Could not read '{entry['path']}': {result['error']}")
                continue
            readable.append((entry, split_resume_sections(result["content"])))

        prompts: list[LanguageModelInput] = [build_extraction_messages(sections) for _, sections in readable]
        results = extraction_model.batch(
            prompts,
            config={"max_concurrency": config.EXTRACTION_MAX_CONCURRENCY},
            return_exceptions=True,
        )

        for (entry, sections), fields in zip(readable, results):
            if isinstance(fields, BaseException):
                logger.error(f"Extraction failed for '{entry['path']}': {fields}")
                fields = ResumeFields()
            records.append(
                {
                    "file_path": entry["path"],
                    "file_name": entry["name"],
                    "dept": infer_dept(entry["path"]),
                    "candidate_name": fields.candidate_name,
                    "skills": fields.skills,
                    "total_experience_years": fields.total_experience_years,
                    "education_level": fields.education_level,
                    "sections": sections,
                }
            )

    return records


def build_embedding_model() -> Embeddings:
    """Builds the dense embedding client, via OpenRouter's OpenAI-compatible
    /embeddings endpoint (langchain-openrouter itself exports no embeddings
    class, only ChatOpenRouter).
    """
    return OpenAIEmbeddings(
        model=config.EMBEDDING_MODEL_NAME,
        base_url=config.OPENROUTER_BASE_URL,
        api_key=SecretStr(config.OPENROUTER_API_KEY),
    )


def build_sparse_embedding_model() -> SparseTextEmbedding:
    """Builds the sparse (lexical/keyword) embedding model for hybrid search.

    Uses fastembed's BM25 model ("Qdrant/bm25"): deterministic term-frequency
    sparse vectors. Qdrant applies IDF weighting server-side (see the
    Modifier.IDF sparse vector config in ensure_qdrant_collection), so no
    corpus-wide document-frequency stats need to be computed here.
    """
    return SparseTextEmbedding(model_name="Qdrant/bm25")


def embed_chunks(
    chunks: list[dict],
    embedding_model: Embeddings | None = None,
    sparse_model: SparseTextEmbedding | None = None,
) -> list[dict]:
    """Embeds each chunk's page_content with both a dense and a sparse model.

    Batch-embeds once per model rather than one call per chunk: dense via
    `embedding_model.embed_documents(...)`, sparse via
    `sparse_model.embed(...)`. Returns chunks with "dense_embedding"
    (list[float]) and "sparse_embedding" ({"indices": list[int], "values":
    list[float]}) added, ready for upsert_chunks.
    """
    embedding_model = embedding_model or build_embedding_model()
    sparse_model = sparse_model or build_sparse_embedding_model()

    texts = [chunk["page_content"] for chunk in chunks]
    dense_vectors = embedding_model.embed_documents(texts)
    sparse_vectors = list(sparse_model.embed(texts))

    embedded = []
    for chunk, dense_vector, sparse_vector in zip(chunks, dense_vectors, sparse_vectors):
        embedded.append(
            {
                **chunk,
                "dense_embedding": dense_vector,
                "sparse_embedding": {
                    "indices": sparse_vector.indices.tolist(),
                    "values": sparse_vector.values.tolist(),
                },
            }
        )
    return embedded


def ensure_qdrant_collection(vector_size: int) -> None:
    """Creates the hybrid (dense + sparse) Qdrant collection if it doesn't
    already exist, and ensures payload indexes for metadata filtering.

    Two named vectors per point: "dense" (size=vector_size, cosine distance)
    and "sparse" (no fixed size; Modifier.IDF applies BM25-style IDF
    weighting server-side over fastembed's raw term-frequency vectors).
    Payload indexes on metadata.dept/education_level/skills let a later
    hybrid query filter (e.g. "backend only") without a full scan.
    """
    if not config.client.collection_exists(config.QDRANT_COLLECTION_NAME):
        config.client.create_collection(
            collection_name=config.QDRANT_COLLECTION_NAME,
            vectors_config={
                "dense": qdrant_models.VectorParams(
                    size=vector_size, distance=qdrant_models.Distance.COSINE
                ),
            },
            sparse_vectors_config={
                "sparse": qdrant_models.SparseVectorParams(
                    modifier=qdrant_models.Modifier.IDF
                ),
            },
        )

    for field_name in ("metadata.dept", "metadata.education_level", "metadata.skills"):
        config.client.create_payload_index(
            collection_name=config.QDRANT_COLLECTION_NAME,
            field_name=field_name,
            field_schema=qdrant_models.PayloadSchemaType.KEYWORD,
        )


def _stable_point_id(metadata: dict) -> str:
    """Derives a deterministic point ID from a chunk's file_path + section,
    so re-running the pipeline on the same resumes upserts in place instead
    of creating duplicate points.
    """
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{metadata['file_path']}::{metadata['section']}"))


def upsert_chunks(embedded_chunks: list[dict]) -> None:
    """Upserts embedded chunks into Qdrant as hybrid dense+sparse points.

    Each point's payload is {"page_content", "metadata"} -- the same shape
    already used in chunks.json -- and its vector carries both the "dense"
    and "sparse" named vectors for later RRF fusion at query time.
    """
    points = [
        qdrant_models.PointStruct(
            id=_stable_point_id(chunk["metadata"]),
            vector={
                "dense": chunk["dense_embedding"],
                "sparse": qdrant_models.SparseVector(
                    indices=chunk["sparse_embedding"]["indices"],
                    values=chunk["sparse_embedding"]["values"],
                ),
            },
            payload={"page_content": chunk["page_content"], "metadata": chunk["metadata"]},
        )
        for chunk in embedded_chunks
    ]
    config.client.upsert(collection_name=config.QDRANT_COLLECTION_NAME, points=points)


def build_chunks(records: list[dict]) -> list[dict]:
    """Builds section-level chunk documents (page_content + metadata) from extraction records."""
    chunks = []
    for record in records:
        base_metadata = {
            "file_path": record["file_path"],
            "file_name": record["file_name"],
            "dept": record["dept"],
            "candidate_name": record["candidate_name"],
            "education_level": record["education_level"],
            "skills": record["skills"],
        }
        for section_name in ("header", "skills", "experience", "education"):
            content = record["sections"].get(section_name, "").strip()
            if not content:
                continue
            chunks.append(
                {
                    "page_content": content,
                    "metadata": {**base_metadata, "section": section_name},
                }
            )
    return chunks
