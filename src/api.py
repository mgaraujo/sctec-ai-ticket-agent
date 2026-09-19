import logging
import re
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, model_validator

from src.graph import get_graph
from src.history import append_history, get_ticket

logger = logging.getLogger("TriagemAgente")

app = FastAPI(
    title="Agente de Triagem API",
    description="API REST para triagem de chamados com suporte a Human-in-the-Loop",
    version="1.0"
)

# Armazenador global de grafos para manter estado entre requisições
# Em produção, isso seria um banco de dados (PostgreSQL, Redis, etc)
_graph_store = {}


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

    # Cria um grafo novo para cada request
    graph = get_graph()
    
    # Armazena o grafo para uso posterior no endpoint de aprovação
    _graph_store[thread_id] = {
        "graph": graph,
        "config": config,
        "title": request.title,
        "description": request.description,
    }

    initial_state = {
        "ticket_title": request.title,
        "ticket_description": request.description
    }

    # Executa o workflow até o fim ou até bater num interrupt
    try:
        for _ in graph.stream(initial_state, config=config, stream_mode="values"):
            pass
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as e:  # noqa: BLE001
        # Se houver interrupt (aguardando aprovação), é esperado
        logger.debug(f"Interrupção esperada no workflow: {e}")

    state_snapshot = graph.get_state(config)
    final_state = state_snapshot.values

    # Se estiver aguardando ação humana (chamado crítico)
    structured_response = final_state.get("structured_response")
    requires_human = (
        structured_response.requires_human 
        if structured_response and hasattr(structured_response, "requires_human") 
        else False
    )
    
    if requires_human:
        _record_history(thread_id, request.title, request.description, "pending_human_approval", None)
        return {
            "status": "pending_human_approval",
            "thread_id": thread_id,
            "message": (
                "Chamado requer aprovação humana antes de qualquer ação operacional. "
                f"Faça POST em /triagem/{thread_id}/approve para continuar."
            ),
        }

    # Se terminou com erro
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
    """Aprova ou rejeita um chamado que está aguardando aprovação humana."""
    
    # Recupera o grafo armazenado
    if thread_id not in _graph_store:
        raise HTTPException(
            status_code=404,
            detail=f"Chamado com ID {thread_id} não encontrado ou já foi finalizado."
        )
    
    stored = _graph_store[thread_id]
    graph = stored["graph"]
    config = stored["config"]
    
    # Atualiza o estado com a decisão humana
    if request.approve:
        # Humano aprovou - continua para finalizar_chamado
        graph.update_state(config, {"human_approved": True})
    else:
        # Humano rejeitou - vai para finalizar_sem_acao
        graph.update_state(config, {"human_approved": False})
    
    # Retoma a execução do grafo
    for _ in graph.stream(None, config=config, stream_mode="values"):
        pass
    
    # Obtém o estado final
    final_state = graph.get_state(config).values
    
    # Limpa o armazenamento (não precisa mais)
    del _graph_store[thread_id]
    
    # Se terminou com erro
    if final_state.get("error"):
        _record_history(thread_id, stored["title"], stored["description"], "error", {"message": final_state["error"]})
        return {"status": "error", "message": final_state["error"]}
    
    # Se foi rejeitado, retorna status rejeitado
    if final_state.get("status") == "rejected":
        _record_history(thread_id, stored["title"], stored["description"], "rejected", None)
        return {
            "status": "rejected",
            "thread_id": thread_id,
            "message": "Chamado crítico foi rejeitado pelo usuário. Nenhuma ação foi executada."
        }
    
    # Caso contrário, foi aprovado e finalizado
    _record_history(thread_id, stored["title"], stored["description"], "completed", final_state.get("structured_response"))
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
