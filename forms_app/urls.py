from django.urls import path

from forms_app import views


urlpatterns = [
    path('q/<str:link_code>/', views.isi_kuesioner, name='isi_kuesioner'),
    path('q/<str:link_code>/selesai/', views.selesai_pengisian, name='selesai_pengisian'),
]
