from rest_framework.permissions import SAFE_METHODS, BasePermission

class IsStoreOwner(BasePermission):

    def has_permission(self, request, view):

        if request.method in ('GET'):
            return True
        
        if request.method == 'POST':
            return request.user.role == 'STORE_OWNER'

        return True
    
    def has_object_permission(self, request, view, obj):

        if request.method in SAFE_METHODS:
            return True

        return obj.owner == request.user
    