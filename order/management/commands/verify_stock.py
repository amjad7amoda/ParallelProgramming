# management/commands/verify_stock.py
from django.core.management.base import BaseCommand
from order_items.models import OrderItem
from products.models import Product
from django.db.models import Sum


class Command(BaseCommand):
    help = 'Verify stock integrity after load test'

    def add_arguments(self, parser):
        parser.add_argument('product_id', type=int)
        parser.add_argument('--initial-stock', type=int, default=10_000)

    def handle(self, *args, **options):
        product_id = options['product_id']
        initial_stock = options['initial_stock']

        product = Product.objects.get(id=product_id)
        sold = OrderItem.objects.filter(
            product_id=product_id,
            order__status__in=['PENDING', 'PROCESSING', 'SHIPPED']
        ).aggregate(total=Sum('quantity'))['total'] or 0

        # مجموع ما تم إرجاعه من الأوردرات الملغية
        cancelled = OrderItem.objects.filter(
            product_id=product_id,
            order__status='CANCELLED'
        ).aggregate(total=Sum('quantity'))['total'] or 0

        expected_stock = initial_stock - sold
        actual_stock = product.stock

        self.stdout.write(f"\n{'='*50}")
        self.stdout.write(f"Product: {product.name} (ID: {product_id})")
        self.stdout.write(f"Initial Stock:  {initial_stock}")
        self.stdout.write(f"Total Sold:     {sold}")
        self.stdout.write(f"Total Cancelled:{cancelled}")
        self.stdout.write(f"Expected Stock: {expected_stock}")
        self.stdout.write(f"Actual Stock:   {actual_stock}")
        self.stdout.write(f"{'='*50}")

        if expected_stock == actual_stock:
            self.stdout.write(self.style.SUCCESS("✅ Stock is CORRECT — no corruption"))
        else:
            diff = actual_stock - expected_stock
            self.stdout.write(self.style.ERROR(
                f"❌ Stock MISMATCH — difference: {diff:+d}\n"
                f"   {'Oversold (race condition!)' if diff < 0 else 'Stock not decremented properly'}"
            ))