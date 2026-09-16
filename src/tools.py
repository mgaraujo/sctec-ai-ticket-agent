import os
from langchain_core.tools import tool

# Mock database
KNOWLEDGE_BASE = {
    "login": "Para problemas de login, instrua o usuário a limpar o cache ou redefinir a senha.",
    "vpn": "Problemas de VPN geralmente ocorrem devido a rotas incorretas. Verificar configurações do client."
}

@tool
def consultar_base(query: str) -> str:
    """Consulta a base de conhecimento para problemas conhecidos e simples.
    
    Args:
        query: Termo de busca (ex: 'login', 'vpn')
    """
    query = query.lower()
    for key, value in KNOWLEDGE_BASE.items():
        if key in query:
            return value
    return "Nenhum artigo encontrado na base de conhecimento para este problema."

@tool
def consultar_tool(ticket_id: str, action: str) -> str:
    """Ferramenta operacional crítica para chamados complexos. Pode alterar estado.
    Exige validação.
    
    Args:
        ticket_id: ID do chamado
        action: Ação a ser executada (ex: 'restart_server', 'invalidate_permission_cache')
    """
    if not ticket_id or len(ticket_id) < 3:
        # Condição de falha/erro
        return "Erro: ID do chamado inválido. Deve ter pelo menos 3 caracteres."
    
    if action == "invalidate_permission_cache":
        return f"Sucesso: Cache de permissão invalidado para o contexto do ticket {ticket_id}."
    elif action == "restart_server":
        return f"Sucesso: Comando de reinício enviado para o servidor afetado no ticket {ticket_id}."
    else:
        return f"Aviso: Ação '{action}' não reconhecida pela ferramenta operacional."
