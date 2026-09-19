from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.api import app
from src.graph import route_after_llm_response, route_human_decision
from src.state import TicketOutput
from src.tools import consultar_base


def test_consultar_base_sucesso():
    """Teste de sucesso: base de conhecimento retorna resultado."""
    resultado = consultar_base.invoke({"query": "login"})
    assert isinstance(resultado, str)
    assert len(resultado) > 0
    assert "login" in resultado.lower() or "cache" in resultado.lower()


def test_comportamento_roteamento_after_llm():
    """Testa route_after_llm_response com requires_human=True."""
    # Mock de resposta com requires_human=True (crítico)
    class MockResponseCritico:
        requires_human = True

    state_critico = {"structured_response": MockResponseCritico()}
    assert route_after_llm_response(state_critico) == "aguardar_aprovacao_humana"

    # Mock de resposta com requires_human=False (simples)
    class MockResponseSimples:
        requires_human = False

    state_simples = {"structured_response": MockResponseSimples()}
    assert route_after_llm_response(state_simples) == "finalizar_chamado"


def test_comportamento_roteamento_human_decision():
    """Testa route_human_decision com aprovação e rejeição."""
    # Aprovado
    state_aprovado = {"human_approved": True}
    assert route_human_decision(state_aprovado) == "finalizar_chamado"

    # Rejeitado
    state_rejeitado = {"human_approved": False}
    assert route_human_decision(state_rejeitado) == "finalizar_sem_acao"


@patch("src.graph.get_llm")
def test_sucesso_chamado_simples(mock_get_llm):
    """Fluxo principal: chamado simples vai direto para completed."""
    # Mock do LLM para retornar uma resposta simples (não-crítica)
    mock_llm = MagicMock()
    mock_response = TicketOutput(
        category="autenticação",
        severity="média",
        summary="Problema de login do usuário",
        suggested_action="Resetar senha do usuário",
        requires_human=False
    )
    mock_llm.with_structured_output.return_value.invoke.return_value = mock_response
    mock_get_llm.return_value = mock_llm

    client = TestClient(app)
    response = client.post(
        "/triagem",
        json={
            "title": "Problema de login",
            "description": "Um usuário não consegue fazer login no sistema",
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "completed"
    assert "response" in result
    assert result["response"]["requires_human"] is False


def test_falha_entrada_invalida():
    """Validação: entrada inválida retorna erro 422."""
    client = TestClient(app)

    # Title muito curto
    response = client.post(
        "/triagem",
        json={
            "title": "AB",
            "description": "Descrição válida com mais de 10 caracteres",
        },
    )
    assert response.status_code == 422

    # Description muito curta
    response = client.post(
        "/triagem",
        json={"title": "Título válido", "description": "Desc"},
    )
    assert response.status_code == 422


@patch("src.graph.get_llm")
def test_chamado_critico_pendente(mock_get_llm):
    """Human-in-the-Loop: chamado crítico retorna pending_human_approval."""
    # Mock do LLM para retornar uma resposta crítica
    mock_llm = MagicMock()
    mock_response = TicketOutput(
        category="infraestrutura",
        severity="crítica",
        summary="Banco de dados offline",
        suggested_action="Restaurar BD de backup",
        requires_human=True
    )
    mock_llm.with_structured_output.return_value.invoke.return_value = mock_response
    mock_get_llm.return_value = mock_llm

    client = TestClient(app)
    response = client.post(
        "/triagem",
        json={
            "title": "Banco de dados não responde",
            "description": "BD crítico está offline, produção parada",
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "pending_human_approval"
    assert "thread_id" in result


@patch("src.graph.get_llm")
def test_aprovacao_chamado_critico(mock_get_llm):
    """Aprovação: crítico com aprovação retorna completed."""
    # Mock do LLM para retornar uma resposta crítica
    mock_llm = MagicMock()
    mock_response = TicketOutput(
        category="infraestrutura",
        severity="crítica",
        summary="Falha crítica de BD",
        suggested_action="Executar plano de recuperação",
        requires_human=True
    )
    mock_llm.with_structured_output.return_value.invoke.return_value = mock_response
    mock_get_llm.return_value = mock_llm

    client = TestClient(app)

    # Criar chamado crítico
    response = client.post(
        "/triagem",
        json={
            "title": "Falha crítica de BD",
            "description": "BD está completamente offline",
        },
    )
    result = response.json()
    thread_id = result["thread_id"]

    # Aprovar
    response = client.post(
        f"/triagem/{thread_id}/approve", json={"approve": True}
    )

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "completed"
    assert result["response"]["requires_human"] is True


@patch("src.graph.get_llm")
def test_rejeicao_chamado_critico(mock_get_llm):
    """Rejeição: crítico rejeitado retorna rejected."""
    # Mock do LLM para retornar uma resposta crítica
    mock_llm = MagicMock()
    mock_response = TicketOutput(
        category="infraestrutura",
        severity="crítica",
        summary="Falha crítica de infra",
        suggested_action="Restaurar servidor",
        requires_human=True
    )
    mock_llm.with_structured_output.return_value.invoke.return_value = mock_response
    mock_get_llm.return_value = mock_llm

    client = TestClient(app)

    # Criar chamado crítico
    response = client.post(
        "/triagem",
        json={
            "title": "Infra crítica falha",
            "description": "Servidor de produção está fora",
        },
    )
    result = response.json()
    thread_id = result["thread_id"]

    # Rejeitar
    response = client.post(
        f"/triagem/{thread_id}/approve", json={"approve": False}
    )

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "rejected"

