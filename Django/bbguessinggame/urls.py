from django.urls import path

from . import views

app_name = 'bbGuessGame'
urlpatterns = [
    path('', views.indexView, name='index'),
    path('data', views.dataView, name='data'),
    path('getByName', views.getByNameView, name='getByName'),
    path('getBotOfTheDay', views.getBotOfTheDayView, name='getBotOfTheDay'),
    #path("getDebugTimes",views.getDebugTimes,name="getDebugTimes"),
    path('match', views.matchView, name='match'),
]
