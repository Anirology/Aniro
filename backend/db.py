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
            if revision == "0008_backup_snapshots":
                connection.execute(text("""CREATE TABLE recurring_weekly_goals (
                    id VARCHAR(36) PRIMARY KEY,
                    user_id VARCHAR(36) NOT NULL REFERENCES users(id),
                    module_id VARCHAR(36) NOT NULL REFERENCES modules(id),
                    starts_on VARCHAR(10) NOT NULL,
                    archived_at TIMESTAMPTZ,
                    CONSTRAINT recurring_goal_user_module UNIQUE (user_id, module_id)
                )"""))
                connection.execute(text("CREATE INDEX ix_recurring_weekly_goals_user_id ON recurring_weekly_goals (user_id)"))
                connection.execute(text("CREATE INDEX ix_recurring_weekly_goals_module_id ON recurring_weekly_goals (module_id)"))
                connection.execute(text("ALTER TABLE goals ADD COLUMN recurring_template_id VARCHAR(36) REFERENCES recurring_weekly_goals(id)"))
                connection.execute(text("CREATE INDEX ix_goals_recurring_template_id ON goals (recurring_template_id)"))
                connection.execute(text("CREATE UNIQUE INDEX recurring_goal_template_week ON goals (recurring_template_id, target_date)"))
                connection.execute(text("UPDATE alembic_version SET version_num = '0009_recurring_weekly_goals'"))
                revision = "0009_recurring_weekly_goals"
            if revision == "0009_recurring_weekly_goals":
                Base.metadata.tables["focus_preferences"].create(connection, checkfirst=True)
                Base.metadata.tables["focus_sessions"].create(connection, checkfirst=True)
                connection.execute(text("ALTER TABLE completion_logs ADD COLUMN focus_session_id VARCHAR(36) REFERENCES focus_sessions(id)"))
                connection.execute(text("CREATE UNIQUE INDEX ix_completion_logs_focus_session_id ON completion_logs (focus_session_id)"))
                connection.execute(text("UPDATE alembic_version SET version_num = '0010_focus_sessions'"))
                revision = "0010_focus_sessions"
            if revision == "0010_focus_sessions":
                for table in ("goals", "tasks"):
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN recurrence_id VARCHAR(36)"))
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN recurrence_frequency VARCHAR(10)"))
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN occurrence_date VARCHAR(10)"))
                    connection.execute(text(f"CREATE INDEX ix_{table}_recurrence_id ON {table} (recurrence_id)"))
                    connection.execute(text(f"CREATE UNIQUE INDEX {table}_recurrence_occurrence ON {table} (recurrence_id, occurrence_date)"))
                connection.execute(text("UPDATE alembic_version SET version_num = '0011_custom_recurrence'"))
                revision = "0011_custom_recurrence"
            if revision == "0011_custom_recurrence":
                Base.metadata.tables["financial_accounts"].create(connection, checkfirst=True)
                Base.metadata.tables["expense_envelopes"].create(connection, checkfirst=True)
                Base.metadata.tables["upcoming_bills"].create(connection, checkfirst=True)
                connection.execute(text("ALTER TABLE expenses ADD COLUMN account_id VARCHAR(36) REFERENCES financial_accounts(id)"))
                connection.execute(text("CREATE INDEX ix_expenses_account_id ON expenses (account_id)"))
                connection.execute(text("UPDATE alembic_version SET version_num = '0012_student_money_tools'"))
                revision = "0012_student_money_tools"
            if revision != "0012_student_money_tools":
                raise RuntimeError(f"Unsupported hosted schema revision: {revision}")
            return
        if tables.intersection(Base.metadata.tables):
            raise RuntimeError("Hosted database already has Aniro tables but no migration version")
        Base.metadata.create_all(connection)
        connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)"))
        connection.execute(text("INSERT INTO alembic_version (version_num) VALUES ('0012_student_money_tools')"))
