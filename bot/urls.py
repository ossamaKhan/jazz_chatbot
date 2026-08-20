from django.urls import path

from . import views

urlpatterns = [
    path("webhook/", views.webhook, name="whatsapp-webhook"),
    path("chat/", views.chat_page, name="chat-page"),
    path("ask/", views.ask, name="chat-ask"),
]
