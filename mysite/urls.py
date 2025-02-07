from django.contrib import admin
from django.urls import path, include
from decouple import config
from main.views import check_staff_email


urlpatterns = [
    path('admin/', admin.site.urls),
    path('auth/', include('djoser.urls')),
    path('auth/', include('djoser.urls.jwt')),
    path('auth/check-staff-email/', check_staff_email, name='check-staff-email'),
    path('', include('main.urls')),
]

