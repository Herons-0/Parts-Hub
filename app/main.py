"""FastAPI application: routes, page rendering, and JSON endpoints.

Run with:  uvicorn app.main:app --reload
Then open:  http://127.0.0.1:8000
"""
from pathlib import Path

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import projects as proj
from .config import VENDORS
from .database import init_db
from .search import search_products, compare_group

BASE_DIR = Path(__file__).resolve().parent
app = FastAPI(title="PartsHub")

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


# Format helper available in all templates: ₹1,234.00
def rupees(value) -> str:
    if value in (None, ""):
        return "—"
    try:
        return f"₹{float(value):,.2f}"
    except (ValueError, TypeError):
        return "—"


templates.env.filters["rupees"] = rupees


@app.on_event("startup")
def _startup() -> None:
    init_db()


def _ctx(request: Request, **kwargs) -> dict:
    """Common template context (vendor list for filters, project list for nav)."""
    base = {
        "request": request,
        "vendors": VENDORS,
        "projects": proj.list_projects(),
    }
    base.update(kwargs)
    return base


# ---------------------------------------------------------------- pages

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(request, "index.html", _ctx(request))


@app.get("/search", response_class=HTMLResponse)
def search_page(
    request: Request,
    q: str = "",
    vendor: str = "",
    in_stock: str = "",
    sort: str = "relevance",
    group: str = "",
):
    results = search_products(
        q,
        vendor=vendor or None,
        in_stock_only=bool(in_stock),
        sort=sort,
    )

    grouped = None
    if group:  # "Compare similar" view: collapse results by normalized key
        buckets: dict[str, list] = {}
        for r in results:
            buckets.setdefault(r["norm_key"] or str(r["id"]), []).append(r)
        grouped = []
        for items in buckets.values():
            items.sort(key=lambda x: (0 if x["in_stock"] else 1,
                                      x["price"] if x["price"] is not None else float("inf")))
            grouped.append(items)
        grouped.sort(key=lambda g: len(g), reverse=True)  # multi-vendor groups first

    return templates.TemplateResponse(
        request,
        "search.html",
        _ctx(request, q=q, vendor=vendor, in_stock=in_stock, sort=sort,
             group=group, results=results, grouped=grouped),
    )


@app.get("/product/{product_id}/compare", response_class=HTMLResponse)
def product_compare(request: Request, product_id: int):
    matches = compare_group(product_id)
    if not matches:
        raise HTTPException(404, "Product not found")
    return templates.TemplateResponse(
        request, "compare.html", _ctx(request, product=matches[0], matches=matches)
    )


@app.get("/projects", response_class=HTMLResponse)
def projects_page(request: Request):
    return templates.TemplateResponse(request, "projects.html", _ctx(request))


@app.get("/projects/{project_id}", response_class=HTMLResponse)
def project_detail(request: Request, project_id: int):
    project = proj.get_project(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return templates.TemplateResponse(request, "project_detail.html", _ctx(request, project=project))


# ---------------------------------------------------------------- actions (forms)

@app.post("/projects")
def create_project(name: str = Form(...)):
    pid = proj.create_project(name)
    return RedirectResponse(f"/projects/{pid}", status_code=303)


@app.post("/projects/{project_id}/delete")
def delete_project(project_id: int):
    proj.delete_project(project_id)
    return RedirectResponse("/projects", status_code=303)


@app.post("/projects/{project_id}/items/{product_id}/quantity")
def update_quantity(project_id: int, product_id: int, quantity: int = Form(...)):
    proj.set_quantity(project_id, product_id, quantity)
    return RedirectResponse(f"/projects/{project_id}", status_code=303)


@app.post("/projects/{project_id}/items/{product_id}/remove")
def remove_item(project_id: int, product_id: int):
    proj.remove_item(project_id, product_id)
    return RedirectResponse(f"/projects/{project_id}", status_code=303)


# ---------------------------------------------------------------- JSON API (used by JS)

@app.get("/api/projects")
def api_projects():
    return proj.list_projects()


@app.post("/api/projects/{project_id}/add")
def api_add_item(project_id: int, payload: dict):
    product_id = int(payload.get("product_id"))
    quantity = int(payload.get("quantity", 1))
    proj.add_item(project_id, product_id, quantity)
    return JSONResponse({"ok": True})


@app.post("/api/projects/quick")
def api_quick_project(payload: dict):
    """Create a project on the fly (used by the 'Add to new project' UI)."""
    pid = proj.create_project(payload.get("name", "Untitled"))
    return JSONResponse({"ok": True, "project_id": pid})
