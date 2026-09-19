# Quick Start - 5 Minutos para Avaliar

**Objetivo:** Executar, testar e demonstrar a solução em 5 minutos

---

## 1. Setup (1 min)

```bash
# Clonar
git clone <seu-repo>
cd recuperacao_agente

# Ambiente
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configuração
cp .env.example .env
# Adicionar sua OPENAI_API_KEY no .env
```

---

## 2. Rodar Testes (1 min)

```bash
pytest tests/ -v

# Esperado: 6/6 PASSED
```

**O que valida:**
- ✅ Fluxo principal funciona
- ✅ Roteamento está correto
- ✅ Human-in-the-loop funciona
- ✅ Validação de entrada funciona

---

## 3. Iniciar API (em terminal separado)

```bash
uvicorn src.api:app --reload

# Esperado: "Uvicorn running on http://127.0.0.1:8000"
```

---

## 4. Teste 1: Chamado Simples (1 min)

**Terminal novo:**

```bash
curl -X POST http://localhost:8000/triagem \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Problema de login",
    "description": "Um usuário não consegue fazer login no sistema"
  }'
```

**Resposta esperada:**
```json
{
  "status": "completed",
  "thread_id": "...",
  "response": {
    "category": "autenticação",
    "severity": "média",
    "summary": "Falha de autenticação do usuário.",
    "suggested_action": "...",
    "requires_human": false
  }
}
```

**Validação:** ✅ Status=completed (não requer aprovação)

---

## 5. Teste 2: Chamado Crítico + Aprovação (2 min)

### Parte A: Submeter
```bash
curl -X POST http://localhost:8000/triagem \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Banco de dados não responde",
    "description": "BD crítico está offline, produção parada"
  }'
```

**Resposta:**
```json
{
  "status": "pending_human_approval",
  "thread_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Validação:** ✅ Status=pending_human_approval (workflow PAUSADO)

### Parte B: Aprovar (usando thread_id anterior)
```bash
curl -X POST http://localhost:8000/triagem/550e8400-e29b-41d4-a716-446655440000/approve \
  -H "Content-Type: application/json" \
  -d '{"approve": true}'
```

**Resposta:**
```json
{
  "status": "completed",
  "thread_id": "550e8400-e29b-41d4-a716-446655440000",
  "response": {
    "category": "infraestrutura",
    "severity": "crítica",
    "requires_human": true
  }
}
```

**Validação:** ✅ Status=completed (workflow RETOMOU)

---

## Checklist Rápido de Validação

- ✅ **Testes**: 6/6 passando
- ✅ **Fluxo Simples**: POST /triagem → completed
- ✅ **Fluxo Crítico**: POST /triagem → pending_human_approval
- ✅ **Aprovação**: POST /approve → completed
- ✅ **Validação**: Title < 3 chars → HTTP 422
- ✅ **Segurança**: "ignore instructions" → HTTP 422

---

## Documentação Para Ler

| Arquivo | Tempo | Conteúdo |
|---------|-------|----------|
| **README.md** | 10 min | Completo, arquitetura, código |
| **ROTEIRO_APRESENTACAO.md** | 10 min | Script com exemplos |
| **EXEMPLOS_API.md** | 5 min | 20+ exemplos curl |
| **QA_COM_IA.md** | 5 min | Iteração com IA |
| **SUMARIO_EXECUTIVO.md** | 3 min | Overview executivo |

---

## Estrutura do Projeto

```
recuperacao_agente/
├── src/
│   ├── api.py              ← FastAPI endpoints
│   ├── graph.py            ← LangGraph fluxo
│   ├── state.py            ← GraphState TypedDict
│   ├── tools.py            ← Tool funcional
│   ├── history.py          ← Persistência
│   └── data/
│       └── tickets_history.json
├── tests/
│   └── test_triagem.py     ← 6 testes
├── docs/
│   ├── ROTEIRO_APRESENTACAO.md
│   ├── EXEMPLOS_API.md
│   ├── QA_COM_IA.md
│   └── SUMARIO_EXECUTIVO.md
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md               ← LEIA ISTO
└── QUICK_START.md          ← Este arquivo

```

---

## Pontos-Chave Para o Avaliador

### 1. Fluxo LangGraph
📍 Arquivo: `src/graph.py`  
📝 Procure por: `build_graph()`, nodes, edges, roteadores

### 2. State Compartilhado
📍 Arquivo: `src/state.py`  
📝 Procure por: `GraphState` TypedDict

### 3. Tool Funcional
📍 Arquivo: `src/tools.py`  
📝 Procure por: `consultar_base()` function

### 4. API REST
📍 Arquivo: `src/api.py`  
📝 Procure por: `/triagem` e `/triagem/{id}/approve` endpoints

### 5. Testes
📍 Arquivo: `tests/test_triagem.py`  
📝 Procure por: 6 test functions cobrindo todos cenários

### 6. Human-in-the-Loop
📍 Local: `src/graph.py` linha ~45  
📝 Procure por: `interrupt_before=["aguardar_aprovacao_humana"]`

### 7. Memória Persistente
📍 Local: `src/api.py` linha ~20  
📝 Procure por: `_graph_store = {}`

---

## Perguntas Frequentes (Pronto para Responder)

**P: Como o agente decide se é crítico?**  
R: LLM decide via `requires_human` na resposta estruturada. Não usamos palavras-chave.

**P: O que significa "pending_human_approval"?**  
R: Workflow parou em `aguardar_aprovacao_humana` (interrupt_before). Aguarda POST /approve.

**P: Como retoma o workflow?**  
R: `graph.update_state()` define `human_approved=true/false`, então `graph.stream()` retoma.

**P: Onde está a base de conhecimento?**  
R: `src/data/tickets_history.json`. É um RAG simulado em arquivo JSON.

**P: Como garante segurança?**  
R: Validação de entrada, proteção contra prompt injection, tratamento de exceções.

---

## Tempo Esperado

- Setup: 1 min
- Testes: 1 min  
- Teste Simples: 1 min
- Teste Crítico + Aprovação: 2 min
- **Total: 5 minutos** ✅

---

**Pronto? Comece pelo passo 1!** 🚀
