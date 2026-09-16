from typing import TypedDict, Annotated, Optional
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
    risk_level: Optional[str]  # "simples" ou "critico"
    context: Optional[str]
    tool_output: Optional[str]
    structured_response: Optional[TicketOutput]
    error: Optional[str]
