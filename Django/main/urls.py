from django.urls import path

from . import views

app_name = 'main'
urlpatterns = [
    path('', views.IndexView.as_view(), name='index'),
    path('robots', views.robot_index_view, name='robotIndex'),
    path('robots/<int:robot_id>', views.robot_detail_view, name='robotDetail'),
    path('robots/new/<int:team_id>', views.new_robot_view, name='newRobot'),
    path('events', views.EventIndexView.as_view(), name='eventIndex'),
    path('events/<int:event_id>', views.event_detail_view, name='eventDetail'),
    path('events/new/<int:franchise_id>', views.new_event_view, name='newEvent'),
    path('events/<int:event_id>/edit', views.modify_event_view, name='editEvent'),
    path('contests/<int:contest_id>', views.contest_detail_view, name='contestDetail'),
    path('contests/<int:contest_id>/signup', views.contest_signup_view, name='contestSignup'),
    path('contests/new/<int:event_id>', views.new_contest_view, name='newContest'),
    path('contests/<int:contest_id>/edit', views.edit_contest_view, name='editContest'),
    path('teams/<int:team_id>', views.team_detail_view, name='teamDetail'),
    path('teams/<int:team_id>/edit', views.team_edit_view, name='editTeam'),
    path('teams/new', views.team_edit_view, name='newTeam'),
    path('franchises/<int:franchise_id>/edit', views.franchise_modify_view, name='modifyFranchise'),
    path('franchises/new', views.franchise_modify_view, name='newFranchise'),
    path('franchises/<int:fran_id>', views.franchise_detail_view, name='franchiseDetail'),
    path('fights/new/<contest_id>', views.new_fight_view, name='newFight'),
    path('fights/<int:fight_id>/edit', views.fight_edith_view, name='editWholeFight'),
    path('fights/<int:fight_id>', views.fight_detail_view, name='fightDetail'),
    path('fights/<int:fight_id>/modify', views.fight_editj_view, name='editJustFight'),
    path('fights/<int:fight_id>/addRobot', views.modify_fight_version_view, name='newFightVersion'),
    path('fights/<int:fight_id>/editRobot/<int:vf_id>', views.modify_fight_version_view, name='editFightVersion'),
    path('versions/<int:version_id>', views.version_detail_view, name='versionDetail'),
    path('events/<int:event_id>/awards', views.award_index_view, name='awardIndex'),
    path('awards/<int:event_id>/new', views.new_award_view, name='newAward'),
    path('awards/<int:award_id>/edit', views.award_edit_view, name='editAward'),
    path('accounts/register', views.register, name='register'),
    path('accounts/profile', views.profile_view, name='profile'),
    path('message', views.message_view, name='message'),
]
