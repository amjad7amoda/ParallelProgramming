from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import LogoutSerializer, RegisterSerializer
from .tasks import send_register_email

class RegisterView(APIView):

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()

            # Asyncronous adding to the queue and send an email using redis & celery
            transaction.on_commit(
                lambda: (
                    send_register_email.delay(user.username, user.email)
                )
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LogoutView(APIView):

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {'message': 'Logged out successfully'},
            status=status.HTTP_205_RESET_CONTENT
        )