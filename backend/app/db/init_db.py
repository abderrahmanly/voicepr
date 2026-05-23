"""Create database tables. Idempotent — safe to run on every startup."""

from app.db import models  # noqa: F401  (register models)
from app.db.session import Base, engine


def main() -> None:
    Base.metadata.create_all(bind=engine)
    print("[init_db] tables ensured")


if __name__ == "__main__":
    main()
