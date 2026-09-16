import uuid

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.graph import build_graph

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

class AprovarRequest(BaseModel):
    approve: bool

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
    if state_snapshot.next:
        return {
            "status": "pending_human_approval",
            "thread_id": thread_id,
            "message": f"O fluxo foi pausado antes do nó: {state_snapshot.next}. Ferramenta crítica pendente. Faça POST em /triagem/{thread_id}/approve para continuar."
        }

    # Se terminou normalmente ou com erro
    if final_state.get("error"):
        return {"status": "error", "message": final_state["error"]}
        
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
        
    final_state = graph.get_state(config).values
    
    if final_state.get("error"):
        return {"status": "error", "message": final_state["error"]}
        
    return {
        "status": "completed",
        "thread_id": thread_id,
        "response": final_state.get("structured_response")
    }
