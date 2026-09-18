import re
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, model_validator

from src.graph import build_graph
from src.history import append_history, get_ticket

app = FastAPI(
    title="Agente de Triagem API",
    description="API REST para triagem de chamados com suporte a Human-in-the-Loop",
    version="1.0"
)

# Instância global do grafo (para manter o checkpointer na memória entre requests)
graph = build_graph()

class ChamadoRequest(BaseModel):
    title: str = Field(min_length=3, description="Título do chamado (obrigatório)")
    description: str = Field(min_length=10, description="Descrição do chamado (obrigatória)")

    @model_validator(mode='before')
    def check_injection(cls, values):
        # Combine title and description for scanning
        combined = f"{values.get('title','')} {values.get('description','')}"
        suspicious = [
            r"ignore\s*all\s*previous\s*instructions",
            r"system\s*prompt",
            r"esqueça\s*tudo",
            r"desconsidere\s*as?\s*instruções?",
            r"ignore\s*(?:todas?)?\s*as?\s*instruções?\s*anteriores"
        ]
        for pat in suspicious:
            if re.search(pat, combined, re.IGNORECASE):
                raise ValueError("Potencial ataque de Prompt Injection detectado. Requisição bloqueada.")
        return values

class AprovarRequest(BaseModel):
    approve: bool

def _record_history(ticket_id: str, title: str, description: str, status: str, response: dict | None = None) -> None:
    """Persist a ticket processing record.

    Args:
        ticket_id: ID da thread criada para o chamado.
        title: Título original.
        description: Descrição original.
        status: "completed", "error", "aborted", "pending_human_approval".
        response: Payload retornado ao cliente (quando houver).
    """
    # Convert Pydantic models to plain dicts for JSON serialization
    if response is not None and hasattr(response, "model_dump"):
        response = response.model_dump()
    record = {
        "ticket_id": ticket_id,
        "title": title,
        "description": description,
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
        "response": response,
    }
    append_history(record)


@app.post("/triagem")
def iniciar_triagem(request: ChamadoRequest):
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    initial_state = {
        "ticket_title": request.title,
        "ticket_description": request.description
    }
    
    # Executa até o fim ou até bater no interrupt
    for _ in graph.stream(initial_state, config=config, stream_mode="values"):
        pass

    state_snapshot = graph.get_state(config)
    final_state = state_snapshot.values

    # Se estiver pausado
    # Inclui detalhes para o operador humano decidir
    risk = state_snapshot.values.get("risk_level")
    pending_node = state_snapshot.next
    _record_history(thread_id, request.title, request.description, "pending_human_approval", None)
    return {
        "status": "pending_human_approval",
        "thread_id": thread_id,
        "risk_level": risk,
        "pending_node": pending_node,
        "message": (
            f"O fluxo foi pausado antes do nó '{pending_node}'. "
            f"Risco classificado como '{risk}'. "
            "Ferramenta crítica requer aprovação humana. "
            f"Faça POST em /triagem/{thread_id}/approve para continuar."
        ),
    }

    # Se terminou normalmente ou com erro
    if final_state.get("error"):
        _record_history(thread_id, request.title, request.description, "error", {"message": final_state["error"]})
        return {"status": "error", "message": final_state["error"]}

    # Registro de sucesso
    _record_history(thread_id, request.title, request.description, "completed", final_state.get("structured_response"))
    return {
        "status": "completed",
        "thread_id": thread_id,
        "response": final_state.get("structured_response")
    }



@app.post("/triagem/{thread_id}/approve")
def aprovar_triagem(thread_id: str, request: AprovarRequest):
    config = {"configurable": {"thread_id": thread_id}}
    state_snapshot = graph.get_state(config)
    
    if not state_snapshot.next:
        raise HTTPException(status_code=400, detail="Este chamado não está aguardando aprovação.")
        
    if not request.approve:
        return {"status": "aborted", "message": "Execução da ferramenta rejeitada."}
        
    # Retoma a execução
    for _ in graph.stream(None, config=config, stream_mode="values"):
        pass
        
    # Obtém o estado final após retomar
    final_state = graph.get_state(config).values
    # Se terminou normalmente ou com erro
    if final_state.get("error"):
        # Record error
        _record_history(thread_id, "", "", "error", {"message": final_state["error"]})
        return {"status": "error", "message": final_state["error"]}

    # Record successful completion
    _record_history(thread_id, "", "", "completed", final_state.get("structured_response"))
    return {
        "status": "completed",
        "thread_id": thread_id,
        "response": final_state.get("structured_response")
    }

@app.get("/historico/{ticket_id}")
def obter_historico(ticket_id: str):
    """Retorna o registro histórico do ticket indicado.

    Args:
        ticket_id: ID da thread (thread_id) retornado nas chamadas /triagem.
    """
    rec = get_ticket(ticket_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return rec

