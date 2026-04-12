"""FastAPI server entry point."""

import os
import sys
import warnings

# ★ 抑制 urllib3 的 OpenSSL 警告（macOS 系统使用 LibreSSL）
warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL")

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn
from dotenv import load_dotenv

load_dotenv()


def main():
    """Run the FastAPI server."""
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    reload = os.getenv("API_RELOAD", "true").lower() == "true"

    print(f"Starting API server on {host}:{port} (reload={reload})")
    uvicorn.run(
        "src.api.main:app",
        host=host,
        port=port,
        reload=reload,
        reload_dirs=["src"],
        reload_delay=2.0,  # 等待2秒再重启，合并多次文件变动
        reload_excludes=["tests/*", "scripts/*", "data/*", "logs/*", "*.pyc", "__pycache__/*"],
    )


if __name__ == "__main__":
    main()
