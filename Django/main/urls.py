from django.urls import path

from . import views

app_name = 'main'
urlpatterns = [
    path('', views.IndexView.as_view(), name='index'),
    path('robots', views.RobotIndexView.as_view(), name='robotIndex'),
    path('robots/<int:pk>', views.RobotDetailView.as_view(), name='robotdetail'),
    path('robots/new/<int:team_id>', views.new_robot_view, name='newrobot'),
    path('events', views.IndexView.as_view(), name='eventview'),
    path('events/<int:pk>', views.EventDetailView.as_view(), name='eventdetail'),
    path('contests/<int:contest_id>/signup', views.contest_signup_view, name='contestsignup'),
    path('myteams', views.my_teams_view, name='myteams'),
    path('teams/<int:team_id>', views.team_detail_view, name='teamdetail'),
    path('accounts/register', views.register, name='register'),
]
