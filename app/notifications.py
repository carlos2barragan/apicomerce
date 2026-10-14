"""Notificaciones (tareas en segundo plano).

Simula el envío de correos. En producción esto NO se hace dentro del
request (el usuario esperaría el envío completo). Se encola y se procesa
aparte: Celery, RQ o el BackgroundTasks de FastAPI para trabajos ligeros.

Migración a Celery: reemplaza el cuerpo de estas funciones por
`enviar_email_confirmacion.delay(...)` con una tarea de Celery.
"""

import logging

logger = logging.getLogger("app.notifications")


def send_order_confirmation(email: str, order_id: int, total: str) -> None:
    """Envía (o simula) el correo de confirmación de una compra."""
    # ⚠️ En producción: SMTP, SendGrid, Amazon SES, etc.
    logger.info(
        "Correo de confirmación -> %s | orden #%s | total %s",
        email,
        order_id,
        total,
    )
