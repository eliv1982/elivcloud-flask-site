"""
RAG search over FAISS index for ElivCloud FAQ assistant.

Usage:
    python rag_index.py "Чем занимается ElivCloud?"
"""

import os
import sys
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from openai import OpenAI

import faiss

load_dotenv()

DATA_DIR = Path(__file__).parent / "data"
INDEX_PATH = DATA_DIR / "faiss_index.bin"
METADATA_PATH = DATA_DIR / "faqs_metadata.npy"

_index: faiss.IndexFlatIP | None = None
_metadata: np.ndarray | None = None
_client: OpenAI | None = None
_embed_model: str = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set. Add it to .env or environment.")
        _client = OpenAI(api_key=api_key)
    return _client


def _load_index() -> tuple[faiss.IndexFlatIP, np.ndarray]:
    global _index, _metadata
    if _index is None:
        if not INDEX_PATH.exists():
            raise FileNotFoundError(
                f"FAISS index not found at {INDEX_PATH}. Run 'python build_index.py' first."
            )
        _index = faiss.read_index(str(INDEX_PATH))
    if _metadata is None:
        if not METADATA_PATH.exists():
            raise FileNotFoundError(
                f"Metadata not found at {METADATA_PATH}. Run 'python build_index.py' first."
            )
        _metadata = np.load(str(METADATA_PATH), allow_pickle=True)
    return _index, _metadata


def search_knowledge_base(query: str, top_k: int = 4) -> list[dict]:
    client = _get_client()
    index, metadata = _load_index()

    response = client.embeddings.create(input=[query], model=_embed_model)
    query_vector = np.array([response.data[0].embedding], dtype=np.float32)
    faiss.normalize_L2(query_vector)

    scores, indices = index.search(query_vector, top_k)

    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0:
            continue
        doc = metadata[idx]
        results.append(
            {
                "score": float(score),
                "question": str(doc["question"]),
                "answer": str(doc["answer"]),
                "source": str(doc["source"]),
                "kind": str(doc["kind"]),
            }
        )
    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python rag_index.py \"Your question here\"")
        sys.exit(1)

    query = sys.argv[1]
    print(f"Query: {query}\n{'=' * 60}")

    try:
        results = search_knowledge_base(query, top_k=4)
    except (FileNotFoundError, RuntimeError) as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    if not results:
        print("No results found.")
        sys.exit(0)

    for i, r in enumerate(results, 1):
        answer_preview = r["answer"][:200].replace("\n", " ")
        if len(r["answer"]) > 200:
            answer_preview += "..."
        print(f"[{i}] score={r['score']:.4f}  source={r['source']}  kind={r['kind']}")
        print(f"    Q: {r['question']}")
        print(f"    A: {answer_preview}")
        print()
