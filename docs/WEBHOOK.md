# 🔔 Webhook - Notificações de Aprovação

## Visão Geral

O sistema envia notificações via webhook quando um chamado crítico aguarda aprovação humana. Isso permite que sistemas externos sejam notificados em tempo real sobre decisões pendentes.

**Casos de Uso:**
- ✅ Notificar slack/discord/teams de chamados críticos
- ✅ Criar tickets em sistemas de help desk
- ✅ Registrar eventos em plataformas de observabilidade
- ✅ Acionar escalação automática
- ✅ Integrar com ferramentas de workflow

---

## Configuração

### 1. Setup Rápido com webhook.site

Para testes e demonstração, use [webhook.site](https://webhook.site):

1. Abra https://webhook.site
2. Copie a URL única (exemplo: `https://webhook.site/abc123def456`)
3. Configure em `.env`:

```bash
WEBHOOK_URL=https://webhook.site/abc123def456
```

4. Restart da API

### 2. Setup em Produção

Configure no seu sistema:

```bash
# Docker
docker run -e WEBHOOK_URL=https://seu-dominio.com/webhooks/triagem ...

# Kubernetes
env:
  - name: WEBHOOK_URL
    valueFrom:
      secretKeyRef:
        name: triagem-secrets
        key: webhook-url

# Environment file
export WEBHOOK_URL=https://seu-dominio.com/webhooks/triagem
```

### 3. Desabilitar Webhook

Deixe `WEBHOOK_URL` vazio ou não definido:

```bash
WEBHOOK_URL=
# ou
unset WEBHOOK_URL
```

---

## Payload - Notificação de Aprovação

Quando um chamado crítico é criado e requer aprovação, o webhook recebe:

```json
{
  "type": "ticket_approval_required",
  "timestamp": "2026-09-18T10:30:45.123456Z",
  "ticket": {
    "thread_id": "550e8400-e29b-41d4-a716-446655440000",
    "title": "Banco de dados não responde",
    "description": "O servidor de BD crítico está offline. Produção parada.",
    "severity": "crítica",
    "summary": "Banco de dados crítico está offline - falha completa de serviço.",
    "suggested_action": "1. Verificar status do servidor BD, 2. Revisar logs, 3. Reiniciar serviço"
  },
  "approval": {
    "approve_url": "http://localhost:8000/triagem/550e8400-e29b-41d4-a716-446655440000/approve?approve=true",
    "reject_url": "http://localhost:8000/triagem/550e8400-e29b-41d4-a716-446655440000/approve?approve=false",
    "approval_endpoint": "http://localhost:8000/triagem/550e8400-e29b-41d4-a716-446655440000/approve"
  }
}
```

### Campos

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `type` | string | `"ticket_approval_required"` |
| `timestamp` | ISO 8601 | Data/hora no UTC |
| `ticket.thread_id` | UUID | ID único do chamado |
| `ticket.title` | string | Título do chamado |
| `ticket.description` | string | Descrição completa |
| `ticket.severity` | string | `crítica`, `alta`, `média`, `baixa` |
| `ticket.summary` | string | Análise do LLM |
| `ticket.suggested_action` | string | Ação recomendada |
| `approval.approve_url` | URL | Para aprovar via GET |
| `approval.reject_url` | URL | Para rejeitar via GET |
| `approval.approval_endpoint` | URL | Para POST com JSON body |

---

## Payload - Notificação de Decisão

Após aprovação/rejeição, o webhook recebe (opcional):

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

---

## Exemplos de Integração

### Slack Integration

```python
import json
from fastapi import Request

@app.post("/webhooks/from-triagem")
async def handle_triagem_webhook(request: Request):
    payload = await request.json()
    
    if payload["type"] == "ticket_approval_required":
        ticket = payload["ticket"]
        
        slack_message = {
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"🚨 *Aprovação Necessária*\n{ticket['title']}"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Severidade:*\n{ticket['severity']}"},
                        {"type": "mrkdwn", "text": f"*ID:*\n{ticket['thread_id'][:8]}..."}
                    ]
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "✅ Aprovar"},
                            "url": payload["approval"]["approve_url"],
                            "style": "primary"
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "❌ Rejeitar"},
                            "url": payload["approval"]["reject_url"],
                            "style": "danger"
                        }
                    ]
                }
            ]
        }
        
        # Send to Slack
        requests.post("https://hooks.slack.com/services/...", json=slack_message)
        
    return {"status": "received"}
```

### Discord Integration

```python
@app.post("/webhooks/from-triagem")
async def handle_triagem_webhook(request: Request):
    payload = await request.json()
    
    if payload["type"] == "ticket_approval_required":
        ticket = payload["ticket"]
        
        discord_message = {
            "embeds": [{
                "title": f"🚨 Aprovação Necessária",
                "description": ticket["title"],
                "color": 16711680,  # Red
                "fields": [
                    {"name": "Severidade", "value": ticket["severity"], "inline": True},
                    {"name": "Status", "value": "Aguardando Aprovação", "inline": True},
                    {"name": "Descrição", "value": ticket["description"], "inline": False},
                    {"name": "Ação Sugerida", "value": ticket["suggested_action"], "inline": False}
                ],
                "buttons": [
                    {"label": "✅ Aprovar", "url": payload["approval"]["approve_url"]},
                    {"label": "❌ Rejeitar", "url": payload["approval"]["reject_url"]}
                ]
            }]
        }
        
        # Send to Discord webhook
        requests.post("https://discordapp.com/api/webhooks/...", json=discord_message)
        
    return {"status": "received"}
```

### Zapier / Make.com

Configure um webhook trigger:

1. Em Zapier/Make, crie um novo zap/flow
2. Trigger: "Webhooks by Zapier" / "Webhooks"
3. Cole a URL de webhook.site como WEBHOOK_URL no Agente
4. Capture o payload
5. Configure ações (Slack, email, ticket, etc)

Exemplo de fluxo:
```
Triagem Webhook → Extract ticket data → Send Slack message → Update spreadsheet
```

---

## Retry e Timeout

### Configuração

- **Timeout:** 10 segundos
- **Retry:** Não há retry automático (HTTP é fire-and-forget)
- **Logging:** Todos os sucesso/falha são registrados em logs

### Recomendações

Para garantir entrega confiável:

1. **Idempotência**: Use `thread_id` como chave única
2. **Retry na API**: Implemente retry exponencial no seu webhook receiver
3. **Logging**: Registre todas as notificações recebidas
4. **Dead Letter Queue**: Armazene falhas para retry posterior

```python
# Exemplo de receiver robusto
@app.post("/webhooks/from-triagem")
async def handle_triagem_webhook(request: Request):
    payload = await request.json()
    thread_id = payload["ticket"]["thread_id"]
    
    # Verificar idempotência
    if await db.webhook_processed(thread_id):
        return {"status": "already_processed"}
    
    try:
        # Processar
        await process_approval_request(payload)
        await db.mark_webhook_processed(thread_id)
        return {"status": "success"}
    except Exception as e:
        # Dead letter queue
        await db.queue_for_retry(thread_id, payload, str(e))
        return {"status": "error", "retry": True}
```

---

## Teste com webhook.site

### Passo 1: Copiar URL

```
https://webhook.site/550e8400-e29b-41d4-a716-446655440000
```

### Passo 2: Configurar

```bash
# Terminal 1
export WEBHOOK_URL=https://webhook.site/550e8400-e29b-41d4-a716-446655440000
uvicorn src.api:app --reload
```

### Passo 3: Criar Chamado Crítico

```bash
# Terminal 2
curl -X POST http://localhost:8000/triagem \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Banco de dados não responde",
    "description": "O servidor de BD crítico está offline. A produção está parada. Todos os usuários estão recebendo erro de timeout."
  }'
```

### Passo 4: Ver Notificação

Volte para https://webhook.site e veja o payload recebido em tempo real! ✅

---

## Segurança

### Recomendações

1. **HTTPS Obrigatório**: Use sempre HTTPS em produção
2. **Validação de IP**: Restrinja a origem do webhook
3. **Timeout Curto**: Máximo 10 segundos
4. **Sem Informações Sensíveis**: Webhook não envia senhas ou tokens
5. **Logging**: Registre quem aprovou e quando

### Exemplo - Validação de IP

```python
ALLOWED_WEBHOOK_IPS = ["192.168.1.0/24", "10.0.0.0/8"]

@app.post("/triagem")
def iniciar_triagem(request: Request, chamado: ChamadoRequest):
    # Sua lógica...
    
    # Após criar chamado crítico que precisa de aprovação:
    if send_webhook and requires_human:
        # send_approval_notification() é chamado
        # Se falhar, a requisição prossegue normalmente
        # (webhook é "best effort")
        pass
```

---

## Troubleshooting

### Webhook não está sendo enviado

1. ✅ Verificar se `WEBHOOK_URL` está configurada
   ```bash
   echo $WEBHOOK_URL
   ```

2. ✅ Verificar se o chamado é realmente crítico
   - Deve ter `requires_human=true`
   - Severidade deve ser "crítica"

3. ✅ Verificar logs da API
   ```bash
   grep "WEBHOOK" debug.log
   ```

### Webhook está falhando

1. ✅ Verificar URL de webhook.site está correta
2. ✅ Verificar timeout (10 segundos limite)
3. ✅ Verificar se webhook endpoint retorna 200-202

### Notificações duplicadas

1. ✅ Usar `thread_id` como chave de idempotência
2. ✅ Implement deduplication no receiver

---

## Exemplo Completo - Sistema de Monitoramento

```python
# monitor.py
import asyncio
import httpx
from typing import Optional

class ApprovalMonitor:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
        self.pending_approvals: dict = {}
    
    async def on_approval_required(self, payload: dict):
        """Chamado quando webhook recebe notificação de aprovação"""
        ticket = payload["ticket"]
        thread_id = ticket["thread_id"]
        
        self.pending_approvals[thread_id] = {
            "created_at": payload["timestamp"],
            "title": ticket["title"],
            "severity": ticket["severity"]
        }
        
        print(f"⏳ Aguardando aprovação: {ticket['title']}")
        
        # Opcional: timeout automático após 1 hora
        await asyncio.sleep(3600)
        if thread_id in self.pending_approvals:
            print(f"⚠️ Timeout de aprovação: {thread_id}")
    
    async def on_approval_decision(self, payload: dict):
        """Chamado quando webhook recebe decisão"""
        thread_id = payload["ticket"]["thread_id"]
        decision = payload["decision"]["status"]
        
        if thread_id in self.pending_approvals:
            del self.pending_approvals[thread_id]
        
        if decision == "approved":
            print(f"✅ Aprovado: {payload['ticket']['title']}")
        else:
            print(f"❌ Rejeitado: {payload['ticket']['title']}")

# Uso
monitor = ApprovalMonitor("https://webhook.site/...")
```

---

**Versão:** 1.0  
**Última atualização:** 2026-09-18  
**Status:** ✅ Pronto para produção
