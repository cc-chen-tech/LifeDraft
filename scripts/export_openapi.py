#!/usr/bin/env python3
"""Export FastAPI OpenAPI schema to JSON file for frontend type generation.

Usage:
    python scripts/export_openapi.py [output_path]

Default output: frontend/src/types/openapi-schema.json
"""

import json
import os
import sys

# Ensure project root is in path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Set minimal environment to avoid missing env var errors
os.environ.setdefault("ENVIRONMENT", "development")

from src.api.main import app  # noqa: E402

def main():
    output_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        project_root, "frontend", "src", "types", "openapi-schema.json"
    )

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    schema = app.openapi()

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)

    print(f"OpenAPI schema exported to: {output_path}")
    print(f"  Paths: {len(schema.get('paths', {}))}")
    print(f"  Schemas: {len(schema.get('components', {}).get('schemas', {}))}")


if __name__ == "__main__":
    main()
