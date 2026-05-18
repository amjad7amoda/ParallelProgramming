from celery import shared_task
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.conf import settings

from order.models import Order


@shared_task
def generate_and_send_invoice(order_id, user_email):
    try:
        order = Order.objects.get(id=order_id)

        total_price = 0

        # حساب subtotal لكل عنصر
        for item in order.items.all():
            item.subtotal = item.quantity * item.price
            total_price += item.subtotal

        # تحديث total_price داخل order
        order.total_price = total_price

        context = {
            'order': order
        }

        # render html template
        html_content = render_to_string(
            'invoice.html',
            context
        )

        email = EmailMessage(
            subject=f"فاتورة الطلب #{order_id}",
            body="تم إرفاق تفاصيل طلبك.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user_email],
        )

        # إرسال HTML بدل PDF
        email.content_subtype = "html"
        email.body = html_content

        email.send()

        return f"Invoice sent to {user_email}"

    except Order.DoesNotExist:
        return f"Order {order_id} does not exist"

    except Exception as e:
        return f"Task failed with error: {str(e)}"