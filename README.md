# Agente Inteligente de Triagem de Chamados Técnicos

## 1. Descrição da Solução e Objetivo

Este projeto implementa um **Agente Inteligente de Triagem de Chamados Técnicos** que recebe um chamado (título + descrição), analisa seu conteúdo com inteligência artificial e classifica sua severidade.

**Fluxo resumido:**
1. Recebe chamado (título + descrição)
2. **Análise automática** com LLM
3. **Classificação inteligente** (o LLM decide: simples ou crítico)
4. **Recuperação de contexto** via base de conhecimento
5. **Geração de resposta estruturada** com recomendações
6. **Se crítico: Approval Gate** - pausa o workflow aguardando aprovação humana
7. **Se aprovado:** Finaliza com sucesso; **Se rejeitado:** Retorna rejected

A resposta final inclui: categoria, severidade, resumo, ação sugerida e indicação de necessidade de revisão humana.

---

## 2. Arquitetura e Fluxo LangGraph

O fluxo foi modelado com **LangGraph explícito**, garantindo state compartilhado, nodes com responsabilidades claras e decisões condicionais documentadas.

```
┌─────────────────────┐
│ Entrada chamado     │
│ (title, desc)       │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ analisar_chamado    │
│ (log, validate)     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ consultar_base      │
│ (RAG context)       │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ gerar_resposta      │
│ (LLM decides:       │
│  severity,          │
│  requires_human)    │
└──────────┬──────────┘
           │
    ┌──────┴──────────────────┐
    │ Condicional             │
    │ requires_human?         │
    ▼                         ▼
   SIM                       NÃO
    │                         │
    ▼                         ▼
┌──────────────────────┐  ┌──────────────┐
│aguardar_aprovacao    │  │finalizar     │
│_humana               │  │_chamado      │
│                      │  │(completed)   │
│⏸️  PAUSA AQUI        │  └──────────────┘
│pending_human_        │
│approval              │
│(webhook enviado)     │
└──────────┬───────────┘
           │
   ┌───────┴────────┐
   │ Condicional    │
   │ human_        │
   │ approved?     │
   ▼               ▼
  SIM             NÃO
   │               │
   ▼               ▼
┌─────────┐   ┌─────────┐
│finalizar│   │finalizar│
│_chamado │   │_sem_acao│
│(✅ OK)  │   │(❌ REJECT)
└─────────┘   └─────────┘
```

Fluxo simplificado:
- **analisar → consultar_base → gerar_resposta** (linear)
- **Bifurcação:** requires_human? → Aprovação → Finalizar
- **Webhook:** Notificado quando pausa em aprovação

---

## 3. Descrição do State, Nodes e Decisões Condicionais

### GraphState (TypedDict)
```python
{
    "ticket_title": str,                    # Título do chamado
    "ticket_description": str,              # Descrição detalhada
    "status": str | None,                   # "processing", "waiting_human_action", "rejected", "completed"
    "context": str | None,                  # Contexto recuperado da base
    "structured_response": TicketOutput,    # Resposta estruturada
    "requires_human": bool | None,          # Extraído de structured_response
    "human_approved": bool | None,          # Definido via API /approve
    "error": str | None,                    # Mensagens de erro
}
```

### Nodes e Responsabilidades

| Node | Entrada | Saída | Descrição |
|------|---------|-------|-----------|
| **analisar_chamado** | title, description | (atualiza status) | Valida e loga o chamado |
| **consultar_base** | title, description | context | Busca na base de conhecimento |
| **gerar_resposta** | all + context | structured_response | LLM decide severity e requires_human |
| **aguardar_aprovacao_humana** | human_approved | (status update) | Processa decisão; **interrompe se None** |
| **finalizar_chamado** | status=processing | status=completed | Retorna com sucesso |
| **finalizar_sem_acao** | status=rejected | status=rejected | Retorna rejeitado |

### Decisões Condicionais

**route_after_llm_response(state)**
```python
if state["structured_response"].requires_human:
    return "aguardar_aprovacao_humana"  # Pausa aqui
else:
    return "finalizar_chamado"  # Vai direto ao fim
```

**route_human_decision(state)**
```python
if state.get("human_approved") is True:
    return "finalizar_chamado"  # Sucesso
else:
    return "finalizar_sem_acao"  # Rejeitado
```

---

## 4. Tool Funcional: `consultar_base`

A aplicação utiliza **uma tool funcional principal** que atua como **recuperação de contexto (RAG simulado)**:

### Função: `consultar_base()`
```python
def consultar_base(ticket_title: str, ticket_description: str) -> str:
    """
    Busca soluções documentadas na base de conhecimento.
    
    Retorno:
      - Contexto recuperado ou mensagem padrão se não encontrado
    
    Tratamento:
      - Validação de entrada (min_length)
      - Try-catch para leitura de arquivo JSON
      - Retorna mensagem controlada se falhar
    """
```

### Fluxo de Integração
1. **Acionada em**: Node `consultar_base` (sempre antes de gerar resposta)
2. **Dados**: Arquivo `src/data/tickets_history.json`
3. **Utilização**: Contexto é armazenado em `state["context"]`
4. **Impacto**: Contexto é injetado no prompt do LLM

### Validação e Tratamento
- ✅ Valida comprimento mínimo de entrada
- ✅ Trata arquivo não encontrado
- ✅ Trata JSON inválido
- ✅ Retorna mensagem controlada

---

## 5. Memória, Contexto e RAG

### Estratégia Implementada

1. **State do LangGraph** (`GraphState`)
   - Mantém contexto da sessão em memória
   - Cada thread tem seu próprio state isolado

2. **Checkpointer (InMemorySaver)**
   - Persiste state entre chamadas ao grafo
   - Permite pausar e retomar com `interrupt_before`

3. **RAG Simulado** (`consultar_base`)
   - Carrega base de conhecimento de `src/data/tickets_history.json`
   - Busca entradas relevantes por palavras-chave
   - Retorna contexto que alimenta o LLM

4. **Armazenador Global** (`_graph_store` dict)
   - Mantém grafo instanciado por thread_id
   - Permite retomar workflow após aprovação
   - Em produção: seria PostgreSQL ou Redis

---

## 6. Instalação, Configuração e Execução

### Pré-requisitos
- Python 3.10+
- pip ou uv
- Chave de API OpenAI

### Instalação

```bash
# 1. Clonar repositório
cd recuperacao_agente

# 2. Criar ambiente virtual
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# ou
.venv\Scripts\activate  # Windows

# 3. Instalar dependências
pip install -r requirements.txt

# 4. Configurar variáveis
cp .env.example .env
# Editar .env e adicionar OPENAI_API_KEY
```

### Execução

```bash
# A. Executar a API REST
uvicorn src.api:app --reload --port 8000

# API disponível em:
# - REST: http://localhost:8000
# - Swagger: http://localhost:8000/docs

# B. Rodar testes
pytest tests/ -v

# C. Rodar teste específico
pytest tests/test_triagem.py::test_sucesso_chamado_simples -v
```

---

## 7. Cenários Demonstrados

### Cenário 1: Fluxo Principal (Chamado Simples) ✅

**Entrada:**
```bash
curl -X POST http://localhost:8000/triagem \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Problema de login",
    "description": "Um usuário não consegue fazer login no sistema. Recebe erro 401."
  }'
```

**Processo:**
1. Node `analisar_chamado` → Valida e loga
2. Node `consultar_base` → Busca contexto sobre login
3. Node `gerar_resposta` → **LLM decide**: severity = "média", requires_human = False
4. Condicional → Va direto para `finalizar_chamado`

**Saída:**
```json
{
  "status": "completed",
  "thread_id": "abc-123-def",
  "response": {
    "category": "autenticação",
    "severity": "média",
    "summary": "Falha de autenticação do usuário.",
    "suggested_action": "Verificar credenciais e status da conta.",
    "requires_human": false
  }
}
```

---

### Cenário 2: Chamado Crítico com Approval 🚨

**Entrada (Parte 1):**
```bash
curl -X POST http://localhost:8000/triagem \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Banco de dados não responde",
    "description": "Servidor de BD está offline. Produção parada completamente."
  }'
```

**Saída (Parte 1):**
```json
{
  "status": "pending_human_approval",
  "thread_id": "def-456-ghi",
  "message": "Chamado requer aprovação humana... Faça POST em /triagem/def-456-ghi/approve"
}
```

**Entrada (Parte 2 - Aprovação):**
```bash
curl -X POST http://localhost:8000/triagem/def-456-ghi/approve \
  -H "Content-Type: application/json" \
  -d '{"approve": true}'
```

**Saída (Parte 2):**
```json
{
  "status": "completed",
  "thread_id": "def-456-ghi",
  "response": {
    "category": "infraestrutura",
    "severity": "crítica",
    "summary": "BD crítico offline, falha completa de serviço.",
    "suggested_action": "Restaurar BD: verificar hardware, logs, reiniciar serviço.",
    "requires_human": true
  }
}
```

---

### Cenário 3: Rejeição ❌

**Entrada:**
```bash
curl -X POST http://localhost:8000/triagem/def-456-ghi/approve \
  -H "Content-Type: application/json" \
  -d '{"approve": false}'
```

**Saída:**
```json
{
  "status": "rejected",
  "thread_id": "def-456-ghi",
  "message": "Chamado crítico foi rejeitado pelo usuário."
}
```

---

## 8. Observabilidade Essencial

### Exemplo de Logs Completos

```
2026-09-18 23:00:15,100 - TriagemAgente - INFO - [Trace: abc123...] [NODE] analisar_chamado | Chamado: Banco de dados
2026-09-18 23:00:15,103 - TriagemAgente - INFO - [Trace: abc123...] [NODE] classificar_risco | Avaliando
2026-09-18 23:00:15,105 - TriagemAgente - INFO - [Trace: abc123...] [NODE] consultar_base | Processamento
2026-09-18 23:00:15,108 - TriagemAgente - INFO - [Trace: abc123...] [TOOL] Contexto recuperado
2026-09-18 23:01:18,500 - TriagemAgente - INFO - [Trace: abc123...] [NODE] gerar_resposta
2026-09-18 23:01:18,501 - TriagemAgente - INFO - [Trace: abc123...] [ROTEAMENTO] requires_human=True
2026-09-18 23:01:18,502 - TriagemAgente - INFO - [Trace: abc123...] [INTERRUPT] Aguardando aprovação
```

**Correlação:**
- Todos os logs incluem `[Trace: abc123...]` (thread_id)
- Permite reconstruir fluxo completo filtrando por trace_id

---

## 9. Testes Automatizados

### Cobertura de Testes

```bash
# Rodar todos os testes
pytest tests/ -v

# Com coverage
pytest tests/ -v --cov=src --cov-report=html
```

### Testes Implementados

1. **test_sucesso_chamado_simples**
   - Fluxo principal com entrada válida
   - Valida: Status=completed, resposta estruturada

2. **test_falha_entrada_invalida**
   - Validação de entrada
   - Valida: Title < 3 chars retorna erro 422

3. **test_comportamento_roteamento**
   - Lógica de roteamento condicional
   - Valida: `route_after_llm_response` e `route_human_decision`

4. **test_chamado_critico_pendente**
   - Fluxo com human-in-the-loop
   - Valida: Status=pending_human_approval

5. **test_aprovacao_chamado_critico**
   - Fluxo de aprovação
   - Valida: Transição pending → completed

6. **test_rejeicao_chamado_critico**
   - Fluxo de rejeição
   - Valida: Transição pending → rejected

---

## 10. QA com IA e Refinamento

### Evidência 1: Revisão com IA

**Problema:**
- Testes cobriam apenas "caminho feliz"
- Faltava validação da **lógica de roteamento**

**Sugestão da IA:**
> "Teste as funções de roteamento isoladamente com estados mockados. Isso garante que a bifurcação está correta."

**Decisão Adotada:**
- ✅ Adicionado `test_comportamento_roteamento`
- ✅ 100% de cobertura das condicionais

---

### Evidência 2: Refinamento de Prompt

**Problema Observado:**
- `gerar_resposta` retornava `requires_human: null`

**Prompt Antes:**
```
Analise o chamado e determine se requer ação humana urgente.
Retorne um JSON com: category, severity, summary, suggested_action, requires_human.
```

**Prompt Depois:**
```
Analise o chamado e determine se requer ação humana urgente.

Retorne um JSON com os campos EXATOS:
- requires_human: boolean (true ou false, NUNCA null)

IMPORTANTE: Sempre retorne true ou false, nunca null ou string.
```

**Resultado:**
- ✅ Estrutura sempre válida
- ✅ `requires_human` sempre boolean
- ✅ Zero erros de validação

---

## 11. Extensões Técnicas

### Extensão 1: Human-in-the-Loop ⭐

**Implementação:**
1. Node `aguardar_aprovacao_humana` com `interrupt_before`
2. Workflow pausa ao chegar lá
3. API resume com `graph.update_state()` após aprovação

**Exemplos:**
```bash
# Submeter (crítico)
POST /triagem → pending_human_approval

# Aprovar
POST /triagem/{id}/approve {"approve": true} → completed

# Rejeitar
POST /triagem/{id}/approve {"approve": false} → rejected
```

---

### Extensão 2: Memória Persistente com Checkpointer 💾

**Implementação:**
1. `InMemorySaver()` para persistence
2. `_graph_store` dict para manter grafo por thread_id
3. `graph.update_state()` e `graph.stream()` para retomada

**Fluxo:**
```
Execução 1 → Interrompe
    ↓
[Espera]
    ↓
Execução 2 (mesmo thread_id) → Retoma do ponto exato
```

---

## 12. Segurança

### Validação de Entrada
```python
title: str = Field(min_length=3)          # ✅ Rejeita < 3 chars
description: str = Field(min_length=10)  # ✅ Rejeita < 10 chars
```

### Proteção contra Prompt Injection
```python
suspicious = [
    r"ignore\s*all\s*previous\s*instructions",
    r"system\s*prompt",
    r"esqueça\s*tudo",
]
# ✅ Detecta e bloqueia antes do LLM
```

### Proteção de Credenciais
- ✅ `.env.example` fornecido
- ✅ `.gitignore` protege `.env`
- ✅ Logs não exibem chaves

### Tratamento de Falhas
```python
try:
    for _ in graph.stream(...):
        pass
except Exception as e:
    return {"status": "error", "message": str(e)}
```

---

## 13. Webhook - Notificações em Tempo Real

O sistema pode enviar notificações via webhook quando um chamado crítico aguarda aprovação. Isso permite integração com Slack, Discord, teams ou qualquer sistema externo.

### Setup Rápido

1. **Teste com webhook.site:**
   ```bash
   # Gere uma URL em https://webhook.site
   export WEBHOOK_URL=https://webhook.site/seu-uuid
   
   # Inicie a API
   uvicorn src.api:app --reload
   ```

2. **Envie um chamado crítico:**
   ```bash
   curl -X POST http://localhost:8000/triagem \
     -H "Content-Type: application/json" \
     -d '{
       "title": "Banco de dados não responde",
       "description": "BD crítico está offline, produção parada"
     }'
   ```

3. **Veja a notificação em webhook.site** ✅

### Payload Enviado

```json
{
  "type": "ticket_approval_required",
  "timestamp": "2026-09-18T10:30:45.123456Z",
  "ticket": {
    "thread_id": "550e8400-e29b-41d4-a716-446655440000",
    "title": "Banco de dados não responde",
    "description": "...",
    "severity": "crítica",
    "summary": "Banco de dados crítico está offline",
    "suggested_action": "..."
  },
  "approval": {
    "approve_url": "http://localhost:8000/triagem/550e8400.../approve?approve=true",
    "reject_url": "http://localhost:8000/triagem/550e8400.../approve?approve=false",
    "approval_endpoint": "http://localhost:8000/triagem/550e8400.../approve"
  }
}
```

### Integrações Suportadas

- ✅ **Slack** - Mensagens com botões
- ✅ **Discord** - Embeds e notificações
- ✅ **Teams** - Adaptive cards
- ✅ **Zapier/Make** - Qualquer ação
- ✅ **Custom** - Qualquer URL HTTPS

### Documentação Completa

Veja `docs/WEBHOOK.md` para:
- Configuração em produção
- Exemplos de integração (Slack, Discord, Zapier)
- Retry e error handling
- Segurança e validação

---

## 14. Limitações

1. **Checkpointer em Memória**
   - Dados perdidos ao reiniciar
   - **Solução:** PostgreSQL checkpointer

2. **Base de Conhecimento Estática**
   - Arquivo JSON fixo
   - **Solução:** Vector database

3. **Sem Autenticação**
   - Qualquer pessoa pode submeter
   - **Solução:** JWT/OAuth

4. **Sem Rate Limiting**
   - Chamadas LLM não limitadas
   - **Solução:** Redis middleware

5. **Sem Auditoria de Aprovações**
   - Quem aprovou não é registrado
   - **Solução:** Adicionar `approved_by` no state

---

## 15. Instruções Completas para Avaliador

```bash
# 1. Clonar
git clone https://github.com/seu-usuario/recuperacao_agente.git
cd recuperacao_agente

# 2. Configurar
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Adicionar OPENAI_API_KEY no .env

# 3. Rodar testes
pytest tests/ -v

# 4. Iniciar API
uvicorn src.api:app --reload

# 5. Testar em outro terminal
# Teste 1: Chamado simples
curl -X POST http://localhost:8000/triagem \
  -H "Content-Type: application/json" \
  -d '{"title": "Problema de login", "description": "Um usuário não consegue fazer login no sistema"}'

# Teste 2: Chamado crítico
curl -X POST http://localhost:8000/triagem \
  -H "Content-Type: application/json" \
  -d '{"title": "Banco de dados não responde", "description": "BD crítico está down, produção parada"}'

# Teste 3: Aprovar (usar thread_id do teste 2)
curl -X POST http://localhost:8000/triagem/{thread_id}/approve \
  -H "Content-Type: application/json" \
  -d '{"approve": true}'
```

---

**Repositório:** [GitHub]  
**Vídeo:** [YouTube - Não Listado]  
**Última atualização:** 2026-09-18
