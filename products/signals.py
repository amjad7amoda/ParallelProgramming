from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
import logging

from .models import Product

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Product)
@receiver(post_delete, sender=Product)
def invalidate_product_cache(sender, instance, **kwargs):
    cache_key = f"product:{instance.id}"
    try:
        cache.delete(cache_key)
        cache.delete(f"product:{instance.id}:price")
        cache.delete(f"product:{instance.id}:stock")
        delete_pattern = getattr(cache, 'delete_pattern', None)
        if delete_pattern:
            cache.delete_pattern(f"product_list:store:{instance.store_id}:url:*")
    except Exception as e:
        logger.error(f"Cache delete error: {e}")
