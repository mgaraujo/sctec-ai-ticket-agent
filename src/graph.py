import logging
import os
from typing import Literal

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    def load_dotenv():
        return

try:
    from langchain_core.runnables import RunnableConfig
except ImportError:  # pragma: no cover
    class RunnableConfig(dict):
        pass


from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import interrupt
from langgraph.graph import END, StateGraph


from src.state import GraphState, TicketOutput
from src.tools import consultar_base, consultar_tool


load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger("TriagemAgente")


def get_trace_id(config: RunnableConfig) -> str:
    """Obtém o thread_id usado como identificador de correlação."""
    return config.get(
        "configurable",
        {}
    ).get(
        "thread_id",
        "trace-desconhecido"
    )


def get_llm():
    """Retorna o modelo configurado."""

    if (
        os.getenv("OPENAI_API_KEY")
        and os.getenv("OPENAI_API_KEY") != "your_openai_api_key_here"
    ):
        return ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0
        )

    return ChatOllama(
        model=os.getenv("MODEL_NAME", "llama3.2"),
        temperature=0
    )


# ============================================================
# 1. ANÁLISE
# ============================================================

def analisar_chamado(
    state: GraphState,
    config: RunnableConfig
) -> GraphState:

    trace_id = get_trace_id(config)

    logger.info(
        f"[Trace: {trace_id}] "
        f"[NODE] analisar_chamado | "
        f"Chamado: {state.get('ticket_title')}"
    )

    return state


# ============================================================
# 2. CLASSIFICAÇÃO DE RISCO
# ============================================================

def classificar_risco(
    state: GraphState,
    config: RunnableConfig
) -> GraphState:

    trace_id = get_trace_id(config)

    logger.info(
        f"[Trace: {trace_id}] "
        f"[NODE] classificar_risco | Avaliando chamado"
    )

    # Apenas registra o chamado. A decisão de risco será feita pelo LLM na resposta estruturada.
    new_state = dict(state)
    new_state["status"] = "processing"

    logger.info(
        f"[Trace: {trace_id}] "
        f"[DECISÃO] Processando chamado (decisão final será do LLM)"
    )

    return new_state


# ============================================================
# 3. ROTEAMENTO
# ============================================================

def route_human_decision(
    state: GraphState
) -> Literal["finalizar_chamado", "finalizar_sem_acao"]:
    """Decide após aprovação humana."""
    if state.get("human_approved") is True:
        return "finalizar_chamado"
    
    return "finalizar_sem_acao"


def route_after_llm_response(
    state: GraphState
) -> Literal["aguardar_aprovacao_humana", "finalizar_chamado"]:
    """
    Após o LLM gerar resposta, verifica se requires_human=True.
    Se sim, espera aprovação. Se não, finaliza direto.
    """
    structured_response = state.get("structured_response")
    if structured_response and hasattr(structured_response, "requires_human"):
        if structured_response.requires_human:
            return "aguardar_aprovacao_humana"
    
    return "finalizar_chamado"


# ============================================================
# 4. CHAMADO SIMPLES
# ============================================================

def node_consultar_base(
    state: GraphState,
    config: RunnableConfig
) -> GraphState:

    trace_id = get_trace_id(config)

    logger.info(
        f"[Trace: {trace_id}] "
        f"[NODE] consultar_base | "
        f"Processamento automático"
    )

    query = state.get("ticket_title", "")

    resultado = consultar_base.invoke({
        "query": query
    })

    logger.info(
        f"[Trace: {trace_id}] "
        f"[TOOL] Resultado da base: {resultado}"
    )

    return {
        "context": resultado,
        "status": "processing"
    }


# ============================================================
# 5. GATE HUMANO
# ============================================================




def aguardar_aprovacao_humana(
    state: GraphState,
    config: RunnableConfig
) -> GraphState:

    trace_id = get_trace_id(config)

    logger.info(
        f"[Trace: {trace_id}] "
        f"[NODE] aguardar_aprovacao_humana | "
        f"Aguardando decisão humana"
    )

    # Verifica a decisão humana
    human_approved = state.get("human_approved")
    
    if human_approved is None:
        # Interrompe o workflow aqui até que human_approved seja definido
        logger.info(
            f"[Trace: {trace_id}] "
            f"[INTERRUPT] Aguardando aprovação humana via API"
        )
        interrupt("Aguardando aprovação humana. Faça POST em /triagem/{thread_id}/approve")
    elif human_approved is True:
        # Aprovado - continua para finalizar_chamado
        logger.info(
            f"[Trace: {trace_id}] "
            f"[HUMAN-IN-THE-LOOP] APROVADO"
        )
        return {
            "status": "processing",
            "human_approved": True,
        }
    else:
        # Rejeitado - vai para finalizar_sem_acao
        logger.info(
            f"[Trace: {trace_id}] "
            f"[HUMAN-IN-THE-LOOP] REJEITADO"
        )
        return {
            "status": "rejected",
            "human_approved": False,
        }


# ============================================================
# 6. ROTEAMENTO APÓS AÇÃO HUMANA
# ============================================================

# [REMOVIDO - Usando a definição anterior]

# ============================================================
# 7. FERRAMENTA OPERACIONAL
# ============================================================

# ============================================================
# 8. FINALIZAÇÃO SEM AÇÃO
# ============================================================

def finalizar_sem_acao(state: GraphState, config: RunnableConfig = None) -> GraphState:
    """
    Finaliza a execução sem executar ação operacional.

    Para um chamado crítico rejeitado, retorna status=rejected.
    """
    return {
        "status": "rejected",
    }


def finalizar_chamado(state: GraphState, config: RunnableConfig = None) -> GraphState:
    """
    Finalização terminal de um chamado efetivamente tratado.

    Somente este nó define status="completed".
    """
    return {
        "status": "completed",
        "error": None,
    }


def gerar_resposta(
    state: GraphState,
    config: RunnableConfig
) -> GraphState:

    trace_id = get_trace_id(config)

    logger.info(
        f"[Trace: {trace_id}] "
        f"[NODE] gerar_resposta"
    )

    llm = get_llm()

    structured_llm = llm.with_structured_output(
        TicketOutput
    )

    prompt = """
Crie um relatório estruturado de triagem para o chamado técnico.

CAMPOS OBRIGATÓRIOS:
- category: string (infraestrutura, aplicação, autenticação, outro)
- severity: string (baixa, média, crítica)
- summary: string (resumo claro do problema em 1-2 frases)
- suggested_action: string (ação específica e acionável)
- requires_human: boolean (CRUCIAL!)
  * true = APENAS se severity é "crítica" (perda de dados, produção completamente parada, segurança violada)
  * false = para tudo mais (login lento, reset de senha, bug em feature não-crítica)
  
EXEMPLOS:
- "Usuário não consegue fazer login" → severity=média, requires_human=FALSE (não é crítico)
- "Banco de dados está offline" → severity=crítica, requires_human=TRUE (produção parada)
- "Senha expirada" → severity=baixa, requires_human=FALSE (trivial)
- "Falha de BD no servidor de produção" → severity=crítica, requires_human=TRUE (crítico)

IMPORTANTE: requires_human=TRUE apenas para severity=CRÍTICA. Tudo mais é FALSE.

Dados do chamado:

"""

    prompt += f"Título: {state.get('ticket_title', '')}\n"
    prompt += f"Descrição: {state.get('ticket_description', '')}\n"
    prompt += f"Risco: {state.get('risk_level')}\n"
    prompt += f"Status: {state.get('status')}\n"
    prompt += (
        f"Aprovação humana: "
        f"{state.get('human_approved')}\n"
    )

    if state.get("context"):
        prompt += (
            f"Contexto recuperado da base: "
            f"{state['context']}\n"
        )

    if state.get("tool_output"):
        prompt += (
            f"Saída da ferramenta operacional: "
            f"{state['tool_output']}\n"
        )

    try:
        # Log do prompt completo antes de enviar ao LLM
        logger.info(
            f"[Trace: {trace_id}] "
            f"[PROMPT ENVIADO AO LLM]\n{prompt}"
        )

        response = structured_llm.invoke(prompt)

        logger.info(
            f"[Trace: {trace_id}] "
            f"[RESPOSTA DO LLM] {response}"
        )

        return {
            "structured_response": response
        }

    except Exception as e:

        logger.error(
            f"[Trace: {trace_id}] "
            f"[ERRO] Falha ao gerar resposta: {e}"
        )

        return {
            "error": str(e)
        }


# ============================================================
# 10. CONFIGURAÇÃO DO GRAFO
# ============================================================

def build_graph(checkpointer=None):
    """
    Constrói o grafo do atendimento com decisão baseada no LLM.

    Fluxo:
      1. analisar → classificar_risco → consultar_base → gerar_resposta
      2. Verifica requires_human da resposta:
         - Se True: aguardar_aprovacao_humana → [aprovado] finalizar_chamado → END
                                              → [rejeitado] finalizar_sem_acao → END
         - Se False: finalizar_chamado → END
    """
    workflow = StateGraph(GraphState)

    workflow.add_node("analisar_chamado", analisar_chamado)
    workflow.add_node("classificar_risco", classificar_risco)
    workflow.add_node("consultar_base", node_consultar_base)
    workflow.add_node("gerar_resposta", gerar_resposta)
    workflow.add_node("aguardar_aprovacao_humana", aguardar_aprovacao_humana)
    workflow.add_node("finalizar_chamado", finalizar_chamado)
    workflow.add_node("finalizar_sem_acao", finalizar_sem_acao)

    workflow.set_entry_point("analisar_chamado")

    # Fluxo linear até gerar resposta
    workflow.add_edge("analisar_chamado", "classificar_risco")
    workflow.add_edge("classificar_risco", "consultar_base")
    workflow.add_edge("consultar_base", "gerar_resposta")

    # Após gerar resposta, verifica requires_human do LLM
    workflow.add_conditional_edges(
        "gerar_resposta",
        route_after_llm_response,
        {
            "aguardar_aprovacao_humana": "aguardar_aprovacao_humana",
            "finalizar_chamado": "finalizar_chamado",
        },
    )

    # Fluxo de aprovação humana
    workflow.add_conditional_edges(
        "aguardar_aprovacao_humana",
        route_human_decision,
        {
            "finalizar_chamado": "finalizar_chamado",
            "finalizar_sem_acao": "finalizar_sem_acao",
        },
    )

    # Terminações
    workflow.add_edge("finalizar_chamado", END)
    workflow.add_edge("finalizar_sem_acao", END)

    if checkpointer is None:
        checkpointer = InMemorySaver()

    return workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=["aguardar_aprovacao_humana"]
    )

def get_graph():
    """Retorna um grafo compilado."""
    return build_graph()

