from pymongo.errors import DuplicateKeyError

from src.db import get_db
from src.models.theme import DesignTheme

COLLECTION = "themes"


def create_theme(theme: DesignTheme) -> dict:
    db = get_db()
    doc = theme.model_dump()
    doc["_id"] = theme.slug

    try:
        db[COLLECTION].insert_one(doc)
    except DuplicateKeyError as exc:
        raise ValueError(f"Theme '{theme.slug}' already exists") from exc

    return theme.model_dump()
