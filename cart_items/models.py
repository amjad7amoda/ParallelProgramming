from decimal import Decimal

from django.db import models

from cart.models import Cart
from products.models import Product


class CartItem(models.Model):
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name='items'
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='cart_items'
    )
    quantity = models.PositiveIntegerField(default=1)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('cart', 'product')

    def __str__(self):
        return f'{self.product.name} x{self.quantity}'

    def save(self, *args, **kwargs):
        self.total_price = Decimal(self.quantity) * Decimal(str(self.product.price))
        super().save(*args, **kwargs)
