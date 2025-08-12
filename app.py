import os, tempfile
from pathlib import Path
from sqlalchemy import create_engine

pg_url = os.environ.get("POSTGRES_URL", "").strip()

if pg_url:
    DB_URL = pg_url  # e.g. postgresql+psycopg2://... (Neon) with ?sslmode=require
else:
    data_root = Path("/mount/data")
    if data_root.is_dir() and os.access(data_root, os.W_OK):
        db_file = data_root / "crm.db"
    else:
        # Fallback to temp dir if /mount/data isn't writable/available
        db_file = Path(tempfile.gettempdir()) / "crm.db"
    DB_URL = f"sqlite:///{db_file.as_posix()}"

engine = create_engine(DB_URL, future=True)


