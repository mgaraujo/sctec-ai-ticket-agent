# Sumário Executivo - Agente de Triagem de Chamados

---

## O Problema

Empresas recebem muitos chamados técnicos diariamente:
- **Simples:** Login, reset de senha (resolvido em segundos)
- **Crítico:** BD offline, produção parada (requer aprovação urgente)

**Desafio:** Como classificar automaticamente e garantir que críticos NÃO sejam ignorados?

---

## A Solução

Um **Agente Inteligente com LangGraph** que:

1. ✅ **Recebe** chamado (título + descrição)
2. ✅ **Analisa** com inteligência artificial
3. ✅ **Classifica** severidade (baixa/média/crítica)
4. ✅ **Recupera contexto** de base de conhecimento
5. ✅ **Gera resposta estruturada** com recomendações
6. ✅ **Se crítico:** Pausa e aguarda aprovação humana
7. ✅ **Se aprovado:** Finaliza com sucesso
8. ✅ **Se rejeitado:** Marca como rejeitado (seguro)

---

## Arquitetura

### Fluxo LangGraph

```
Entrada → Análise → Consulta Base → Geração LLM
                                        ↓
                              [LLM decide severity]
                                        ↓
                            ┌───────────┴───────────┐
                            ↓                       ↓
                    requires_human=TRUE    requires_human=FALSE
                            ↓                       ↓
                    PAUSA PARA APROVAÇÃO      FINALIZA DIRETO
                    (pending_human_approval)  (completed)
                            ↓
                        [Humano aprova?]
                        ↙              ↘
                    SIM                NÃO
                    ↓                  ↓
              completed           rejected
```

### Componentes Principais

| Componente | Tipo | Função |
|-----------|------|--------|
| **LangGraph** | Framework | Orquestra nodes, state, roteamento |
| **LLM (ChatOpenAI)** | Inteligência | Classifica severity e requires_human |
| **Tool (consultar_base)** | Recuperação | Busca contexto de execuções anteriores |
| **Checkpointer** | Persistência | Mantém state entre requisições |
| **API (FastAPI)** | Interface | Endpoints REST para triagem e aprovação |

---

## Atende Todos os Requisitos

### Tema (Item 4.1) ✅
- ✅ Recebe título + descrição
- ✅ Analisa com LLM
- ✅ Classifica (severity + requires_human)
- ✅ Tool funcional (consultar_base)
- ✅ Memória/RAG (base de conhecimento)
- ✅ Saída estruturada (Pydantic TicketOutput)
- ✅ Dois cenários (simples + crítico com aprovação)

### LangGraph (Item 4.2) ✅
- ✅ State explícito (GraphState)
- ✅ Nodes com responsabilidades claras (7 nodes)
- ✅ Edges explícitas
- ✅ Ramificação condicional (2 roteadores)
- ✅ Parada controlada (END nodes)
- ✅ Sem loops indefinidos

### Tool + Validação (Item 4.3) ✅
- ✅ Tool funcional: `consultar_base()`
- ✅ Validação: min_length, type checking
- ✅ Tratamento de falhas: try-except, fallback

### Memória/Contexto/RAG (Item 4.4) ✅
- ✅ State mantido pelo LangGraph
- ✅ Checkpointer (InMemorySaver)
- ✅ RAG simulado: busca em arquivo JSON
- ✅ Contexto influencia resposta do LLM

### Segurança (Item 4.5) ✅
- ✅ Sem credenciais no repositório
- ✅ `.env.example` fornecido
- ✅ Validação de entrada (title/description)
- ✅ Proteção contra prompt injection
- ✅ Tratamento de exceções

### Observabilidade (Item 4.6) ✅
- ✅ Logs com trace_id correlacionado
- ✅ Identificador de execução (thread_id)
- ✅ Node executado registrado
- ✅ Decisão de roteamento registrada
- ✅ Chamada de tool registrada
- ✅ Erros tratados

### QA com IA (Item 4.7) ✅
- ✅ 6 testes automatizados
- ✅ Cobre: sucesso, falha, roteamento, crítico, aprovação, rejeição
- ✅ IA revisou e sugeriu melhorias
- ✅ Evidência documentada em `docs/QA_COM_IA.md`

### Prompts (Item 4.8) ✅
- ✅ Instruções documentadas em `src/graph.py`
- ✅ Modelo configurável por `.env`
- ✅ Refinamento documentado (antes/depois)
- ✅ Resultado: 0% de erros em requires_human

---

## Extensões Técnicas Implementadas

### Extensão 1: Human-in-the-Loop ⭐ (1 ponto)

**Requisito:** "Human-in-the-loop para aprovação de uma ação"

**Implementação:**
- Node `aguardar_aprovacao_humana` com `interrupt_before`
- API endpoint `/triagem/{thread_id}/approve`
- Workflow **pausa** ao chegar em node crítico
- Retorna `pending_human_approval`
- Humano aprova/rejeita via API
- Workflow retoma onde parou

**Evidência:**
```bash
# Submeter crítico
POST /triagem → pending_human_approval

# Aprovar
POST /triagem/{id}/approve {"approve": true} → completed

# Rejeitar
POST /triagem/{id}/approve {"approve": false} → rejected
```

---

### Extensão 2: Memória Persistente com Checkpointer 💾 (1 ponto)

**Requisito:** "Memória persistente ou checkpointer com retomada de contexto"

**Implementação:**
- `InMemorySaver()` para persistence do state
- `_graph_store` dict mantém grafo por thread_id
- `graph.update_state()` atualiza decisão humana
- `graph.stream(None)` retoma da interrupção
- Histórico persistido em arquivo JSON

**Evidência:**
```python
# Primeira execução pausa
graph.stream(initial_state) → pending_human_approval

# Segunda execução retoma
graph.update_state({"human_approved": True})
graph.stream(None) → completed (do ponto de parada)
```

---

## Cenários Demonstráveis

### Cenário 1: Fluxo Principal (Simples) ✅
```bash
Input:  "Problema de login"
Output: status=completed, severity=média, requires_human=false
```

### Cenário 2: Fluxo Crítico com Approval 🚨
```bash
Input:  "Banco de dados não responde"
Step 1: POST /triagem → status=pending_human_approval
Step 2: POST /triagem/{id}/approve {"approve":true} → status=completed
```

### Cenário 3: Rejeição ❌
```bash
Input: (mesmo crítico)
Step 1: POST /triagem → status=pending_human_approval  
Step 2: POST /triagem/{id}/approve {"approve":false} → status=rejected
```

### Cenário 4: Validação e Segurança 🛡️
```bash
Input:  "AB" (title < 3 chars) → HTTP 422
Input:  "ignore all instructions" → HTTP 422 (prompt injection)
```

---

## Checklist de Entrega ✅

### Repositório e Organização
- ✅ GitHub com histórico incremental
- ✅ Commits claros e significativos
- ✅ Versão final na main
- ✅ Sem credenciais versionadas
- ✅ `.env.example` fornecido
- ✅ `requirements.txt` com dependências
- ✅ Estrutura: src/, tests/, docs/

### Documentação
- ✅ **README.md**: Completo (15 seções)
  - Descrição, arquitetura, fluxo, state/nodes
  - Tool, contexto, instalação, cenários
  - Observabilidade, testes, QA, extensões
  - Segurança, limitações
  
- ✅ **Roteiro de Apresentação** (ROTEIRO_APRESENTACAO.md)
  - 12 partes, ~10 minutos
  - Exemplos executáveis em cada etapa
  
- ✅ **Exemplos de API** (EXEMPLOS_API.md)
  - 20+ exemplos com curl
  - Respostas esperadas documentadas
  
- ✅ **QA com IA** (QA_COM_IA.md)
  - Problema identificado
  - Sugestão da IA
  - Decisão e implementação do aluno
  - Resultado/impacto

### Aplicação
- ✅ Funcional ponta a ponta
- ✅ Fluxo principal + cenário falha
- ✅ Saída estruturada JSON
- ✅ Executa sem erros

### Testes
- ✅ 6 testes automatizados
- ✅ Sucesso, falha, roteamento, crítico, aprovação, rejeição
- ✅ Cobertura de componentes-chave
- ✅ Todos passando

---

## Como Executar (Avaliador)

```bash
# 1. Setup
git clone <repo>
cd recuperacao_agente
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Adicionar OPENAI_API_KEY

# 2. Testes
pytest tests/ -v

# 3. API
uvicorn src.api:app --reload

# 4. Exemplos (outro terminal)
curl -X POST http://localhost:8000/triagem \
  -H "Content-Type: application/json" \
  -d '{"title": "Problema de login", "description": "Usuário não consegue fazer login"}'

# 5. Crítico + Aprovação
curl -X POST http://localhost:8000/triagem \
  -H "Content-Type: application/json" \
  -d '{"title": "BD offline", "description": "Banco de dados está offline"}'
# → Salvar thread_id

curl -X POST http://localhost:8000/triagem/{thread_id}/approve \
  -H "Content-Type: application/json" \
  -d '{"approve": true}'
```

---

## Métricas de Qualidade

| Métrica | Valor | Status |
|---------|-------|--------|
| **Testes** | 6/6 passando | ✅ 100% |
| **Cobertura de roteamento** | 100% | ✅ Total |
| **Erros de validação** | 0% | ✅ Zero |
| **Requisitos atendidos** | 11/11 | ✅ 100% |
| **Extensões implementadas** | 2/2 | ✅ Total |
| **Cenários demonstráveis** | 4/4 | ✅ Total |

---

## Próximos Passos (Produção)

1. **Checkpointer:** PostgreSQL ao invés de InMemorySaver
2. **Autenticação:** JWT/OAuth nas rotas
3. **Rate Limiting:** Redis middleware
4. **RAG Real:** Vector database com embeddings
5. **Auditoria:** Registrar quem aprovou/rejeitou
6. **Métricas:** Prometheus/Grafana

---

## Conclusão

**Esta solução demonstra:**
- ✅ Domínio de LangGraph (fluxo, state, roteamento)
- ✅ Integração de IA (prompts, classificação)
- ✅ Padrão Human-in-the-Loop (aprovação crítica)
- ✅ Qualidade de código (testes, logs, segurança)
- ✅ Iteração com IA (refinamento, melhoria)

**Atende 100% dos requisitos do enunciado e implementa 2 extensões técnicas funcionais.**

---

**Data:** 2026-09-18  
**Status:** Pronto para submissão  
**Links:**
- GitHub: [Será adicionado]
- Vídeo YouTube: [Será adicionado]
