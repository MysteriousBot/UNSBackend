from django.urls import path
from . import views

urlpatterns = [
    path('auth/check-staff-email/', views.check_staff_email, name='check-staff-email'),
    path('api/jobs/my-jobs/<str:staff_uuid>/', views.my_jobs, name='my-jobs'),
    path('api/jobs/<str:job_id>/', views.job_detail, name='job-detail'),
    path('api/clients/', views.client_list, name='client-list'),
    path('api/clients/<str:uuid>/favorite/', views.toggle_client_favorite, name='toggle-client-favorite'),
    path('api/staff/<str:staff_uuid>/weekly-hours/', views.staff_weekly_hours, name='staff-weekly-hours'),
    path('api/staff/<str:staff_uuid>/weekly-hours/<str:week_start>/', views.staff_weekly_hours, name='staff-weekly-hours-date'),
] 