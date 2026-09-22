# 🎯 Demo - Webhook com webhook.site

## Objetivo
Demonstrar o envio de notificações de aprovação em tempo real para um webhook externo.

---

## Passo 1: Criar Webhook URL

1. Abra https://webhook.site
2. Você verá uma URL única gerada automaticamente:
   ```
   https://webhook.site/550e8400-e29b-41d4-a716-446655440000
   ```
3. **Deixe esta aba aberta** - você verá as requisições em tempo real!

---

## Passo 2: Configurar API com Webhook

### Terminal 1 - Iniciar API

```bash
# Clone o repositório (se ainda não fez)
git clone https://github.com/seu-usuario/recuperacao_agente.git
cd recuperacao_agente

# Crie o ambiente
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# ou
.venv\Scripts\activate  # Windows

# Instale dependências
pip install -r requirements.txt

# Configure a variável de ambiente com sua URL de webhook.site
export WEBHOOK_URL=https://webhook.site/seu-uuid-aqui

# Inicie a API
uvicorn src.api:app --reload
```

**Output esperado:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete
```

---

## Passo 3: Submeter Chamado Crítico

### Terminal 2 - Cliente

```bash
# Submeter um chamado que acionará aprovação
curl -X POST http://localhost:8000/triagem \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Banco de dados não responde",
    "description": "O servidor de banco de dados crítico está completamente offline. A produção está parada. Todos os usuários estão recebendo erro de timeout ao tentar acessar o sistema."
  }'
```

**Resposta esperada:**
```json
{
  "status": "pending_human_approval",
  "thread_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Chamado requer aprovação humana antes de qualquer ação operacional. Faça POST em /triagem/550e8400-e29b-41d4-a716-446655440000/approve para continuar. Webhook foi enviado se configurado."
}
```

---

## Passo 4: Ver Webhook Recebido

### Volte para webhook.site

**Você verá uma requisição POST com o seguinte payload:**

```json
{
  "type": "ticket_approval_required",
  "timestamp": "2026-09-18T10:30:45.123456Z",
  "ticket": {
    "thread_id": "550e8400-e29b-41d4-a716-446655440000",
    "title": "Banco de dados não responde",
    "description": "O servidor de banco de dados crítico está completamente offline...",
    "severity": "crítica",
    "summary": "Banco de dados crítico está offline - falha completa de serviço.",
    "suggested_action": "1. Verificar status do servidor de BD, 2. Revisar logs de erro, 3. Reiniciar serviço BD, 4. Monitorar recuperação."
  },
  "approval": {
    "approve_url": "http://localhost:8000/triagem/550e8400-e29b-41d4-a716-446655440000/approve?approve=true",
    "reject_url": "http://localhost:8000/triagem/550e8400-e29b-41d4-a716-446655440000/approve?approve=false",
    "approval_endpoint": "http://localhost:8000/triagem/550e8400-e29b-41d4-a716-446655440000/approve"
  }
}
```

✅ **Webhook recebido com sucesso!**

---

## Passo 5: Aprovar via API

### Terminal 2 - Cliente

Use o `thread_id` retornado anteriormente:

```bash
# Aprovar o chamado
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
    "summary": "Banco de dados crítico está offline - falha completa de serviço.",
    "suggested_action": "1. Verificar status do servidor de BD...",
    "requires_human": true
  }
}
```

### Volte para webhook.site

**Você verá uma SEGUNDA requisição:**

```json
{
  "type": "ticket_approval_decision",
  "timestamp": "2026-09-18T10:31:20.654321Z",
  "ticket": {
    "thread_id": "550e8400-e29b-41d4-a716-446655440000",
    "title": "Banco de dados não responde"
  },
  "decision": {
    "approved": true,
    "status": "approved",
    "reason": "Decisão enviada via /approve endpoint"
  }
}
```

✅ **Decisão notificada com sucesso!**

---

## Passo 6: Testar Rejeição

### Terminal 2 - Cliente

Submeter outro chamado crítico:

```bash
curl -X POST http://localhost:8000/triagem \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Falha crítica de infraestrutura",
    "description": "Servidor de produção está completamente fora do ar"
  }'

# Salve o novo thread_id da resposta...
```

**Rejeitar o chamado:**

```bash
curl -X POST http://localhost:8000/triagem/NOVO-THREAD-ID/approve \
  -H "Content-Type: application/json" \
  -d '{"approve": false}'
```

### Volte para webhook.site

**Você verá:**

```json
{
  "type": "ticket_approval_decision",
  "timestamp": "2026-09-18T10:32:15.789012Z",
  "ticket": {
    "thread_id": "NOVO-THREAD-ID",
    "title": "Falha crítica de infraestrutura"
  },
  "decision": {
    "approved": false,
    "status": "rejected",
    "reason": "Decisão enviada via /approve endpoint"
  }
}
```

✅ **Rejeição notificada com sucesso!**

---

## Passo 7: Visualizar Logs

### Terminal 1 - API

Observe os logs da API mostrando webhook enviados:

```
[Trace: ...] [WEBHOOK] Enviando notificação para https://webhook.site/...
[Trace: ...] [WEBHOOK] ✓ Notificação enviada com sucesso - Status: 200
[Trace: ...] [WEBHOOK] Enviando decisão para https://webhook.site/...
[Trace: ...] [WEBHOOK] ✓ Decisão enviada com sucesso - Status: 200
```

---

## Teste Completo com Slack

Se quiser integrar com Slack:

### 1. Criar Slack App

- Vá para https://api.slack.com/apps
- Crie um novo app
- Copie o Webhook URL do Incoming Webhooks

### 2. Configurar API

```bash
export WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
uvicorn src.api:app --reload
```

### 3. Submeter Chamado

```bash
curl -X POST http://localhost:8000/triagem \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Banco de dados não responde",
    "description": "BD crítico está offline, produção parada"
  }'
```

### 4. Ver Mensagem no Slack

Sua sala do Slack receberá uma notificação automática com:
- 🚨 Título do chamado
- Severidade
- ID do thread
- Links para aprovar/rejeitar

---

## Troubleshooting

### Webhook não está sendo enviado

1. ✅ Verificar variável de ambiente:
   ```bash
   echo $WEBHOOK_URL
   ```

2. ✅ Verificar nos logs da API:
   ```bash
   # Procure por [WEBHOOK]
   grep WEBHOOK debug.log
   ```

3. ✅ Verificar se o chamado é realmente crítico:
   - Status deve retornar `pending_human_approval`
   - Se retornar `completed` direto, não é crítico

### Webhook está recebendo mas corpo vazio

1. ✅ Usar a URL correta de webhook.site
2. ✅ Certificar que WEBHOOK_URL não tem espaços extras

### Webhook recebe erro 404

1. ✅ Conferir se webhook.site URL está correta
2. ✅ Não misturar URL de webhook.site com Slack (formatos diferentes)

---

## Checklist de Demonstração

- ✅ Webhook.site aberto em aba separada
- ✅ API iniciada com `WEBHOOK_URL` configurado
- ✅ Primeiro chamado crítico enviado e webhook recebido
- ✅ Logs da API mostram `[WEBHOOK] ✓ Notificação enviada`
- ✅ Webhook.site mostra payload completo com `ticket_approval_required`
- ✅ Approval via API enviado
- ✅ Webhook.site recebe segundo payload com `ticket_approval_decision`
- ✅ Logs mostram `[WEBHOOK] ✓ Decisão enviada`

---

## Documentação Completa

Para mais detalhes sobre webhook, veja `docs/WEBHOOK.md`

---

**Pronto! Você tem um sistema de notificações em tempo real funcionando! 🎉**
