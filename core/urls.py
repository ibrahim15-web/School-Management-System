from django.urls import path
from . import views
urlpatterns = [
    path('', views.home, name='home'),
    path('admin_dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('update-user-status/', views.process_pending_registrations, name='update_user_status'),
]