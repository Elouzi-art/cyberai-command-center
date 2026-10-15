import os
from pathlib import Path

from cyberai_analyzer.worker import serve_forever

if __name__ == "__main__":
    serve_forever(
        Path(os.environ.get("INBOX_DIR", "/inbox")),
        Path(os.environ.get("OUTBOX_DIR", "/outbox")),
        max_bytes=int(os.environ.get("MAX_UPLOAD_BYTES", str(20 * 1024 * 1024))),
        timeout=float(os.environ.get("ANALYSIS_TIMEOUT", "30")),
    )
