from celery import shared_task

from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives

@shared_task
def send_register_email(username, email):

    html_content = render_to_string(
        'welcome_email.html',
        {
            'username': username,
            'email': email
        }
    )

    email_message = EmailMultiAlternatives(
        subject='Welcome To Ecommerce',
        body='Welcome to Ecommerce',
        from_email='ecommerce@localhost',
        to=[email]
    )

    email_message.attach_alternative(
        html_content,
        "text/html"
    )

    email_message.send()