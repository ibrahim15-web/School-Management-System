from django.urls import path
from core import views as core_views

from . import views
urlpatterns = [
    path('login/', views.login, name='login'),
    path('register/', views.register, name='register'),
    path('logout/', views.logout, name='logout'),
    path('forgot_password/', views.forgot_password, name='forgot_password'),
    path('verify_code/', views.verify_code, name='verify_code'),
    path('reset_password/', views.reset_password, name='reset_password'),
    path('profile/', views.profile, name='profile'),
    path('profile/update/', views.profile_update, name='profile_update'),
    path('update_password/', views.update_password, name='update_password'),
    path('waiting-approval/', views.waiting_approval, name='waiting_approval'),
    path("update-user-status/", core_views.update_user_status, name='update_user_status'),

    

]