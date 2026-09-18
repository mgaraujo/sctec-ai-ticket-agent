from typing import TypedDict

from pydantic import BaseModel, Field


class TicketOutput(BaseModel):
    category: str = Field(description="Categoria do chamado (ex: infraestrutura, permissão, etc)")
    severity: str = Field(description="Severidade ou prioridade do chamado (baixa, média, alta, crítica)")
    summary: str = Field(description="Resumo do problema")
    suggested_action: str = Field(description="Ação sugerida para resolver")
    requires_human: bool = Field(description="Se precisa de intervenção humana")

class GraphState(TypedDict):
    ticket_title: str
    ticket_description: str
    risk_level: str | None  # "simples" ou "critico"
    context: str | None
    tool_output: str | None
    structured_response: TicketOutput | None
    error: str | None
