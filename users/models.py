from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):

    class Roles(models.TextChoices):
        CUSTOMER= 'CUSTOMER', 'Customer'
        STORE_OWNER = 'STORE_OWNER', 'Store Owner'

    role = models.CharField(
        max_length=20,
        choices=Roles.choices
    )

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        if is_new and self.role == self.Roles.CUSTOMER:
            from cart.models import Cart
            Cart.objects.get_or_create(user=self)
