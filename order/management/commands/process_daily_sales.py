"""Multithreaded daily sales batch job.

Run manually, once per day, for example:
    python manage.py process_daily_sales --date 2026-05-17 --chunk-size 100 --workers 4

The job does the following:
1) Extract paid OrderItem rows for one date.
2) Split them into chunks.
3) Process chunks with worker threads.
4) Merge partial results into one JSON report.

The report also contains a deadLetter section. Failed records are skipped,
logged, and do not block the rest of the batch.
"""

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
import json, os, threading, time

from django.core.management.base import BaseCommand
from django.db import close_old_connections
from django.utils import timezone

from order.models import Order
from order_items.models import OrderItem
from payments.models import Payment


def chunks(items, size):
    """Split a list into fixed-size chunks."""
    return [items[i:i + size] for i in range(0, len(items), size)]


def money(value):
    """Convert Decimal money safely for JSON."""
    return str(value.quantize(Decimal('0.01')))


def process_chunk(index, ids, simulate_bad_product_id=0):
    """Process one chunk inside one worker thread.

    Each thread gets its own DB connection handling. Each bad record is written
    to dead_letters and the worker continues with the remaining records.
    """
    close_old_connections()
    start = time.perf_counter()
    worker = threading.current_thread().name
    products = defaultdict(lambda: {'qty': 0, 'revenue': Decimal('0'), 'orders': set(), 'store': None, 'name': ''})
    stores = defaultdict(lambda: {'qty': 0, 'revenue': Decimal('0'), 'orders': set(), 'name': ''})
    dead_letters = []

    try:
        queryset = OrderItem.objects.select_related('order', 'product', 'product__store').filter(id__in=ids)
        for item in queryset:
            try:
                # For testing, lets the test command prove that deadLetter works.
                if simulate_bad_product_id and item.product_id == simulate_bad_product_id:
                    raise ValueError('Simulated item failure for deadLetter demo')

                value = Decimal(item.quantity) * item.price

                # Product-level partial result for this chunk.
                p = products[item.product_id]
                p['qty'] += item.quantity
                p['revenue'] += value
                p['orders'].add(item.order_id)
                p['store'] = item.product.store_id
                p['name'] = item.product.name

                # Store-level partial result for this chunk.
                s = stores[item.product.store_id]
                s['qty'] += item.quantity
                s['revenue'] += value
                s['orders'].add(item.order_id)
                s['name'] = item.product.store.name

            except Exception as exc:
                dead_letters.append({
                    'type': 'ORDER_ITEM',
                    'chunk': index,
                    'worker': worker,
                    'order_item_id': item.id,
                    'order_id': item.order_id,
                    'product_id': item.product_id,
                    'reason': str(exc),
                })
    except Exception as exc:
        # Chunk-level failure: logged so the report identifies failures.
        dead_letters.append({
            'type': 'CHUNK',
            'chunk': index,
            'worker': worker,
            'order_item_ids': ids,
            'reason': str(exc),
        })

    close_old_connections()
    return {
        'chunk': index,
        'worker': worker,
        'records': len(ids),
        'failed_records': len(dead_letters),
        'duration_ms': round((time.perf_counter() - start) * 1000, 2),
        'products': products,
        'stores': stores,
        'dead_letters': dead_letters,
    }


class Command(BaseCommand):
    help = 'Create a multithreaded daily sales batch report.'

    def add_arguments(self, parser):
        parser.add_argument('--date', default=str(timezone.localdate()), help='Sales date: YYYY-MM-DD. Default: today.')
        parser.add_argument('--chunk-size', type=int, default=100, help='Order items per chunk.')
        parser.add_argument('--workers', type=int, default=4, help='Number of worker threads.')
        parser.add_argument('--output', default='', help='Optional report path.')
        parser.add_argument('--simulate-dead-letter-product-id', type=int, default=0, help='Testing only: skip this product and log it in deadLetter.')

    def handle(self, *args, **options):
        day = options['date']
        size = max(1, options['chunk_size'])
        workers = max(1, options['workers'])
        simulate_bad_product_id = options['simulate_dead_letter_product_id']
        start = time.perf_counter()

        # Extract: only completed paid sales count as daily sales.
        ids = list(OrderItem.objects.filter(
            order__status=Order.Status.PAID,
            order__payment__status=Payment.Status.COMPLETED,
            order__payment__created_at__date=day,
        ).values_list('id', flat=True).order_by('id'))

        parts = chunks(ids, size)
        product_totals = defaultdict(lambda: {'qty': 0, 'revenue': Decimal('0'), 'orders': set(), 'store': None, 'name': ''})
        store_totals = defaultdict(lambda: {'qty': 0, 'revenue': Decimal('0'), 'orders': set(), 'name': ''})
        chunk_log, dead_letters = [], []

        # Transform: distribute chunks to a fixed-size thread pool.
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix='batch-worker') as pool:
            futures = [pool.submit(process_chunk, i + 1, chunk, simulate_bad_product_id) for i, chunk in enumerate(parts)]
            for future in as_completed(futures):
                result = future.result()
                chunk_log.append({k: result[k] for k in ('chunk', 'worker', 'records', 'failed_records', 'duration_ms')})
                dead_letters.extend(result['dead_letters'])

                # Merge each chunk's partial product/store totals.
                for product_id, partial in result['products'].items():
                    total = product_totals[product_id]
                    total['qty'] += partial['qty']
                    total['revenue'] += partial['revenue']
                    total['orders'] |= partial['orders']
                    total['store'] = partial['store']
                    total['name'] = partial['name']

                for store_id, partial in result['stores'].items():
                    total = store_totals[store_id]
                    total['qty'] += partial['qty']
                    total['revenue'] += partial['revenue']
                    total['orders'] |= partial['orders']
                    total['name'] = partial['name']

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        success_count = len(ids) - len([x for x in dead_letters if x['type'] == 'ORDER_ITEM'])

        # Load: write a single idempotent JSON report. Same date/output overwrites old report.
        report = {
            'date': day,
            'workers': workers,
            'chunk_size': size,
            'total_order_items_found': len(ids),
            'successful_order_items': success_count,
            'failed_order_items': len([x for x in dead_letters if x['type'] == 'ORDER_ITEM']),
            'total_chunks': len(parts),
            'duration_ms': duration_ms,
            'records_per_second': round(success_count / (duration_ms / 1000), 2) if duration_ms else 0,
            'chunks': sorted(chunk_log, key=lambda row: row['chunk']),
            'products': sorted([
                {'product_id': pid, 'product_name': x['name'], 'store_id': x['store'], 'quantity_sold': x['qty'], 'gross_revenue': money(x['revenue']), 'order_count': len(x['orders'])}
                for pid, x in product_totals.items()
            ], key=lambda row: row['product_id']),
            'stores': sorted([
                {'store_id': sid, 'store_name': x['name'], 'total_orders': len(x['orders']), 'total_items_sold': x['qty'], 'gross_revenue': money(x['revenue'])}
                for sid, x in store_totals.items()
            ], key=lambda row: row['store_id']),
            'deadLetter': {
                'count': len(dead_letters),
                'strategy': 'skip_failed_records_and_continue',
                'items': sorted(dead_letters, key=lambda row: (row.get('chunk', 0), row.get('order_item_id') or 0)),
            },
        }

        path = options['output'] or os.path.join('batch_reports', f'daily_sales_{day}.json')
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        with open(path, 'w', encoding='utf-8') as file:
            json.dump(report, file, indent=2)

        self.stdout.write(self.style.SUCCESS(
            f"Batch OK: {success_count}/{len(ids)} items, {len(parts)} chunks, {workers} threads, {duration_ms} ms"
        ))
        if dead_letters:
            self.stdout.write(self.style.WARNING(f"DeadLetter records: {len(dead_letters)}"))
        self.stdout.write(f'Report: {path}')
