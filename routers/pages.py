from __future__ import annotations

import os

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))


@router.get("/")
async def landing(request: Request):
    request.session["redirect_to_landing"] = True
    return templates.TemplateResponse(
        request=request,
        name="landing.html",
        context={"page_id": "landing"},
    )


@router.get("/app")
async def app_page(request: Request):
    if (
        request.session.get("redirect_to_landing")
        and request.query_params.get("from_landing") != "1"
    ):
        return RedirectResponse("/", status_code=302)
    request.session.pop("redirect_to_landing", None)
    demo = os.getenv("DEMO_ALLOW_MOCK", "0").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"page_id": "index", "demo_allow_mock": demo},
    )
