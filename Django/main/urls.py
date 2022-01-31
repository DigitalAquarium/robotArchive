from django.urls import path

from . import views

app_name = 'main'
urlpatterns = [
    path('', views.IndexView.as_view(), name='index'),
    path('robots', views.RobotIndexView.as_view(), name='robotIndex'),
    path('robots/<int:pk>', views.RobotDetailView.as_view(), name='robotDetail'),
    path('robots/new/<int:team_id>', views.new_robot_view, name='newRobot'),
    path('events', views.EventIndexView.as_view(), name='eventView'),
    path('events/<int:event_id>', views.event_detail_view, name='eventDetail'),
    path('contests/<int:contest_id>/signup', views.contest_signup_view, name='contestSignup'),
    path('myteams', views.my_teams_view, name='myTeams'),
    path('teams/<int:team_id>', views.team_detail_view, name='teamDetail'),
    path('teams/edit/<int:team_id>', views.team_edit_view, name='editTeam'),
    path('teams/new', views.team_edit_view, name='newTeam'),
    path('franchises/edit/<int:franchise_id>', views.franchise_modify_view, name='modifyFranchise'),
    path('franchises/new', views.franchise_modify_view, name='newFranchise'),
    path('myfranchises', views.my_franchises_view, name='myFranchises'),
    path('franchises/<int:fran_id>', views.franchise_detail_view, name='franchiseDetail'),
    path('accounts/register', views.register, name='register'),
]
