"""Adaptateur de notification par email (faux expéditeur existant)."""
from app.application.ports import NotificationFailed
from app.utils.email_sender import send_email


class EmailNotifier:
    def __init__(self, recipient: str = "production@festiplan.test"):
        self.recipient = recipient

    def notify_schedule_change(self, concert_id: int, message: str) -> None:
        try:
            send_email(self.recipient, f"Modification du concert #{concert_id}", message)
        except RuntimeError as exc:
            raise NotificationFailed(str(exc)) from exc
