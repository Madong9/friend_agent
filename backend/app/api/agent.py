from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..agents import CampusSocialAgent, TraceStore
from ..auth import get_social_user
from ..database import get_db
from ..memory import SessionBusyError
from ..llm import LLMProviderError
from ..models import User
from ..schemas.agent import AgentRequest, AgentResponse

router = APIRouter(prefix="/agent", tags=["agent"])


async def _run_agent(payload: AgentRequest, user_id: str, db: Session) -> dict:
    try:
        return await CampusSocialAgent(db).run(
            user_id, payload.message, payload.limit, payload.session_id
        )
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except SessionBusyError as exc:
        raise HTTPException(409, str(exc)) from exc
    except LLMProviderError as exc:
        raise HTTPException(
            503, "LLM service is temporarily unavailable; please retry later"
        ) from exc
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/chat", response_model=AgentResponse)
async def chat(
    payload: AgentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_social_user),
):
    return await _run_agent(payload, current_user.id, db)


@router.post("/recommend", response_model=AgentResponse)
async def recommend(
    payload: AgentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_social_user),
):
    return await _run_agent(payload, current_user.id, db)


@router.get("/{session_id}/trace")
def get_trace(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_social_user),
):
    trace = TraceStore(db).get(session_id)
    if trace is None:
        raise HTTPException(404, "trace not found or expired")
    if trace.user_id != current_user.id:
        raise HTTPException(403, "cannot access another user's trace")
    return trace.model_dump()
