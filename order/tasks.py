from celery import shared_task
from django.core.mail import send_mail

from order_items.models import OrderItem

@shared_task
def send_order_email(user_email, order_id):

    items = OrderItem.objects.filter(order_id=order_id).select_related('product')
    item_list = "\n".join([f"{item.product.name} (x{item.quantity})" for item in items])
    send_mail(
        subject='Order Created',
        message=f'Your order #{order_id} has been created\n\nItems:\n{item_list}',
        from_email='noreply@example.com',
        recipient_list=[user_email],
        fail_silently=False
    )
