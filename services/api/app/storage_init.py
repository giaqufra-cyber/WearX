"""Solo sviluppo: crea il bucket delle foto nell'archivio locale (MinIO o moto_server).

uv run python -m app.storage_init
"""

import asyncio

from app.config import get_settings
from app.storage import get_store

if __name__ == "__main__":
    if get_settings().is_production:
        raise SystemExit("In produzione il bucket si crea con l'infrastruttura (seduta 23).")
    asyncio.run(get_store().ensure_bucket())
    print(f"Bucket pronto: {get_settings().storage_bucket}")
