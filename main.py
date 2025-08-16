#!/usr/bin/env python3

import logging
import sys

from src.api import app

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    try:
        import uvicorn
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
            log_level="info"
        )
    except ImportError:
        logging.error("uvicorn not installed. Install dependencies first.")
        sys.exit(1)


if __name__ == "__main__":
    main()
