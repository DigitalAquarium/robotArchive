from django.urls import path

from . import views

app_name = 'bbGuessGame'
urlpatterns = [
    path('', views.indexView, name='index'),
    path('getByName', views.getByNameView, name='getByName'),
    path('getBotOfTheDay', views.getBotOfTheDayView, name='getBotOfTheDay'),
    path('match', views.matchView, name='match'),
]
