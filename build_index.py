"""
Build FAISS index from data/ knowledge base for ElivCloud FAQ RAG assistant.

Usage:
    python build_index.py
"""

import json
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


def load_faq_documents(data_dir: Path) -> list[dict]:
    faq_path = data_dir / "faqs.json"
    if not faq_path.exists():
        return []
    with open(faq_path, encoding="utf-8") as f:
        raw = json.load(f)
    docs = []
    for i, item in enumerate(raw):
        docs.append(
            {
                "id": f"faq_{i}",
                "question": item.get("question", ""),
                "answer": item.get("answer", ""),
                "source": item.get("source", "faqs.json"),
                "kind": "faq",
            }
        )
    return docs


def load_txt_documents(data_dir: Path) -> list[dict]:
    docs = []
    idx = 0
    for txt_path in sorted(data_dir.glob("*.txt")):
        raw = txt_path.read_text(encoding="utf-8").strip()
        lines = [ln for ln in raw.splitlines() if ln.strip()]
        if not lines:
            continue
        question = lines[0].strip()
        answer = "\n".join(lines[1:]).strip() if len(lines) > 1 else raw
        if not answer:
            answer = raw
        docs.append(
            {
                "id": f"txt_{idx}",
                "question": question,
                "answer": answer,
                "source": txt_path.name,
                "kind": "txt",
            }
        )
        idx += 1
    return docs


def embed_texts(client: OpenAI, texts: list[str], model: str) -> np.ndarray:
    response = client.embeddings.create(input=texts, model=model)
    vectors = [item.embedding for item in response.data]
    return np.array(vectors, dtype=np.float32)


def build_faiss_index(embeddings: np.ndarray) -> faiss.IndexFlatIP:
    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)
    return index


def main() -> None:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        print("ERROR: OPENAI_API_KEY is not set. Add it to .env or environment.")
        sys.exit(1)

    model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

    faq_docs = load_faq_documents(DATA_DIR)
    txt_docs = load_txt_documents(DATA_DIR)
    documents = faq_docs + txt_docs

    print(f"FAQ documents loaded:  {len(faq_docs)}")
    print(f"TXT documents loaded:  {len(txt_docs)}")
    print(f"Total documents:       {len(documents)}")

    if not documents:
        print("ERROR: No documents found in data/. Check that data/ contains .txt or faqs.json files.")
        sys.exit(1)

    texts = []
    for doc in documents:
        if doc["kind"] == "faq":
            texts.append(f"Вопрос: {doc['question']}\nОтвет: {doc['answer']}")
        else:
            texts.append(f"{doc['question']}\n{doc['answer']}")

    print(f"\nRequesting embeddings for {len(texts)} documents (model: {model}) ...")
    client = OpenAI(api_key=api_key)
    embeddings = embed_texts(client, texts, model)

    faiss.normalize_L2(embeddings)

    index = build_faiss_index(embeddings)

    faiss.write_index(index, str(INDEX_PATH))
    print(f"FAISS index saved:     {INDEX_PATH}")

    metadata = np.array(
        [
            {
                "id": doc["id"],
                "question": doc["question"],
                "answer": doc["answer"],
                "source": doc["source"],
                "kind": doc["kind"],
            }
            for doc in documents
        ],
        dtype=object,
    )
    np.save(str(METADATA_PATH), metadata, allow_pickle=True)
    print(f"Metadata saved:        {METADATA_PATH}")
    print("\nIndex build complete.")


if __name__ == "__main__":
    main()
