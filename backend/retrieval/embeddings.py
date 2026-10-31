"""Local dense embeddings: BAAI/bge-small-en-v1.5 via fastembed (ONNX, CPU), cached with a manifest."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from backend.config import DATA, INDEXES

MODEL_NAME = "BAAI/bge-small-en-v1.5"
MODEL_CACHE = DATA / "models"
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
EMB_PATH = INDEXES / "embeddings.f32.npy"
META_PATH = INDEXES / "embeddings_meta.json"
DIM = 384

_model = None


def _revision() -> str:
    snaps = sorted(MODEL_CACHE.glob("models--*/snapshots/*"))
    return "; ".join(f"{p.parent.parent.name.replace('models--', '').replace('--', '/')}@{p.name}" for p in snaps)


def get_model():
    global _model
    if _model is None:
        from fastembed import TextEmbedding
        _model = TextEmbedding(MODEL_NAME, cache_dir=str(MODEL_CACHE), providers=["CPUExecutionProvider"], threads=4)
    return _model


def _norm(a: np.ndarray) -> np.ndarray:
    a = np.asarray(a, dtype=np.float32)
    n = np.linalg.norm(a, axis=-1, keepdims=True)
    return (a / np.maximum(n, 1e-12)).astype(np.float32)


def embed_passages(texts: list[str], batch_size: int = 32) -> np.ndarray:
    if not texts:
        return np.zeros((0, DIM), np.float32)
    return _norm(np.stack(list(get_model().embed(texts, batch_size=batch_size))))


def embed_query(q: str) -> np.ndarray:
    return _norm(np.stack(list(get_model().embed([QUERY_PREFIX + q]))))[0]


def input_hash(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def load_cache():
    if EMB_PATH.exists() and META_PATH.exists():
        meta = json.loads(META_PATH.read_text())
        arr = np.load(EMB_PATH)
        if arr.shape[0] == len(meta["chunk_ids"]):
            return arr, meta
    return None, None


def build_or_load(chunk_ids: list[str], inputs: list[str], force: bool = False, log=print):
    """Return (matrix[n,384] float32 normalised, info). Reuses cached vectors whose
    (chunk_id, sha256(input)) and model revision match; embeds only the remainder."""
    hashes = [input_hash(t) for t in inputs]
    rev = _revision() if MODEL_CACHE.exists() else ""
    arr, meta = (None, None) if force else load_cache()
    cached = {}
    if meta and meta.get("model") == MODEL_NAME and meta.get("revision") == rev and rev:
        for i, (cid, h) in enumerate(zip(meta["chunk_ids"], meta["input_sha256"])):
            cached[(cid, h)] = i
    out = np.zeros((len(inputs), DIM), np.float32)
    todo = []
    for i, (cid, h) in enumerate(zip(chunk_ids, hashes)):
        j = cached.get((cid, h))
        if j is None:
            todo.append(i)
        else:
            out[i] = arr[j]
    if todo:
        log(f"embedding {len(todo)}/{len(inputs)} chunks ...")
        # sort by length so batches pad little; vectors are per-text so order does not change them
        order = sorted(todo, key=lambda i: len(inputs[i]))
        vecs = embed_passages([inputs[i] for i in order])
        for k, i in enumerate(order):
            out[i] = vecs[k]
        rev = _revision()
    INDEXES.mkdir(parents=True, exist_ok=True)
    import fastembed
    info = dict(model=MODEL_NAME, revision=rev, fastembed=fastembed.__version__, dim=DIM, normalized=True,
                dtype="float32", query_prefix=QUERY_PREFIX, n=len(inputs), chunk_ids=chunk_ids, input_sha256=hashes,
                n_embedded_this_run=len(todo))
    if todo or meta is None or meta.get("chunk_ids") != chunk_ids:
        np.save(EMB_PATH, out)
        META_PATH.write_text(json.dumps(info))
    return out, info
