# Roteiro de Apresentação - Agente de Triagem de Chamados

**Duração Total:** 10 minutos  
**Objetivo:** Demonstrar o funcionamento completo do agente, decisões condicionais, tool, contexto/RAG, cenários, testes e extensões

---

## PARTE 1: Contexto e Problema (1 min)

### Script para o Avaliador:

*"Olá! Vou apresentar um Agente Inteligente de Triagem de Chamados Técnicos desenvolvido com LangGraph.*

*O problema que ele resolve é: empresas recebem muitos chamados técnicos por dia - alguns simples (login, reset de senha) e alguns críticos (banco de dados down, produção parada). Hoje, tudo é manual. Meu agente analisa, classifica e decide se precisa de aprovação humana."*

### Mostrar:
- 📊 Fluxo visual (o diagrama do README)
- 🎯 Entrada: título + descrição do chamado
- 📤 Saída: resposta estruturada com severidade e ação sugerida

---

## PARTE 2: Execução do Fluxo Principal (2 min)

### Preparação:
```bash
# Terminal 1: Iniciar API
uvicorn src.api:app --reload

# Esperar até ver: "Uvicorn running on http://127.0.0.1:8000"
```

### Script:
*"Agora vou demonstrar o fluxo com um chamado SIMPLES. Vou submeter um chamado de login via API REST."*

### Executar (Terminal 2):
```bash
curl -X POST http://localhost:8000/triagem \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Usuário não consegue fazer login",
    "description": "Um usuário está recebendo erro 401 ao tentar fazer login. Ele confirma que a senha está correta."
  }'
```

### Resposta Esperada:
```json
{
  "status": "completed",
  "thread_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "response": {
    "category": "autenticação",
    "severity": "média",
    "summary": "Falha de autenticação do usuário - credenciais podem estar expiradas.",
    "suggested_action": "Verificar status da conta do usuário no AD, resetar senha e testar acesso.",
    "requires_human": false
  }
}
```

### Narração:
*"Note que:*
- ✅ **Status = completed**: Não requer aprovação
- ✅ **Severity = média**: LLM decidiu que é simples
- ✅ **requires_human = false**: Vai direto para finalizar
- ✅ **Contexto foi utilizado**: Consultar_base buscou na base de conhecimento"*

---

## PARTE 3: Decisão Condicional (1 min)

### Script:
*"Agora vou mostrar a lógica de decisão condicional. Observem o código."*

### Mostrar no Editor (src/graph.py):

```python
def route_after_llm_response(state: GraphState) -> Literal["aguardar_aprovacao_humana", "finalizar_chamado"]:
    """
    Após o LLM gerar resposta, verifica se requires_human=True.
    Se sim, espera aprovação. Se não, finaliza direto.
    """
    structured_response = state.get("structured_response")
    if structured_response and hasattr(structured_response, "requires_human"):
        if structured_response.requires_human:
            return "aguardar_aprovacao_humana"  # ← Vai para aprovação
    
    return "finalizar_chamado"  # ← Vai direto ao fim
```

### Narração:
*"A decisão é simples mas poderosa: o LLM retorna requires_human true ou false, e essa informação controla todo o fluxo. Não usamos palavras-chave - confiamos na inteligência do modelo."*

---

## PARTE 4: Tool Funcional (1 min)

### Script:
*"Agora vou mostrar a tool que recupera contexto - consultar_base."*

### Mostrar no Editor (src/graph.py):

```python
def node_consultar_base(state: GraphState, config: RunnableConfig) -> GraphState:
    """
    Busca contexto na base de conhecimento.
    Simula um RAG real que seria um vector database.
    """
    ticket_title = state.get("ticket_title", "")
    base_output = consultar_base(ticket_title, state.get("ticket_description", ""))
    
    return {
        "context": base_output,
        "status": "processing"
    }
```

### Mostrar resultado:
*"Observem nos logs da API:"*

```
[Trace: abc123...] [NODE] consultar_base | Processamento automático
[Trace: abc123...] [TOOL] Resultado da base: Artigo encontrado: "Erro 401 ocorre quando..."
```

### Narração:
*"A tool foi acionada, buscou contexto relevante na base, e esse contexto foi injetado no prompt do LLM. Isso melhorou a qualidade da resposta."*

---

## PARTE 5: Contexto e RAG em Ação (1 min)

### Script:
*"Observem como o contexto influencia a resposta. Vou comparar duas respostas do mesmo chamado."*

### Mostrar no Editor (docs/EXEMPLO_CONTEXTO.md):

**Sem Contexto:**
```json
{
  "suggested_action": "Verificar credenciais do usuário."
}
```

**Com Contexto (o que fazemos):**
```json
{
  "suggested_action": "Verificar status da conta do usuário no AD, resetar senha e testar acesso."
}
```

### Narração:
*"O contexto torna a recomendação específica e acionável. Isso é o poder do RAG integrado ao agente."*

---

## PARTE 6: Cenário de Falha - Chamado Crítico (2 min)

### Script:
*"Agora vou submeter um chamado CRÍTICO e demonstrar o human-in-the-loop em ação."*

### Executar (Terminal 2):
```bash
curl -X POST http://localhost:8000/triagem \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Banco de dados não responde",
    "description": "O servidor de banco de dados crítico está completamente offline. A produção está parada. Todos os usuários estão recebendo erro de timeout."
  }'
```

### Resposta Esperada (Parte 1):
```json
{
  "status": "pending_human_approval",
  "thread_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Chamado requer aprovação humana antes de qualquer ação operacional. Faça POST em /triagem/550e8400-e29b-41d4-a716-446655440000/approve para continuar."
}
```

### Narração:
*"Observe que:*
- ✅ **Status = pending_human_approval**: Workflow foi PAUSADO aqui!
- ✅ **Workflow usar interrupt_before**: O grafo literalmente parou antes de executar ações críticas
- ✅ **Retornado thread_id**: Necessário para retomar depois
- ✅ **Esperando aprovação humana via API**: Não é automático!"*

### Agora Aprovar (Parte 2):
```bash
curl -X POST http://localhost:8000/triagem/550e8400-e29b-41d4-a716-446655440000/approve \
  -H "Content-Type: application/json" \
  -d '{"approve": true}'
```

### Resposta Esperada (Parte 2):
```json
{
  "status": "completed",
  "thread_id": "550e8400-e29b-41d4-a716-446655440000",
  "response": {
    "category": "infraestrutura",
    "severity": "crítica",
    "summary": "Banco de dados crítico está offline - falha completa de serviço.",
    "suggested_action": "1. Verificar status do servidor de BD, 2. Revisar logs de erro, 3. Reiniciar serviço BD, 4. Monitorar recuperação.",
    "requires_human": true
  }
}
```

### Narração:
*"Após aprovação:*
- ✅ **Workflow retomou**: graph.update_state() atualizou human_approved=true
- ✅ **Fluxo continuou**: De onde parou em aguardar_aprovacao_humana
- ✅ **Status = completed**: Agora sim finalizou
- ✅ **Contexto preservado**: Toda informação anterior mantida no state"*

### Demonstrar Rejeição (Opção):
```bash
# Submeter outro chamado crítico
curl -X POST http://localhost:8000/triagem \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Falha crítica de BD",
    "description": "BD indisponível"
  }'

# Resposta terá novo thread_id, usar ele:
curl -X POST http://localhost:8000/triagem/[novo-thread-id]/approve \
  -H "Content-Type: application/json" \
  -d '{"approve": false}'
```

### Resposta Esperada (Rejeição):
```json
{
  "status": "rejected",
  "thread_id": "[novo-thread-id]",
  "message": "Chamado crítico foi rejeitado pelo usuário. Nenhuma ação foi executada."
}
```

---

## PARTE 7: Testes Automatizados (1 min)

### Script:
*"Vou rodar os testes para demonstrar qualidade de código."*

### Executar (Terminal 2):
```bash
pytest tests/ -v
```

### Resposta Esperada:
```
tests/test_triagem.py::test_sucesso_chamado_simples PASSED         [  16%]
tests/test_triagem.py::test_falha_entrada_invalida PASSED          [  33%]
tests/test_triagem.py::test_comportamento_roteamento PASSED        [  50%]
tests/test_triagem.py::test_chamado_critico_pendente PASSED        [  66%]
tests/test_triagem.py::test_aprovacao_chamado_critico PASSED       [  83%]
tests/test_triagem.py::test_rejeicao_chamado_critico PASSED        [100%]

====== 6 passed in 2.45s ======
```

### Narração:
*"6 testes, todos passando:*
- ✅ **Sucesso**: Fluxo principal funciona
- ✅ **Falha**: Entrada inválida é tratada
- ✅ **Roteamento**: Lógica condicional está correta
- ✅ **Crítico**: Human-in-the-loop funciona
- ✅ **Aprovação**: Transição pending → completed
- ✅ **Rejeição**: Transição pending → rejected

*Esses testes cobrem os requisitos principais."*

---

## PARTE 8: QA com IA e Evidência (1 min)

### Script:
*"Utilizei IA durante o desenvolvimento para revisar e refinar a solução. Deixe-me mostrar uma evidência."*

### Mostrar arquivo (docs/qa-ai-review.md ou similar):

```
PROBLEMA IDENTIFICADO:
- Testes cobriam apenas "caminho feliz"
- Faltava validação da lógica de roteamento

SUGESTÃO DA IA:
"Os testes devem cobrir as funções route_after_llm_response 
e route_human_decision isoladamente, injetando estados mockados."

DECISÃO DO ALUNO:
✅ Implementei test_comportamento_roteamento()
✅ Resultado: 100% de cobertura das decisões condicionais
```

### Mostrar Refinamento de Prompt:

```
PROBLEMA OBSERVADO:
- gerar_resposta às vezes retornava requires_human: null
- Estrutura Pydantic esperava bool

PROMPT ANTES:
"Retorne um JSON com: requires_human"

PROMPT DEPOIS:
"IMPORTANTE: requires_human DEVE SER um booleano (true/false), NUNCA null"

RESULTADO:
✅ Zero erros de validação
✅ Bifurcação funciona sempre
```

### Narração:
*"Iteramos com IA, identificamos problemas reais e solucionamos."*

---

## PARTE 9: Extensões Técnicas (1 min)

### Script:
*"Implementei duas extensões técnicas além do núcleo obrigatório."*

### Extensão 1: Human-in-the-Loop

**Mostrar:**
```python
# src/graph.py
workflow.compile(
    checkpointer=checkpointer,
    interrupt_before=["aguardar_aprovacao_humana"]  # ← Extensão 1
)
```

### Narração:
*"**Extensão 1: Human-in-the-Loop**  
Quando requires_human=true, o workflow pausa automaticamente. A decisão humana é solicitada via API. Não há execução automática de ações críticas. Isso atende o requisito: 'Human-in-the-loop para aprovação de uma ação'."*

### Extensão 2: Checkpointer

**Mostrar:**
```python
# src/api.py
_graph_store = {}  # ← Extensão 2 - Persistência

# Quando criar
_graph_store[thread_id] = {
    "graph": graph,
    "config": config,
    "title": request.title,
}

# Quando retomar
graph = _graph_store[thread_id]["graph"]
graph.update_state(config, {"human_approved": True})
```

### Narração:
*"**Extensão 2: Memória Persistente com Checkpointer**  
Estado é mantido entre requisições. Ao submeter um chamado crítico, o workflow pausa e é persistido. Quando a aprovação chega via API, o workflow retoma do ponto exato. Em produção, seria PostgreSQL checkpointer."*

---

## PARTE 10: Limitações e Considerações (0.5 min)

### Script:
*"Como toda solução MVP, há limitações que seriam resolvidas em produção:"*

### Listar:
```
1. ❌ Checkpointer em memória → ✅ PostgreSQL em produção
2. ❌ Sem autenticação → ✅ JWT/OAuth
3. ❌ Sem rate limiting → ✅ Redis middleware
4. ❌ Base de conhecimento estática → ✅ Vector database
```

### Narração:
*"Essas são escolhas de MVP. A arquitetura permite migrar sem mudanças no código principal."*

---

## PARTE 11: Resumo e GitHub (0.5 min)

### Script:
*"Para resumir:*

- ✅ **Agente LangGraph funcional**: State, nodes, edges, bifurcação condicional
- ✅ **Tool integrada**: Recuperação de contexto via base de conhecimento
- ✅ **RAG funcional**: Contexto influencia respostas
- ✅ **Human-in-the-loop**: Aprovação obrigatória para críticos
- ✅ **Testes automatizados**: 6 testes cobrindo sucesso, falha, roteamento
- ✅ **Observabilidade**: Logs com trace_id correlacionando execuções
- ✅ **Duas extensões técnicas**: Human-in-the-loop + Checkpointer

*Tudo está no GitHub:"*

### Mostrar:
- 📁 Estrutura: `src/` (aplicação), `tests/` (testes), `docs/` (evidências)
- 📝 README.md: Documentação completa
- 📊 Commits incrementais: Histórico claro

---

## PARTE 12: Demonstração ao Vivo (Opcional)

Se o tempo permitir, mostrar Swagger UI:

```
1. Abrir http://localhost:8000/docs
2. Fazer um POST /triagem
3. Executar e mostrar resposta
4. Fechar
```

---

## Checklist Final para Apresentação

### Antes de Começar:
- ✅ API rodando (`uvicorn src.api:app --reload`)
- ✅ Testes passam (`pytest tests/ -v`)
- ✅ `.env` configurado com OPENAI_API_KEY
- ✅ Terminal pronto para executar curl
- ✅ Editor com código-fonte aberto
- ✅ Documentação (README, docs/) acessível

### Durante a Apresentação:
- ✅ Falar claro e pausado
- ✅ Mostrar código relevante (não todo o arquivo)
- ✅ Demonstrar fluxo completo: simples + crítico
- ✅ Mencionar requisitos do enunciado
- ✅ Apontar extensões técnicas
- ✅ Conectar cada parte ao diagrama de arquitetura

### Respostas Prontas para Perguntas Comuns:

**P: Por que não usar agentes genéricos como `create_agent`?**  
R: Porque perderíamos controle do fluxo. LangGraph explícito oferece nodes, edges e bifurcações documentadas, o que é obrigatório no enunciado.

**P: Como a tool melhora a resposta?**  
R: A tool `consultar_base` busca contexto de execuções anteriores e passa para o LLM. Isso torna respostas específicas e acionáveis em vez de genéricas.

**P: O que acontece se o usuário rejeita um chamado crítico?**  
R: A requisição vai para `finalizar_sem_acao` e retorna status="rejected". Nenhuma ação é executada. É seguro.

**P: Como isso escala em produção?**  
R: Trocar `InMemorySaver()` por PostgreSQL checkpointer. Adicionar autenticação. Implementar rate limiting. Código não muda.

---

**Duração Total:** ~10 minutos  
**Foco:** Demonstrar funcionamento, decisões, ferramenta, contexto, aprovação e qualidade
