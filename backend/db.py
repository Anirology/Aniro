import os
from pathlib import Path
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

ROOT = Path(__file__).resolve().parent
DATABASE_URL = (
    os.getenv("ANIRO_DATABASE_URL")
    or os.getenv("POSTGRES_URL")
    or os.getenv("DATABASE_URL")
    or f"sqlite:///{ROOT / 'aniro.db'}"
)
if os.getenv("VERCEL") and DATABASE_URL.startswith("sqlite"):
    raise RuntimeError("Set ANIRO_DATABASE_URL to a persistent Postgres database before deploying")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql://" + DATABASE_URL.removeprefix("postgres://")
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL.removeprefix("postgresql://")
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    pool_pre_ping=True,
)

if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def sqlite_settings(connection, _):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

class Base(DeclarativeBase):
    pass


def ensure_hosted_schema():
    """Initialize a new hosted database once, without altering an unknown schema."""
    if not os.getenv("VERCEL"):
        return
    if engine.dialect.name != "postgresql":
        raise RuntimeError("Hosted Aniro requires Postgres")
    with engine.begin() as connection:
        connection.execute(text("SELECT pg_advisory_xact_lock(hashtext('aniro_schema'))"))
        tables = set(inspect(connection).get_table_names())
        if "alembic_version" in tables:
            revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
            if revision != "0008_backup_snapshots":
                raise RuntimeError(f"Unsupported hosted schema revision: {revision}")
            return
        if tables.intersection(Base.metadata.tables):
            raise RuntimeError("Hosted database already has Aniro tables but no migration version")
        Base.metadata.create_all(connection)
        connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)"))
        connection.execute(text("INSERT INTO alembic_version (version_num) VALUES ('0008_backup_snapshots')"))
