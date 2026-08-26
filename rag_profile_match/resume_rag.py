"""
1. Document Processing Pipeline
- Load resumes using file system tools from Milestone 1
- Chunk documents intelligently (preserve sections like Education, Experience)
- Generate embeddings using OpenAI/Cohere/HuggingFace models
- Store in vector database (ChromaDB, Pinecone, or Weaviate)

2. Metadata Extraction
- Extract key fields: Name, Skills, Experience Years, Education
- Store metadata alongside embeddings for filtering
"""