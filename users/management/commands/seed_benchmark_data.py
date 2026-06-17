import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from products.models import Product
from store.models import Store
from users.models import User


class Command(BaseCommand):
    help = 'Seed deterministic store and product data for load testing.'

    def handle(self, *args, **options):
        owner, _ = User.objects.get_or_create(
            username='benchmark_owner',
            defaults={
                'email': 'benchmark_owner@example.com',
                'role': User.Roles.STORE_OWNER,
            },
        )
        owner.role = User.Roles.STORE_OWNER
        owner.email = 'benchmark_owner@example.com'
        owner.set_password('Benchmark123!')
        owner.save()

        store, _ = Store.objects.get_or_create(
            name='Benchmark Store',
            defaults={
                'description': 'Deterministic catalog used for benchmark runs.',
                'owner': owner,
            },
        )
        if store.owner != owner:
            store.owner = owner
            store.save(update_fields=['owner'])

        product, _ = Product.objects.get_or_create(
            store=store,
            name='Benchmark Product',
            defaults={
                'description': 'Seeded product for concurrent checkout tests.',
                'price': '19.99',
                'stock': 10000,
            },
        )
        if product.stock < 10000:
            product.stock = 10000
        product.price = '19.99'
        product.description = 'Seeded product for concurrent checkout tests.'
        product.save()

        context = {
            'store_id': store.id,
            'product_id': product.id,
            'quantity': 1,
        }
        context_path = Path(settings.BASE_DIR) / 'benchmark_context.json'
        context_path.write_text(json.dumps(context, indent=2), encoding='utf-8')

        self.stdout.write(self.style.SUCCESS(f'Benchmark context written to {context_path}'))