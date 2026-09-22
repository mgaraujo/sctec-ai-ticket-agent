"""
Webhook notification system for critical ticket approvals.

Sends notifications to a configured webhook URL when a critical ticket
(requires_human=True) enters the human approval stage.

Example webhook.site usage:
1. Visit https://webhook.site
2. Copy your unique URL: https://webhook.site/your-unique-id
3. Set WEBHOOK_URL=https://webhook.site/your-unique-id in .env
"""

import logging
import os

import requests

logger = logging.getLogger("TriagemAgente")


def get_webhook_url() -> str | None:
    """Retorna a URL do webhook configurada nas variáveis de ambiente."""
    webhook_url = os.getenv("WEBHOOK_URL", "").strip()
    return webhook_url if webhook_url else None


def send_approval_notification(
    thread_id: str,
    ticket_title: str,
    ticket_description: str,
    severity: str,
    summary: str,
    suggested_action: str,
    approval_url: str
) -> bool:
    """
    Envia notificação de aprovação pendente para o webhook configurado.

    Args:
        thread_id: ID único da thread/chamado
        ticket_title: Título do chamado
        ticket_description: Descrição do chamado
        severity: Severidade (baixa, média, crítica)
        summary: Resumo da análise LLM
        suggested_action: Ação sugerida
        approval_url: URL para aprovação/rejeição

    Returns:
        bool: True se enviado com sucesso, False caso contrário
    """
    webhook_url = get_webhook_url()

    if not webhook_url:
        logger.debug("[WEBHOOK] Webhook não configurado. Notificação não será enviada.")
        return False

    payload = {
        "type": "ticket_approval_required",
        "timestamp": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat(),
        "ticket": {
            "thread_id": thread_id,
            "title": ticket_title,
            "description": ticket_description,
            "severity": severity,
            "summary": summary,
            "suggested_action": suggested_action,
        },
        "approval": {
            "approve_url": f"{approval_url}?approve=true",
            "reject_url": f"{approval_url}?approve=false",
            "approval_endpoint": approval_url,
        },
    }

    try:
        logger.info(
            f"[WEBHOOK] Enviando notificação para {webhook_url} "
            f"- Thread: {thread_id}"
        )

        response = requests.post(
            webhook_url,
            json=payload,
            timeout=10,
            headers={"Content-Type": "application/json"},
        )

        if response.status_code in (200, 201, 202):
            logger.info(
                f"[WEBHOOK] ✓ Notificação enviada com sucesso "
                f"- Status: {response.status_code}"
            )
            return True
        else:
            logger.warning(
                f"[WEBHOOK] ✗ Falha ao enviar notificação "
                f"- Status: {response.status_code} - Response: {response.text}"
            )
            return False

    except requests.exceptions.Timeout:
        logger.warning(
            f"[WEBHOOK] ✗ Timeout ao tentar enviar notificação "
            f"- URL: {webhook_url}"
        )
        return False
    except requests.exceptions.ConnectionError as e:
        logger.warning(
            f"[WEBHOOK] ✗ Erro de conexão ao enviar notificação "
            f"- URL: {webhook_url} - Error: {e}"
        )
        return False
    except Exception:
        logger.exception(
            "[WEBHOOK] ✗ Erro inesperado ao enviar notificação"
        )
        return False


def send_approval_response_notification(
    thread_id: str,
    ticket_title: str,
    approved: bool,
    reason: str = ""
) -> bool:
    """
    Envia notificação de decisão de aprovação/rejeição (opcional).

    Args:
        thread_id: ID único da thread/chamado
        ticket_title: Título do chamado
        approved: True se aprovado, False se rejeitado
        reason: Motivo/comentário (opcional)

    Returns:
        bool: True se enviado com sucesso, False caso contrário
    """
    webhook_url = get_webhook_url()

    if not webhook_url:
        return False

    payload = {
        "type": "ticket_approval_decision",
        "timestamp": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat(),
        "ticket": {
            "thread_id": thread_id,
            "title": ticket_title,
        },
        "decision": {
            "approved": approved,
            "status": "approved" if approved else "rejected",
            "reason": reason,
        },
    }

    try:
        logger.info(
            f"[WEBHOOK] Enviando decisão para {webhook_url} "
            f"- Thread: {thread_id} - Decisão: {'Aprovado' if approved else 'Rejeitado'}"
        )

        response = requests.post(
            webhook_url,
            json=payload,
            timeout=10,
            headers={"Content-Type": "application/json"},
        )

        if response.status_code in (200, 201, 202):
            logger.info(
                f"[WEBHOOK] ✓ Decisão enviada com sucesso "
                f"- Status: {response.status_code}"
            )
            return True
        else:
            logger.warning(
                f"[WEBHOOK] ✗ Falha ao enviar decisão "
                f"- Status: {response.status_code}"
            )
            return False

    except Exception:
        logger.exception(
            "[WEBHOOK] ✗ Erro ao enviar decisão"
        )
        return False
