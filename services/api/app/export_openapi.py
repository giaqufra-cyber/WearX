"""Stampa la descrizione OpenAPI dell'API (JSON ordinato, stabile tra un'esecuzione e l'altra).

Uso: uv run python -m app.export_openapi > ../../packages/api-types/openapi.json
"""

import json
import sys

from app.main import create_app


def main() -> None:
    schema = create_app().openapi()
    json.dump(schema, sys.stdout, indent=2, sort_keys=True, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
