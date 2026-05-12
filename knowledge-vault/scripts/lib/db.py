from __future__ import annotations

import sqlite3
from pathlib import Path

from .config import app_config, resolve_path


SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
  id TEXT PRIMARY KEY,
  domain TEXT,
  title TEXT,
  source TEXT,
  url TEXT,
  author TEXT,
  published_at TEXT,
  collected_at TEXT,
  doc_type TEXT,
  credibility_level TEXT,
  importance_score INTEGER,
  summary TEXT,
  file_path TEXT UNIQUE,
  content_hash TEXT,
  status TEXT,
  created_at TEXT,
  updated_at TEXT
);

CREATE TABLE IF NOT EXISTS document_tags (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  document_id TEXT,
  tag TEXT
);

CREATE INDEX IF NOT EXISTS idx_document_tags_doc ON document_tags(document_id);
CREATE INDEX IF NOT EXISTS idx_document_tags_tag ON document_tags(tag);

CREATE TABLE IF NOT EXISTS document_entities (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  document_id TEXT,
  entity_name TEXT,
  entity_type TEXT
);

CREATE INDEX IF NOT EXISTS idx_document_entities_doc ON document_entities(document_id);
CREATE INDEX IF NOT EXISTS idx_document_entities_name ON document_entities(entity_name);

CREATE TABLE IF NOT EXISTS chunks (
  id TEXT PRIMARY KEY,
  document_id TEXT,
  domain TEXT,
  chunk_index INTEGER,
  chunk_text TEXT,
  file_path TEXT,
  heading TEXT,
  token_count INTEGER,
  embedding_status TEXT,
  created_at TEXT,
  updated_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_chunks_domain ON chunks(domain);
CREATE INDEX IF NOT EXISTS idx_chunks_status ON chunks(embedding_status);

CREATE TABLE IF NOT EXISTS sources (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_name TEXT,
  source_url TEXT,
  domain TEXT,
  source_type TEXT,
  credibility_level TEXT,
  enabled INTEGER,
  notes TEXT
);

CREATE TABLE IF NOT EXISTS questions (
  id TEXT PRIMARY KEY,
  question TEXT,
  routed_domain TEXT,
  answer TEXT,
  used_document_ids TEXT,
  created_at TEXT
);

CREATE TABLE IF NOT EXISTS sync_state (
  key TEXT PRIMARY KEY,
  value TEXT,
  updated_at TEXT
);
"""


def db_path() -> Path:
    return resolve_path(app_config()["database_path"])


def connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
        conn.commit()
