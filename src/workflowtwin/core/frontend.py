"""Optional static frontend serving for the unified deployment image."""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def install_frontend_entry(application: FastAPI, dist_path: Path | None) -> Path | None:
    """Register the SPA root and assets before the API's JSON root route."""
    if dist_path is None:
        return None

    resolved = dist_path.resolve()
    index = resolved / "index.html"
    assets = resolved / "assets"
    if not index.is_file() or not assets.is_dir():
        raise RuntimeError(f"Frontend distribution is incomplete: {resolved}")

    application.mount("/assets", StaticFiles(directory=assets), name="frontend-assets")

    @application.get("/", include_in_schema=False)
    async def frontend_index() -> FileResponse:
        return FileResponse(index)

    return index


def install_frontend_fallback(application: FastAPI, index: Path | None) -> None:
    """Register the client-route fallback after every API route."""
    if index is None:
        return

    @application.get("/{client_path:path}", include_in_schema=False)
    async def frontend_route(client_path: str) -> FileResponse:
        if "." in Path(client_path).name:
            raise HTTPException(status_code=404, detail="Frontend asset not found")
        return FileResponse(index)
