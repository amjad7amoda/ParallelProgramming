from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsPaymentAccess(BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return request.user.role in ('CUSTOMER', 'STORE_OWNER')
        return request.user.role == 'CUSTOMER'

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            if request.user.role == 'CUSTOMER':
                return obj.order.user == request.user
            if request.user.role == 'STORE_OWNER':
                return obj.order.items.filter(
                    product__store__owner=request.user
                ).exists()
        return obj.order.user == request.user
