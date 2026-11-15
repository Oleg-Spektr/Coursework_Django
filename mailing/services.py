from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from .models import Mailing, MailingAttempt


def send_mailing(mailing: Mailing) -> tuple[bool, str]:
    """
    Проверяет окно времени отправки, отправляет письма каждому получателю
    и сохраняет попытки рассылки пакетно (batch) через bulk_create.
    """
    mailing.update_status()
    now = timezone.now()

    if not (mailing.start_time <= now <= mailing.end_time):
        return False, 'Ошибка: текущее время не входит в интервал отправки рассылки.'

    recipients = mailing.recipients.all()
    if not recipients.exists():
        return False, 'Ошибка: у рассылки нет ни одного получателя.'

    attempts_to_create = []

    for recipient in recipients:
        try:
            send_mail(
                subject=mailing.message.subject,
                message=mailing.message.body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient.email],
                fail_silently=False,
            )
            attempts_to_create.append(
                MailingAttempt(
                    status=MailingAttempt.STATUS_SUCCESS,
                    server_response=f'Письмо успешно отправлено на {recipient.email}',
                    mailing=mailing,
                )
            )
        except Exception as exc:
            attempts_to_create.append(
                MailingAttempt(
                    status=MailingAttempt.STATUS_FAILED,
                    server_response=str(exc),
                    mailing=mailing,
                )
            )

    # Пакетное сохранение всех попыток в БД (batch)
    if attempts_to_create:
        MailingAttempt.objects.bulk_create(attempts_to_create)

    return True, f'Рассылка выполнена. Обработано получателей: {len(attempts_to_create)}.'
