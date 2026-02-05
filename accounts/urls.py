from django.urls import path
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
    # path('approve/<int:user_id>/', approve_user, name='approve_user'),
    

]