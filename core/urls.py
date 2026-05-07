from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('admin_dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('update-user-status/', views.process_pending_registrations, name='update_user_status'),
    # Announcements
    path('announcements/', views.announcement_list, name='announcement_list'),
    path('announcements/create/', views.announcement_create, name='announcement_create'),
    path('announcements/<uuid:pk>/delete/', views.announcement_delete, name='announcement_delete'),
    path('announcements/<uuid:pk>/pin/', views.announcement_toggle_pin, name='announcement_toggle_pin'),
    # Notifications
    path('notifications/', views.notification_list, name='notification_list'),
    path('notifications/mark-all-read/', views.notifications_mark_all_read, name='notifications_mark_all_read'),
    path('notifications/<uuid:pk>/read/', views.notification_mark_read, name='notification_mark_read'),
]