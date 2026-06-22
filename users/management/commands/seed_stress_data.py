"""
ضع هذا الملف في: <any_app>/management/commands/seed_stress_data.py
مثال: users/management/commands/seed_stress_data.py

لازم يكون عندك:
    users/management/__init__.py
    users/management/commands/__init__.py
(ملفات فاضية، عشان django يتعرف عليها كـ command)

طريقة التشغيل:
    python manage.py seed_stress_data
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from users.models import User
from store.models import Store
from products.models import Product

NUM_CUSTOMERS = 200
NUM_PRODUCTS = 20
DEFAULT_PASSWORD = "Test1234!"


class Command(BaseCommand):
    help = "Seed data for stress testing: 1 store owner, 1 store, N products, N customers"

    def add_arguments(self, parser):
        parser.add_argument(
            "--customers",
            type=int,
            default=NUM_CUSTOMERS,
            help="Number of customer users to create",
        )
        parser.add_argument(
            "--products",
            type=int,
            default=NUM_PRODUCTS,
            help="Number of products to create",
        )
        parser.add_argument(
            "--stock",
            type=int,
            default=1_000_000,
            help="Stock per product (keep huge so stress test doesn't run out)",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        num_customers = options["customers"]
        num_products = options["products"]
        stock = options["stock"]

        # 1) Store owner
        owner, created = User.objects.get_or_create(
            username="stress_owner",
            defaults={
                "email": "stress_owner@example.com",
                "role": User.Roles.STORE_OWNER,
            },
        )
        if created:
            owner.set_password(DEFAULT_PASSWORD)
            owner.save()
            self.stdout.write(self.style.SUCCESS(f"Created store owner: {owner.username}"))
        else:
            self.stdout.write(f"Store owner already exists: {owner.username}")

        # 2) Store
        store, created = Store.objects.get_or_create(
            name="Stress Test Store",
            owner=owner,
            defaults={"description": "Store used for load/stress testing"},
        )
        self.stdout.write(self.style.SUCCESS(f"Store ID: {store.id}"))

        # 3) Products
        product_ids = []
        for i in range(1, num_products + 1):
            product, _ = Product.objects.get_or_create(
                store=store,
                name=f"Stress Product {i}",
                defaults={
                    "description": f"Auto-generated product #{i} for stress testing",
                    "price": 9.99 + i,
                    "stock": stock,
                },
            )
            # تأكد دائماً إنه الستوك كبير، حتى لو الـ product كان موجود من قبل
            if product.stock < stock:
                product.stock = stock
                product.save(update_fields=["stock"])
            product_ids.append(product.id)

        self.stdout.write(self.style.SUCCESS(f"Created/verified {len(product_ids)} products"))

        # 4) Customers (loadtest_user_0 .. loadtest_user_N)
        created_count = 0
        for i in range(num_customers):
            username = f"loadtest_user_{i}"
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": f"{username}@example.com",
                    "role": User.Roles.CUSTOMER,
                },
            )
            if created:
                user.set_password(DEFAULT_PASSWORD)
                user.save()
                created_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Customers ready: {num_customers} "
                f"(newly created: {created_count}, password for all: {DEFAULT_PASSWORD})"
            )
        )

        self.stdout.write(self.style.SUCCESS("\n=== DONE ==="))
        self.stdout.write(f"STORE_ID = {store.id}")
        self.stdout.write(f"Password for all seeded users = {DEFAULT_PASSWORD}")
