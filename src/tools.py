try:
    from langchain_core.tools import tool
except ImportError:  # pragma: no cover
    def tool(fn):
        """Simple fallback decorator that wraps a function in an object exposing a callable and .invoke method."""
        class ToolWrapper:
            def __init__(self, func):
                self._func = func
            def __call__(self, *args, **kwargs):
                return self._func(*args, **kwargs)
            def invoke(self, inputs: dict):
                return self._func(**inputs)
        return ToolWrapper(fn)

import requests

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
    Exige validação de entrada e realiza chamada a webhook externo.
    
    Args:
        ticket_id: ID do chamado
        action: Ação a ser executada (ex: 'restart_server', 'invalidate_permission_cache')
    """
    if not ticket_id or len(ticket_id) < 3:
        # Condição de falha/erro de validação
        return "Erro: ID do chamado inválido. Deve ter pelo menos 3 caracteres."
    
    # Tratamento de falhas: Simulação de chamada HTTP (Webhook) que pode falhar
    try:
        # Simula um endpoint que retorna erro 500 caso seja um ticket especifico de erro, ou time-out
        if "erro-http" in ticket_id.lower():
            response = requests.post("https://httpbin.org/status/500", timeout=2)
            response.raise_for_status()
    except requests.exceptions.RequestException as e:
        # Falha HTTP/Webhook tratada de forma controlada sem estourar exceção para o agente
        return f"Erro de integração (Webhook falhou): Falha ao contatar serviço externo. Detalhe: {e!s}"
    
    if action == "invalidate_permission_cache":
        return f"Sucesso: Cache de permissão invalidado para o contexto do ticket {ticket_id}."
    elif action == "restart_server":
        return f"Sucesso: Comando de reinício enviado para o servidor afetado no ticket {ticket_id}."
    else:
        return f"Aviso: Ação '{action}' não reconhecida pela ferramenta operacional."
