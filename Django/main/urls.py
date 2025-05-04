from django.urls import path

from . import views
from . import ajax_views
from . import error_views
from .sitemap_views import *
from django.contrib.sitemaps.views import sitemap
from main.models import *

app_name = 'main'

info_dict = {
    "queryset": Robot.objects.all(),
}

urlpatterns = [
    path('', views.index_view, name='index'),
    path('delete/<str:model>/<int:instance_id>/<int:next_id>', views.delete_view, name='delete'),
    path('delete/<str:model>/<int:instance_id>', views.delete_view, name='delete_noreturn'),
    path('robots', views.robot_index_view, name='robotIndex'),
    path('robot/<str:slug>', views.robot_detail_view, name='robotDetail'),
    path('robots/random', views.random_robot_view, name='randomRobot'),
    path('robots/<int:robot_id>/transfer', views.robot_transfer_view, name='transferRobot_form'),
    path('robots/<int:robot_id>/transfer/<int:team_id>', views.robot_transfer_view, name='transferRobot'),
    path('robots/<int:robot_id>/edit', views.robot_edit_view, name='editRobot'),
    path('robots/new', views.new_robot_view, name='newRobot'),
    path('leaderboard', views.leaderboard, name="leaderboard"),
    path('events', views.event_index_view, name='eventIndex'),
    path('event/<slug:slug>', views.event_detail_view, name='eventDetail'),
    path('events/new/<int:franchise_id>', views.new_event_view, name='newEvent'),
    path('events/<int:event_id>/edit', views.modify_event_view, name='editEvent'),
    path('contest/<int:contest_id>', views.contest_detail_view, name='contestDetail'),
    path('contests/new/<int:event_id>', views.new_contest_view, name='newContest'),
    path('contests/<int:contest_id>/edit', views.edit_contest_view, name='editContest'),
    path('teams', views.team_index_view, name='teamIndex'),
    path('teams/<int:team_id>/edit', views.team_modify_view, name='editTeam'),
    path('teams/new', views.team_modify_view, name='newTeam'),
    path('team/<slug:slug>', views.team_detail_view, name='teamDetail'),
    path('franchises', views.franchise_index_view, name='franchiseIndex'),
    path('franchises/<int:franchise_id>/edit', views.franchise_modify_view, name='editFranchise'),
    path('franchises/new', views.franchise_modify_view, name='newFranchise'),
    path('franchise/<slug:slug>', views.franchise_detail_view, name='franchiseDetail'),
    path('fights/new/<int:contest_id>', views.new_fight_view, name='newFight'),
    path('fight/<int:fight_id>', views.fight_detail_view, name='fightDetail'),
    path('fight/<int:fight_id>/edit', views.fight_editj_view, name='editJustFight'),
    path('fights/<int:fight_id>/addRobot', views.modify_fight_version_view, name='newFightVersion'),
    path('fights/<int:fight_id>/editRobot/<int:vf_id>', views.modify_fight_version_view, name='editFightVersion'),
    path('version/<int:version_id>', views.version_detail_view, name='versionDetail'),
    path('versions/<int:version_id>/edit', views.version_edit_view, name='editVersion'),
    path('versions/new/<int:robot_id>', views.new_version_view, name='newVersion'),
    path('event/<slug:event_slug>/awards', views.award_index_view, name='awardIndex'),
    path('awards/new/<int:event_id>', views.new_award_view, name='newAward'),
    path('weight_class/new/<int:return_id>', views.new_weight_class_view, name='newWeightClass'),
    path('awards/<int:award_id>/edit', views.award_edit_view, name='editAward'),
    path('account_public_details/<int:person_id>/edit', views.person_edit_view, name='editPerson'),
    # path('accounts/register', views.register, name='register'),
    # path('accounts/profile/', views.profile_view, name='profile'),
    path('<str:obj_type>/add_member/<int:obj_id>', views.add_member_view, name="addMember"),
    path('hall-of-fame', views.hall_of_fame_view, name="hallOfFame"),
    path('weapon-types', views.weapon_types_view, name="weaponTypes"),
    path('weight-classes', views.weight_class_view, name="weightClasses"),
    path('weight-classes', views.futures_features_view, name="futureFeatures"),
    path('weight-classes', views.ranking_system_view, name="weightClasses"),
    path('search', views.search_view, name="search"),
    path('message', views.message_view, name='message'),
    path('credits', views.credits_view, name='credits'),

    path('editor/home', views.edt_home_view, name='edtHome'),
    path('editor/newEvent', views.edt_new_event_view, name='edtNewEvent'),
    path('editor/event/<int:event_id>', views.edt_event_view, name='edtEvent'),
    path('editor/contest/<int:contest_id>', views.edt_contest_view, name='edtContest'),
    path('editor/selectFranchise', views.edt_fran_view, name='edtSelectFran'),
    path('editor/fight/<int:fight_id>', views.edt_fight_view, name='edtFightOverview'),
    path('editor/selectRobot', views.edt_select_robot_view, name='edtSelectRobot'),  # Modifyfightversion
    path('editor/fight/selectVersion/<int:robot_id>', views.edt_select_version_view, name='edtSelectVersion'),
    path('editor/fight/<int:fight_id>/signupVersion/<int:version_id>', views.edt_signup_version_view, name='edtSignupVersion'),
    path('editor/fight/<int:fight_id>/selectTeam', views.edt_select_team_view, name='edtSelectTeam'),
    path('editor/team/<int:team_id>', views.edt_team_view, name='edtTeam'),
    path('editor/link/<str:obj_type>/<int:obj_id>', views.edt_team_view, name='edtLink'),
    path('editor/pruneMedia', views.prune_media, name='edtPrune'),
    path('editor/calculate_test',views.calc_test, name='calcTest'),
    # path('test/tourny', views.tournament_tree, name='tournament_test'),
    # path('import', views.importView, name='import'),
    # path('test/graph', views.graph_test, name='graph_test'),
    # path('test/graph_data', views.graph_data, name='graph_test'),
    #path('test/merge', views.mergeView__SCARY, name='merge'),

    path('ajax/get_location', ajax_views.get_location, name='ajax_getLocation'),
    path('ajax/get_history', ajax_views.get_history, name='ajax_getHistory'),
    path('ajax/disclaimer', ajax_views.disclaimer, name='ajax_disclaimer'),
    path('ajax/yt_video_status/<int:fight_id>', ajax_views.yt_video_status, name="ajax_youtube"),

    path("404/", error_views._404),
    path("500/", error_views._500),

    path("sitemap.xml",
         sitemap,
         {"sitemaps": {
             "static": StaticSitemap,
             "index": IndexSitemap,
             "leaderboard": LeaderboardSitemap,
             "events": EventSitemap,
             "contests": ContestSitemap,
             "robots": RobotSitemap,
             "teams": TeamSitemap,
             "franchises": FranchiseSitemap,
         }},
         name="django.contrib.sitemaps.views.index", ),

    path("sitemap-<section>.xml",
         sitemap,
         {"sitemaps": {
             "static": StaticSitemap,
             "index": IndexSitemap,
             "leaderboard": LeaderboardSitemap,
             "events": EventSitemap,
             "contests": ContestSitemap,
             "robots": RobotSitemap,
             "teams": TeamSitemap,
             "franchises": FranchiseSitemap,
         }},
         name="django.contrib.sitemaps.views.sitemap", ),
]
