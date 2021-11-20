from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static


app_name = 'main'
urlpatterns = [
	path('',views.IndexView.as_view(),name='index'),
	path('events',views.IndexView.as_view(),name='eventview'),
	path('events/<int:pk>',views.EventDetailView.as_view(),name='eventdetail'),
	path('contests/<int:pk>/signupform',views.ContestSignupView.as_view(),name='contestsignupform'),
	path('contests/<int:contest_id>/signup',views.contestSignup,name='contestsignup'),
]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
