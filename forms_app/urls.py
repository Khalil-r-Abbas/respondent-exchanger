from django.urls import path

from . import views


app_name = 'forms_app'

urlpatterns = [
    path('kuesioner/', views.questionnaire_list, name='questionnaire_list'),
    path('kuesioner/baru/', views.questionnaire_builder, name='questionnaire_new'),
    path('kuesioner/<int:pk>/edit/', views.questionnaire_builder, name='questionnaire_edit'),
    path('kuesioner/<int:pk>/preview/', views.questionnaire_preview, name='questionnaire_preview'),
    path('kuesioner/<int:pk>/publish/', views.questionnaire_publish, name='questionnaire_publish'),
    path('kuesioner/<int:pk>/duplicate/', views.questionnaire_duplicate, name='questionnaire_duplicate'),
    path('kuesioner/<int:pk>/delete/', views.questionnaire_delete, name='questionnaire_delete'),
    path('f/<str:link_code>/', views.public_questionnaire, name='public_questionnaire'),
    path('q/<str:link_code>/', views.isi_kuesioner, name='isi_kuesioner'),
    path('q/<str:link_code>/selesai/', views.selesai_pengisian, name='selesai_pengisian'),
]
