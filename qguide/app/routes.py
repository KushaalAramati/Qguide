"""
FastAPI routes for Q-Guide.

Thin HTTP layer over the core pipeline. The API is deliberately stateless and
returns plain Pydantic models (JSON) so a React frontend can consume it directly;
the Streamlit prototype calls the same `core.pipeline` functions in-process.
"""
from __future__ import annotations

from typing import Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from qguide.app.schemas import DesignRequest, DesignResponse, Guide
from qguide.core import pipeline
from qguide.core.explainability import assumptions
from qguide.core.guide_generator import CAS_PROFILES

router = APIRouter()


@router.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "service": "q-guide", "version": "1.0"}


@router.get("/enzymes")
def enzymes() -> Dict[str, Dict]:
    """Supported Cas systems and their default PAM / guide length."""
    return {
        name: {"pam": p.pam, "guide_length": p.guide_length, "pam_side": p.pam_side}
        for name, p in CAS_PROFILES.items()
    }


@router.post("/design", response_model=DesignResponse)
def design(request: DesignRequest) -> DesignResponse:
    if not request.sequence.strip():
        raise HTTPException(status_code=400, detail="Empty sequence.")
    return pipeline.run_design(request)


class SensitivityRequest(BaseModel):
    request: DesignRequest
    guide_id: str
    scenarios: List[Dict[str, object]]


@router.post("/sensitivity")
def sensitivity(payload: SensitivityRequest) -> List[Dict[str, object]]:
    return pipeline.context_sensitivity(
        payload.request, payload.guide_id, payload.scenarios
    )


@router.get("/simulation/axes")
def simulation_axes() -> Dict[str, List[Dict[str, object]]]:
    """Built-in experiment-simulation sweeps (Cas enzyme, cell type, etc.)."""
    return pipeline.SIMULATION_AXES


class SimulationRequest(BaseModel):
    request: DesignRequest
    # Provide EITHER a named axis to sweep OR an explicit list of scenarios.
    axis: str | None = None
    scenarios: List[Dict[str, object]] | None = None


@router.post("/simulate")
def simulate(payload: SimulationRequest) -> List[Dict[str, object]]:
    if payload.axis:
        return pipeline.simulate_axis(payload.request, payload.axis)
    if payload.scenarios:
        return pipeline.simulate_experiments(payload.request, payload.scenarios)
    raise HTTPException(status_code=400, detail="Provide 'axis' or 'scenarios'.")


class PredictExperimentRequest(BaseModel):
    request: DesignRequest
    guide_id: str
    n_cells: int = 5000
    replicates: int = 300


@router.post("/predict-experiment")
def predict_experiment(payload: PredictExperimentRequest) -> Dict[str, object]:
    """Monte-Carlo the predicted experimental outcome of using a specific guide."""
    from qguide.core import experiment_simulation as expsim
    resp = pipeline.run_design(payload.request)
    guide = next((g for g in resp.guides if g.guide_id == payload.guide_id), None)
    if guide is None:
        raise HTTPException(status_code=404, detail=f"Guide {payload.guide_id} not found.")
    return expsim.simulate_experiment(guide, n_cells=payload.n_cells,
                                      replicates=payload.replicates)


@router.get("/assumptions")
def get_assumptions() -> Dict[str, List[str]]:
    return {"assumptions": assumptions()}
