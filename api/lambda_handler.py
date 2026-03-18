from __future__ import annotations

from mangum import Mangum

from api.main import app

# AWS Lambda entrypoint for FastAPI app
handler = Mangum(app)
