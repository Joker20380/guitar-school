from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.shortcuts import render

from .forms import ContactMessageForm


def get_client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")

    if forwarded:
        return forwarded.split(",")[0].strip()

    return request.META.get("REMOTE_ADDR")


def send_contact_notification(contact_message):
    recipient = getattr(settings, "CONTACT_NOTIFY_EMAIL", "")

    if not recipient:
        return

    body = (
        "Новое сообщение с сайта школы гитары\n\n"
        f"Имя: {contact_message.name}\n"
        f"Email: {contact_message.email or '-'}\n"
        f"Телефон: {contact_message.phone or '-'}\n"
        f"Telegram: {contact_message.telegram or '-'}\n"
        f"Удобный способ связи: {contact_message.get_preferred_contact_display()}\n"
        f"Тема: {contact_message.subject or '-'}\n\n"
        f"Сообщение:\n{contact_message.message}\n"
    )

    send_mail(
        subject=f"Сообщение с сайта: {contact_message.subject or contact_message.name}",
        message=body,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "webmaster@localhost"),
        recipient_list=[recipient],
        fail_silently=True,
    )


def contact_page(request):
    if request.method == "POST":
        form = ContactMessageForm(request.POST)

        if form.is_valid():
            contact_message = form.save(commit=False)
            contact_message.ip_address = get_client_ip(request)
            contact_message.user_agent = request.META.get("HTTP_USER_AGENT", "")[:300]
            contact_message.save()

            send_contact_notification(contact_message)

            messages.success(
                request,
                "Сообщение отправлено. Мы свяжемся с вами удобным способом.",
            )

            form = ContactMessageForm()
        else:
            messages.error(request, "Проверьте поля формы. Некоторые данные заполнены некорректно.")
    else:
        form = ContactMessageForm()

    return render(request, "contacts/contact.html", {
        "form": form,
        "contact_phone": settings.CONTACT_PHONE,
        "contact_email": settings.CONTACT_EMAIL,
        "contact_telegram": settings.CONTACT_TELEGRAM,
        "contact_address": settings.CONTACT_ADDRESS,
        "contact_working_hours": settings.CONTACT_WORKING_HOURS,
    })
