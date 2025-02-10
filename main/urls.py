from django.urls import path
from . import views

urlpatterns = [
    path('auth/check-staff-email/', views.check_staff_email, name='check-staff-email'),
    path('api/jobs/all/', views.all_jobs, name='all_jobs'),
    path('api/jobs/my-jobs/<str:staff_uuid>/', views.my_jobs, name='my-jobs'),
    path('api/jobs/<str:job_id>/', views.job_detail, name='job-detail'),
    path('api/jobs/<str:job_id>/tasks/', views.job_tasks, name='job-tasks'),
    path('api/clients/', views.client_list, name='client-list'),
    path('api/clients/<str:uuid>/favorite/', views.toggle_client_favorite, name='toggle-client-favorite'),
    path('api/staff/<str:staff_uuid>/weekly-hours/', views.submit_timesheet, name='submit-timesheet'),
    path('api/staff/<str:staff_uuid>/weekly-hours/<str:week_start>/', views.staff_weekly_hours, name='staff-weekly-hours-date'),
    path('api/contacts/', views.all_contacts, name='all-contacts'),
    path('api/clients/<str:client_id>/', views.client_detail, name='client-detail'),
    path('api/clients/<str:client_id>/jobs/', views.client_jobs, name='client-jobs'),
    path('api/clients/<str:client_id>/contacts/', views.client_contacts, name='client-contacts'),
] 