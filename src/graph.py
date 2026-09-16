import os
import logging
from typing import Literal
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import InMemorySaver
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from src.state import GraphState, TicketOutput
from src.tools import consultar_base, consultar_tool

# Setup básico de observabilidade
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("TriagemAgente")

def get_llm():
    # Usa Ollama local, ou OpenAI se configurado
    if os.getenv("OPENAI_API_KEY") and os.getenv("OPENAI_API_KEY") != "your_openai_api_key_here":
        return ChatOpenAI(model="gpt-4o-mini", temperature=0)
    return ChatOllama(model=os.getenv("MODEL_NAME", "llama3.2"), temperature=0)

def analisar_chamado(state: GraphState) -> GraphState:
    logger.info(f"[NODE] analisar_chamado | Chamado: {state['ticket_title']}")
    # Na prática, poderíamos fazer extrações preliminares aqui.
    return state

def classificar_risco(state: GraphState) -> GraphState:
    logger.info("[NODE] classificar_risco | Avaliando complexidade")
    llm = get_llm()
    prompt = f"Analise o chamado abaixo e classifique o risco apenas como 'simples' ou 'critico'.\n\nTítulo: {state['ticket_title']}\nDescrição: {state['ticket_description']}\n\nRetorne apenas a palavra simples ou critico."
    
    response = llm.invoke(prompt)
    classification = response.content.strip().lower()
    
    if "critico" in classification or "crítico" in classification:
        risk = "critico"
    else:
        risk = "simples"
        
    logger.info(f"[DECISÃO] Risco classificado como: {risk}")
    return {"risk_level": risk}

def route_risk(state: GraphState) -> Literal["consultar_base", "consultar_tool"]:
    if state.get("risk_level") == "critico":
        return "consultar_tool"
    return "consultar_base"

def node_consultar_base(state: GraphState) -> GraphState:
    logger.info("[NODE] consultar_base | Buscando contexto")
    query = state['ticket_title']
    resultado = consultar_base.invoke({"query": query})
    logger.info(f"[TOOL] Resultado da base: {resultado}")
    return {"context": resultado}

def node_consultar_tool(state: GraphState) -> GraphState:
    logger.info("[NODE] consultar_tool | Executando ferramenta crítica")
    # Tenta usar a tool com o título como ID para simular a extração
    ticket_id = state['ticket_title'].split()[0] if state['ticket_title'] else ""
    resultado = consultar_tool.invoke({"ticket_id": ticket_id, "action": "invalidate_permission_cache"})
    logger.info(f"[TOOL] Resultado da ferramenta: {resultado}")
    return {"tool_output": resultado}

def gerar_resposta(state: GraphState) -> GraphState:
    logger.info("[NODE] gerar_resposta | Construindo saída estruturada")
    llm = get_llm()
    structured_llm = llm.with_structured_output(TicketOutput)
    
    prompt = f"Crie um relatório estruturado de triagem para o chamado.\n\n"
    prompt += f"Título: {state['ticket_title']}\n"
    prompt += f"Descrição: {state['ticket_description']}\n"
    prompt += f"Risco identificado: {state['risk_level']}\n"
    
    if state.get("context"):
        prompt += f"Contexto recuperado da base: {state['context']}\n"
    if state.get("tool_output"):
        prompt += f"Saída de ferramentas operacionais: {state['tool_output']}\n"
        
    try:
        response = structured_llm.invoke(prompt)
        return {"structured_response": response}
    except Exception as e:
        logger.error(f"[ERRO] Falha ao gerar resposta estruturada: {e}")
        return {"error": str(e)}

# Configura o Grafo
def build_graph():
    workflow = StateGraph(GraphState)
    
    workflow.add_node("analisar_chamado", analisar_chamado)
    workflow.add_node("classificar_risco", classificar_risco)
    workflow.add_node("consultar_base", node_consultar_base)
    workflow.add_node("consultar_tool", node_consultar_tool)
    workflow.add_node("gerar_resposta", gerar_resposta)
    
    workflow.set_entry_point("analisar_chamado")
    workflow.add_edge("analisar_chamado", "classificar_risco")
    
    # Ramificação condicional
    workflow.add_conditional_edges(
        "classificar_risco",
        route_risk,
        {
            "consultar_base": "consultar_base",
            "consultar_tool": "consultar_tool"
        }
    )
    
    workflow.add_edge("consultar_base", "gerar_resposta")
    workflow.add_edge("consultar_tool", "gerar_resposta")
    workflow.add_edge("gerar_resposta", END)
    
    checkpointer = InMemorySaver()
    # Adicionamos Human-in-the-loop antes de consultar a tool crítica (Extensão)
    graph = workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=["consultar_tool"]
    )
    return graph
