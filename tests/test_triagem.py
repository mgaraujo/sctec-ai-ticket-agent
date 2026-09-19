from src.graph import route_risk
from src.tools import consultar_base, consultar_tool


def test_consultar_base_sucesso():
    # Caminho de sucesso - base de conhecimento
    resultado = consultar_base.invoke({"query": "vpn"})
    assert "rotas incorretas" in resultado
    
def test_consultar_tool_falha():
    # Falha/Entrada inválida - id muito curto
    resultado = consultar_tool.invoke({"ticket_id": "12", "action": "restart"})
    assert "inválido" in resultado.lower()

def test_comportamento_grafo_roteamento():
    # Comportamento relevante do grafo (Roteamento condicional)
    state_simples = {"risk_level": "simples"}
    state_critico = {"risk_level": "critico"}
    
    # Testa a decisão de roteamento
    assert route_risk(state_simples) == "consultar_base"
    # Chamados críticos devem ir para aguardar_aprovacao_humana, não diretamente para consultar_tool
    assert route_risk(state_critico) == "aguardar_aprovacao_humana"
