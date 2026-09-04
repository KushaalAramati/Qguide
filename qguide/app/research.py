"""
Research Tools API: project metadata, analysis templates, batch multi-target
runs, cross-project comparison, experiment history and reproducible reports.

Kept in its own router so the scientific pipeline (`qguide.core`) is untouched:
everything here composes existing `pipeline.run_design` / `report.build_report`
calls and the persistence layer.
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from qguide.app import access, billing, store
from qguide.app import roles as roles_mod
from qguide.app.branding import BRANDING
from qguide.app.legal import SHORT_DISCLAIMER
from qguide.app.routes import _notify_members, current_email, require_permission
from qguide.app.schemas import DesignRequest
from qguide.core import pipeline
from qguide.core import report as report_mod

router = APIRouter(prefix="/research", tags=["research"])

EXPERIMENT_TYPES = ["knockout", "knock-in", "base_editing", "prime_editing", "crispri",
                    "crispra", "screen", "validation", "other"]

#: Parameters a template may carry (never the sequence -- that is the target).
TEMPLATE_PARAMS = ("cas_enzyme", "pam", "organism", "desired_outcome", "cell_type",
                   "delivery_method", "temperature", "expression_level", "risk_tolerance",
                   "guide_length", "max_guides", "set_size", "selection_mode",
                   "optimizer_mode", "optimizer_backend", "optimizer_preset")

BATCH_MAX_TARGETS = 10


def _clean_params(params: Dict) -> Dict:
    out = {k: v for k, v in (params or {}).items() if k in TEMPLATE_PARAMS and v is not None}
    # Validate by constructing a request against a placeholder sequence.
    DesignRequest(sequence="ACGT", **out)
    return out


# --------------------------------------------------------------------------- #
# Project metadata / notes                                                    #
# --------------------------------------------------------------------------- #
class MetadataPatch(BaseModel):
    experiment_name: Optional[str] = Field(default=None, max_length=255)
    cell_line: Optional[str] = Field(default=None, max_length=255)
    target_gene: Optional[str] = Field(default=None, max_length=255)
    experiment_type: Optional[str] = Field(default=None, max_length=64)
    notes: Optional[str] = Field(default=None, max_length=20000)
    tags: Optional[List[str]] = None
    citations: Optional[List[Dict[str, str]]] = None


@router.get("/projects/{pid}/metadata")
def get_metadata(pid: str, email: str = Depends(current_email)) -> Dict[str, object]:
    meta, role = access.require_project(email, pid, access.VIEWER)
    md = store.get_metadata(meta["uid"]) or {}
    return {"uid": meta["uid"], "role": role, "metadata": md,
            "experiment_types": EXPERIMENT_TYPES}


@router.patch("/projects/{pid}/metadata")
def patch_metadata(pid: str, body: MetadataPatch,
                   email: str = Depends(current_email)) -> Dict[str, object]:
    meta, _ = access.require_project(email, pid, access.EDITOR)
    if body.experiment_type is not None and body.experiment_type not in EXPERIMENT_TYPES + [""]:
        raise HTTPException(status_code=400, detail="Unknown experiment type.")
    patch = body.model_dump(exclude_unset=True)
    md = store.update_metadata(meta["uid"], patch, email)
    if md is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    _notify_members(meta, email, "project_updated",
                    f"\"{meta['name']}\": experiment notes updated", f"by {email}")
    return {"uid": meta["uid"], "metadata": md}


@router.get("/tags")
def tags(email: str = Depends(current_email)) -> Dict[str, object]:
    return {"tags": store.all_tags(email)}


# --------------------------------------------------------------------------- #
# Analysis templates                                                          #
# --------------------------------------------------------------------------- #
class TemplateBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    params: Dict[str, object]


class TemplatePatch(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    params: Optional[Dict[str, object]] = None


@router.get("/templates")
def list_templates(email: str = Depends(require_permission(roles_mod.P_RESEARCH_TOOLS))) -> Dict[str, object]:
    return {"templates": store.list_templates(email), "fields": list(TEMPLATE_PARAMS)}


@router.post("/templates")
def create_template(body: TemplateBody,
                    email: str = Depends(require_permission(roles_mod.P_RESEARCH_TOOLS))) -> Dict[str, object]:
    try:
        params = _clean_params(body.params)
    except Exception as exc:                              # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Invalid parameters: {exc}") from exc
    if len(store.list_templates(email)) >= 100:
        raise HTTPException(status_code=400, detail="Template limit reached (100).")
    return store.create_template(email, body.name, body.description, params)


@router.patch("/templates/{tid}")
def update_template(tid: int, body: TemplatePatch,
                    email: str = Depends(require_permission(roles_mod.P_RESEARCH_TOOLS))) -> Dict[str, object]:
    params = None
    if body.params is not None:
        try:
            params = _clean_params(body.params)
        except Exception as exc:                          # noqa: BLE001
            raise HTTPException(status_code=400, detail=f"Invalid parameters: {exc}") from exc
    t = store.update_template(email, tid, body.name, body.description, params)
    if t is None:
        raise HTTPException(status_code=404, detail="Template not found.")
    return t


@router.delete("/templates/{tid}")
def delete_template(tid: int,
                    email: str = Depends(require_permission(roles_mod.P_RESEARCH_TOOLS))) -> Dict[str, bool]:
    if not store.delete_template(email, tid):
        raise HTTPException(status_code=404, detail="Template not found.")
    return {"ok": True}


# --------------------------------------------------------------------------- #
# Batch multi-target analysis                                                  #
# --------------------------------------------------------------------------- #
class BatchTarget(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    sequence: str = Field(..., min_length=25)


class BatchBody(BaseModel):
    targets: List[BatchTarget] = Field(..., min_length=1, max_length=BATCH_MAX_TARGETS)
    params: Dict[str, object] = Field(default_factory=dict)
    template_id: Optional[int] = None
    folder_name: Optional[str] = Field(default=None, max_length=255)
    tags: List[str] = Field(default_factory=list)
    experiment_name: Optional[str] = Field(default=None, max_length=255)


@router.get("/batch/limits")
def batch_limits(email: str = Depends(current_email)) -> Dict[str, object]:
    role = store.get_role(email)
    return {"max_targets": BATCH_MAX_TARGETS, "credits_per_target": billing.CREDITS_PER_RUN,
            "allowed": roles_mod.has_permission(role, roles_mod.P_BATCH_ANALYSIS),
            "role": role}


@router.post("/batch")
def run_batch(body: BatchBody,
              email: str = Depends(require_permission(roles_mod.P_BATCH_ANALYSIS))) -> Dict[str, object]:
    """Run the pipeline for several targets with one shared configuration. Each
    target becomes its own project (optionally filed in a new folder and tagged)
    so every existing per-project view keeps working. Credits are checked for
    the whole batch up front and charged per successful run."""
    params = dict(body.params or {})
    if body.template_id is not None:
        tpl = next((t for t in store.list_templates(email) if t["id"] == body.template_id), None)
        if tpl is None:
            raise HTTPException(status_code=404, detail="Template not found.")
        params = {**tpl["params"], **params}
    try:
        params = _clean_params(params)
    except Exception as exc:                              # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Invalid parameters: {exc}") from exc

    user = store.get_user(email)
    needed = billing.CREDITS_PER_RUN * len(body.targets)
    if user["credits"] < needed:
        raise HTTPException(status_code=402,
                            detail=f"This batch needs {needed} credits; you have {user['credits']}.")

    folder_id = None
    if body.folder_name and body.folder_name.strip():
        folder_id = store.create_folder(email, body.folder_name.strip())["id"]

    results, t_batch = [], time.perf_counter()
    for target in body.targets:
        item: Dict[str, object] = {"name": target.name, "ok": False}
        try:
            req = DesignRequest(sequence=target.sequence, gene_name=target.name, **params)
            t0 = time.perf_counter()
            resp = pipeline.run_design(req)
            elapsed = round(time.perf_counter() - t0, 3)
            if not resp.guides:
                item["error"] = "No guides found for this sequence / PAM."
                results.append(item)
                continue
            balance = store.charge_run(email, billing.CREDITS_PER_RUN, f"Batch run: {target.name}")
            if balance is None:
                item["error"] = "Insufficient credits."
                results.append(item)
                continue
            import uuid as _uuid
            pid = store.next_pid(email)
            proj = {"id": pid, "uid": _uuid.uuid4().hex, "name": target.name,
                    "created": datetime.now().strftime("%Y-%m-%d %H:%M"), "elapsed": elapsed,
                    "selected_guide": resp.best_single_guide_id, "request": req, "response": resp}
            store.save_project(email, proj)
            if folder_id:
                store.move_project(email, pid, folder_id)
            md_patch: Dict[str, object] = {"target_gene": target.name, "tags": body.tags}
            if body.experiment_name:
                md_patch["experiment_name"] = body.experiment_name
            store.update_metadata(proj["uid"], md_patch, email)
            item.update({"ok": True, "project_id": pid, "uid": proj["uid"], "elapsed": elapsed,
                         "n_guides": len(resp.guides), "best_guide": resp.best_single_guide_id,
                         "best_score": round(resp.guides[0].final_score, 4),
                         "set": list(resp.optimized_set.selected_guide_ids), "balance": balance})
        except HTTPException:
            raise
        except Exception as exc:                          # noqa: BLE001
            item["error"] = str(exc)[:300]
        results.append(item)

    ok = [r for r in results if r["ok"]]
    return {"ok": len(ok), "failed": len(results) - len(ok), "results": results,
            "folder_id": folder_id, "elapsed": round(time.perf_counter() - t_batch, 3),
            "balance": store.get_user(email)["credits"]}


# --------------------------------------------------------------------------- #
# Comparison                                                                   #
# --------------------------------------------------------------------------- #
class CompareBody(BaseModel):
    project_ids: List[str] = Field(..., min_length=2, max_length=4)


@router.post("/compare")
def compare_projects(body: CompareBody,
                     email: str = Depends(require_permission(roles_mod.P_RESEARCH_TOOLS))) -> Dict[str, object]:
    """Side-by-side summary of 2-4 projects the caller can access."""
    items = []
    for ident in body.project_ids:
        meta, role = access.require_project(email, ident, access.VIEWER)
        summ = store.project_summary_for_compare(meta["uid"])
        if summ is None:
            raise HTTPException(status_code=404, detail="Project not found.")
        summ["role"] = role
        items.append(summ)
    # Guides shared between projects (same protospacer) -- useful for multi-target designs
    seqs = [set(g["sequence"] for g in it["top_guides"]) for it in items]
    common = set.intersection(*seqs) if seqs else set()
    return {"projects": items, "common_top_guides": sorted(common),
            "disclaimer": SHORT_DISCLAIMER}


# --------------------------------------------------------------------------- #
# History                                                                      #
# --------------------------------------------------------------------------- #
@router.get("/history")
def history(limit: int = 50, email: str = Depends(current_email)) -> Dict[str, object]:
    """Experiment history: the caller's design/re-run/batch ledger events joined
    with the projects they can currently open."""
    limit = max(1, min(int(limit), 200))
    acct = store.account_summary(email) or {}
    events = [t for t in acct.get("transactions", []) if t["type"] == "usage"]
    events = list(reversed(events))[:limit]
    own = store.list_projects_meta(email)
    shared = store.list_shared_projects(email)
    return {"events": events,
            "projects": sorted(own + shared, key=lambda p: p.get("created") or "", reverse=True)[:limit]}


# --------------------------------------------------------------------------- #
# Reports (reproducibility bundle)                                             #
# --------------------------------------------------------------------------- #
def _reproducibility(proj: Dict) -> Dict[str, object]:
    resp = proj["response"]
    kinds = {}
    for g in resp.guides[:1]:
        for m in getattr(getattr(g, "ensemble", None), "model_scores", []) or []:
            kinds[m.name] = {"task": m.task, "kind": m.kind, "available": m.available}
    return {
        "generated_by": BRANDING.app_name,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "project": {"id": proj["id"], "uid": proj["uid"], "name": proj["name"],
                    "created": proj["created"], "owner": proj["owner_email"],
                    "pipeline_elapsed_s": proj["elapsed"]},
        "request": resp.request.model_dump(),
        "optimizer": {"method": resp.optimized_set.method, "mode": resp.optimized_set.mode,
                      "iterations": resp.optimized_set.iterations},
        "models": kinds,
        "disclaimer": SHORT_DISCLAIMER,
    }


def _markdown_report(rep: Dict, repro: Dict, md: Dict) -> str:
    import json as _json
    L = [f"# {rep.get('title') or repro['project']['name']}", "",
         f"_{SHORT_DISCLAIMER}_", ""]
    if rep.get("summary"):
        L += [str(rep["summary"]), ""]
    exp = [(k, md.get(k)) for k in ("experiment_name", "target_gene", "cell_line", "experiment_type") if md.get(k)]
    if exp or md.get("tags"):
        L += ["## Experiment", ""]
        for k, v in exp:
            L.append(f"- **{k.replace('_', ' ')}**: {v}")
        if md.get("tags"):
            L.append(f"- **tags**: {', '.join(md['tags'])}")
        L.append("")
    L += ["## Inputs", ""]
    for k, v in (rep.get("inputs") or {}).items():
        L.append(f"- **{k}**: {v}")
    L += ["", "## Selected guide set", ""]
    for g in rep.get("selected_set") or []:
        L.append(f"- `{g['guide_id']}` {g['sequence']} — score {g.get('final_qguide_score', 0):.3f}, "
                 f"confidence {g.get('confidence', '')}. {g.get('explanation', '')}")
    opt = rep.get("optimization") or {}
    if opt:
        L += ["", f"Optimiser: {opt.get('method', '')} ({opt.get('mode', '')}). {opt.get('comparison_note', '')}"]
    L += ["", "## Candidate guides", "",
          "| rank | guide | sequence | PAM | strand | pos | score | confidence |",
          "|---|---|---|---|---|---|---|---|"]
    for g in rep.get("candidate_guides") or []:
        L.append(f"| {g.get('rank', '')} | {g.get('guide_id', '')} | `{g.get('sequence', '')}` | {g.get('pam', '')} | "
                 f"{g.get('strand', '')} | {g.get('position', '')} | {g.get('final_qguide_score', 0):.3f} | {g.get('confidence', '')} |")
    if md.get("notes"):
        L += ["", "## Notes", "", md["notes"]]
    if md.get("citations"):
        L += ["", "## References", ""]
        for c in md["citations"]:
            L.append(f"- {c.get('label') or c.get('doi') or c.get('url')}"
                     + (f" — {c['url']}" if c.get("url") else "")
                     + (f" (doi:{c['doi']})" if c.get("doi") else ""))
    L += ["", "## Limitations", ""]
    ot = rep.get("off_target_limitations") or {}
    if ot.get("warning"):
        L.append(f"- {ot['warning']}")
    if ot.get("high_risk_guides"):
        L.append(f"- High off-target-risk guides: {', '.join(ot['high_risk_guides'])}")
    for w in rep.get("confidence_limitations") or []:
        L.append(f"- {w}")
    if rep.get("validation_note"):
        L += ["", f"**{rep['validation_note']}**"]
    L += ["", "## Assumptions", ""]
    for a in rep.get("assumptions") or []:
        L.append(f"- {a}")
    L += ["", "## Reproducibility", "", "```json",
          _json.dumps({k: v for k, v in repro.items() if k != "disclaimer"}, indent=2, default=str),
          "```", ""]
    return "\n".join(L)


@router.get("/projects/{pid}/report")
def project_report(pid: str, fmt: str = "json",
                   email: str = Depends(current_email)) -> object:
    """Structured scientific report from the STORED result (no re-run), with
    experiment metadata and a reproducibility block. `fmt=md` returns Markdown."""
    from fastapi.responses import PlainTextResponse
    meta, _ = access.require_project(email, pid, access.VIEWER)
    proj = store.get_project_by_uid(meta["uid"])
    if proj is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    rep = report_mod.build_report(proj["response"])
    repro = _reproducibility(proj)
    md = store.get_metadata(meta["uid"]) or {}
    if fmt == "md":
        return PlainTextResponse(_markdown_report(rep, repro, md), media_type="text/markdown")
    return {"report": rep, "metadata": md, "reproducibility": repro}
