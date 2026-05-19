from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.student_dashboard, name='student_dashboard'),
    path('parent/', views.parent_dashboard, name='parent_dashboard'),
    path('report-card/pdf/', views.student_report_card_pdf, name='student_report_card_pdf'),
]