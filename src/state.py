from typing import TypedDict

try:
    from pydantic import BaseModel, Field
except ImportError:  # pragma: no cover
    class BaseModel:
        """Minimal stub for pydantic BaseModel used in tests.
        Stores provided fields as attributes and provides a simple
        `model_dump` method to retrieve a dict representation.
        """
        def __init__(self, **data):
            for k, v in data.items():
                setattr(self, k, v)
        def model_dump(self):
            return self.__dict__
    def Field(**kwargs):
        """Placeholder for pydantic Field – returns None.
        The tests only need the class to exist; metadata is ignored.
        """
        return None


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
