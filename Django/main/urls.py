from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static


app_name = 'main'
urlpatterns = [
	path('',views.IndexView.as_view(),name='index'),
	path('events',views.IndexView.as_view(),name='eventview'),
	path('events/<int:pk>',views.EventDetailView.as_view(),name='eventdetail'),
	path('events/<int:pk>/signup',views.ContestSignupView.as_view(),name='contestsignup'),
]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
