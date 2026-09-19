import logging
import uuid

from src.graph import build_graph


def run_scenario(title: str, description: str, thread_id: str):
    print(f"\n{'='*50}\nIniciando cenário para o chamado: '{title}'")
    graph = build_graph()
    config = {"configurable": {"thread_id": thread_id}}
    
    initial_state = {
        "ticket_title": title,
        "ticket_description": description
    }
    
    # Executa o grafo até terminar ou ser interrompido
    for event in graph.stream(initial_state, config=config, stream_mode="values"):
        # Loga os passos conforme avança
        if "risk_level" in event and not "context" in event and not "tool_output" in event:
            print(f"--> Risco classificado: {event['risk_level']}")
    
    # Verifica o estado final (não apenas se foi pausado)
    final_state = graph.get_state(config).values
    
    # Verifica se o fluxo foi interrompido (Human-in-the-loop aguardando resposta)
    state_snapshot = graph.get_state(config)
    if state_snapshot.next:
        print("\n[ALERTA DE SEGURANÇA] O grafo foi pausado por segurança. Ferramenta crítica pendente: ", state_snapshot.next)
        aprovar = input("Deseja aprovar a execução da ferramenta? (s/n): ")
        if aprovar.lower() == 's':
            print("Execução aprovada. Continuando fluxo...")
            for event in graph.stream(None, config=config, stream_mode="values"):
                pass
            final_state = graph.get_state(config).values
        else:
            print("Execução rejeitada. Fluxo abortado.")
            final_state = graph.get_state(config).values
    
    # Pega o estado final e verifica o status
    print(f"\n[DEBUG] Estado final do grafo: status={final_state.get('status')}, human_approved={final_state.get('human_approved')}")
    
    if final_state.get("error"):
        print("\n[FALHA] O fluxo encontrou um erro:", final_state["error"])
    elif final_state.get("status") == "waiting_human_action":
        print("\n[STATUS] Chamado crítico aguardando ação humana (aprovação rejeitada ou pendente)")
        print("  Resposta Estruturada:")
        if final_state.get("structured_response"):
            resp = final_state["structured_response"]
            print(f"    Categoria: {resp.category}")
            print(f"    Severidade: {resp.severity}")
            print(f"    Resumo: {resp.summary}")
            print(f"    Ação Sugerida: {resp.suggested_action}")
            print(f"    Precisa de Humano?: {resp.requires_human}")
        else:
            print("    (Aguardando interação humana)")
    elif final_state.get("structured_response"):
        resp = final_state["structured_response"]
        print("\n[RESULTADO] Resposta Estruturada:")
        print(f"  Categoria: {resp.category}")
        print(f"  Severidade: {resp.severity}")
        print(f"  Resumo: {resp.summary}")
        print(f"  Ação Sugerida: {resp.suggested_action}")
        print(f"  Precisa de Humano?: {resp.requires_human}")
    else:
        print("\n[STATUS] Estado final não reconhecido")
        print(f"  {final_state}")

if __name__ == "__main__":
    logging.getLogger("TriagemAgente").setLevel(logging.WARNING) # Suprime logs verbosos para a CLI
    
    # Cenário 1: Fluxo Principal (Chamado simples, vai usar a base de conhecimento)
    run_scenario(
        "Problema de login no sistema",
        "Usuário relata que não consegue acessar o portal com sua senha antiga.",
        thread_id=str(uuid.uuid4())
    )
    
    # Cenário 2: Cenário Crítico (Requer Human-in-the-loop)
    run_scenario(
        "TICKET-999 Base de dados corrompida",
        "A base de dados de permissões está corrompida, precisamos invalidar o cache urgentemente.",
        thread_id=str(uuid.uuid4())
    )
    
    # Cenário 3: Falha/Entrada Inválida
    run_scenario(
        "12",
        "Problema",
        thread_id=str(uuid.uuid4())
    )
