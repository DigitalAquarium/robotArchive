import datetime
import sqlite3
import urllib
import time
from io import BytesIO
from PIL import Image
from django.core.files import File

from django.contrib.auth.decorators import login_required
from django.core.validators import URLValidator
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.db import transaction

from main import subdivisions
from .forms import *

# to do for the old uni system Email stuff (low prio),Fight edit cleanup, auto person merging, Home page, leaderboard still needs smol css
ONE_HOUR_TIMER = 3600


@login_required(login_url='/accounts/login/')
def edt_home_view(request):
    name = request.GET.get("name") or ""

    event_list = Event.objects.all()

    if name != "" and name is not None:
        event_list = event_list.filter(name__icontains=name).union(
            event_list.filter(contest__name__icontains=name)).union(
            event_list.filter(franchise__name__icontains=name))

    event_list = event_list.order_by("name").order_by("-start_date")

    return render(request, "main/editor/home.html",
                  {"event_list": event_list,
                   "name": name,
                   })


@login_required(login_url='/accounts/login/')
def edt_new_event_view(request):
    # TODO: Add verification
    fran_id = request.GET.get("franchise") or ""
    if fran_id:
        fran_id = int(fran_id)
        fran = Franchise.objects.get(pk=fran_id)
        if request.method == "POST":
            form = NewEventFormEDT(request.POST)
            if form.is_valid():
                event = form.save(fran)
                event.make_slug(save=True)
                return redirect("main:edtEvent", event.id)
        else:
            form = NewEventFormEDT()
    else:
        fran = None
        form = NewEventFormEDT()
    return render(request, "main/editor/new_event.html", {"form": form, "fran": fran})


def edt_event_view(request, event_id):
    event = Event.objects.get(pk=event_id)

    if request.method == "POST":
        sources = event.source_set.all()
        for i in range(len(sources)):
            updated_name = request.POST["src-name-" + str(i)]
            updated_url = request.POST["src-link-" + str(i)]
            current = sources[i]
            if updated_url != current.link or updated_name != current.name:
                validator = URLValidator()
                try:
                    validator(updated_url)
                    current.name = updated_name
                    current.link = updated_url
                    current.archived = "web.archive.org" in updated_url
                    current.last_accessed=timezone.now()
                    current.save()
                except ValidationError:
                    pass

        new_name = request.POST["new-src-name"]
        new_link = request.POST["new-src-link"]
        if new_name != "" and new_name is not None and new_link != "" and new_link is not None:
            validator = URLValidator()
            src = Source()
            try:
                validator(new_link)
                src.name= new_name
                src.link = new_link
                src.archived = "web.archive.org" in new_link
                src.last_accessed=timezone.now()
                src.event = event
                src.save()
            except ValidationError:
                pass
    return render(request, "main/editor/event.html",
                  {"event": event})


@login_required(login_url='/accounts/login/')
def edt_fran_view(request):
    name = request.GET.get("name") or ""

    fran_list = Franchise.objects.all()

    if name != "" and name is not None:
        fran_list = fran_list.filter(name__icontains=name)

    fran_list = fran_list.order_by("name")

    return render(request, "main/editor/franchise.html",
                  {"fran_list": fran_list,
                   "name": name,
                   })


def edt_contest_view(request, contest_id):
    contest = Contest.objects.get(pk=contest_id)
    fights = Fight.objects.filter(contest=contest).order_by("number")
    registrations = contest.registration_set.all()
    other_contests = Contest.objects.filter(event=contest.event).exclude(pk=contest_id)

    def move_to_contest(fight,target_contest):
        fight.contest = target_contest
        for fv in Fight_Version.objects.filter(fight=fight):
            v = fv.version
            if target_contest.registration_set.filter(version=v).count() == 0:
                reg = Registration()
                reg.contest = target_contest
                reg.version = v
                reg.approved = True
                reg.signee = v.owner
                reg.save()
        fight.save()


    if request.method == "POST":
        if request.POST["save"] == "move":
            fight_dict = {}
            for i in range(fights.count()):
                #Create a permanent fight record that does not change when fights are removed from the contest
                #prevents indexoutofbound
                fight_dict[i] = fights[i]
            for i in range(len(fight_dict)):
                if int(request.POST["fight-"+str(i)]) != contest_id:
                    if "recursive-" + str(i) in request.POST.keys():
                        versions_checked = []
                        versions_to_check = [fv.version for fv in Fight_Version.objects.filter(fight=fight_dict[i])]
                        fights_to_move = [fight_dict[i]]
                        while len(versions_to_check) > 0:
                            v = versions_to_check.pop()
                            fights_to_check = Fight.objects.filter(contest=contest,fight_version__version=v).exclude(fight_version__version__in=versions_checked).exclude(fight_version__version__in=versions_to_check)
                            for fight in fights_to_check:
                                fights_to_move.append(fight)
                                for fv in fight.fight_version_set.all().exclude(version=v):
                                    if fv.version not in versions_to_check and fv.version not in versions_checked:
                                        versions_to_check.append(fv.version)
                            versions_checked.append(v)
                        for fight in fights_to_move:
                            move_to_contest(fight,Contest.objects.get(pk=request.POST["fight-"+str(i)]))

                    else:
                        move_to_contest(fight_dict[i], Contest.objects.get(pk=request.POST["fight-"+str(i)]))
        elif request.POST["save"] == "prune":
            versions = Version.objects.filter(fight_version__fight__contest=contest).distinct()
            Registration.objects.filter(contest=contest).exclude(version__in=versions).delete()
            i = 1
            for f in fights:
                f.number = i
                i += 1
            Fight.objects.bulk_update(fights,["number"])
    return render(request, "main/editor/contest.html",
                  {"contest": contest, "other_contests": other_contests, "fights": fights, "applications": registrations})


def edt_fight_view(request, fight_id):
    fight = Fight.objects.get(pk=fight_id)
    has_winner = False
    for fv in fight.fight_version_set.all():
        if fv.won:
            has_winner = True
            break
    can_change = fight.can_edit(request.user)
    if not can_change:
        return redirect("%s?m=%s" % (reverse("main:message"), "You do not have permission to edit this fight."))

    if request.method == "POST":
        form = FightForm(request.POST, request.FILES, instance=fight)
        if form.is_valid():
            f = form.save()
            f.format_external_media()
            f.set_media_type()
            if "save" in request.POST:
                fight.calculate(commit=True)
                response = redirect("main:edtContest", fight.contest.id)
                response.delete_cookie("editing_fight")
            else:
                response = redirect("main:edtFightOverview", fight_id)
                response.delete_cookie("editing_fight")
        else:
            response = render(request, "main/editor/fight.html",
                              {"form": form, "has_winner": has_winner, "fight": fight})
            response.set_cookie("editing_fight", fight_id, ONE_HOUR_TIMER)
    else:
        if fight.fight_version_set.count() == 0:
            response = redirect('main:newFightVersion', fight_id)
            response.set_cookie("editing_fight", fight_id, ONE_HOUR_TIMER)
        else:
            form = FightForm(instance=fight)
            response = render(request, "main/editor/fight.html",
                              {"form": form, "has_winner": has_winner, "fight": fight})
            response.set_cookie("editing_fight", fight_id, ONE_HOUR_TIMER)
    return response


def edt_select_robot_view(request):
    name = request.GET.get("name") or ""
    ignore_wc = request.GET.get("nowc") or ""
    page = request.GET.get("page")
    try:
        page = int(page)
    except (ValueError, TypeError):
        page = 1

    if request.COOKIES.get("editing_team"):
        obj_type = "team"
        obj_id = request.COOKIES.get("editing_team")
    else:
        obj_type = "fight"
        obj_id = request.COOKIES.get("editing_fight")

    ignore_wc = ignore_wc.lower()
    ignore_wc = True if ignore_wc == "1" or ignore_wc == "on" or ignore_wc == "true" else False

    if ignore_wc or obj_type == "team":
        robot_list = Robot.objects.all()
    else:
        fight = Fight.objects.get(id=obj_id)
        wclass = fight.contest.weight_class.weight_grams
        robot_list = Robot.get_by_rough_weight(wclass)

    if name != "" and name is not None:
        robot_list = robot_list.filter(name__icontains=name).union(
            robot_list.filter(version__robot_name__icontains=name)).union(
            robot_list.filter(version__team__name__icontains=name))

    robot_list = robot_list.order_by("name")
    num = 50
    results = len(robot_list)
    robot_list = robot_list[num * (page - 1):num * page]

    return render(request, "main/editor/select_robot.html",
                  {"robot_list": robot_list,
                   "name": name, "obj_id": obj_id, "obj_type": obj_type, "page": page,
                   "pages": results // num if results % num == 0 else results // num + 1
                   })


def edt_team_view(request, team_id):
    team = Team.objects.get(pk=team_id)
    editing_version_id = request.COOKIES.get("rv_id")
    fight_id = request.COOKIES.get("editing_fight") or 0
    robot_or_version = request.COOKIES.get("robot_or_version")
    add_version = request.GET.get("add_version")
    add_robot = request.GET.get("add_robot")
    try:
        fight_id = int(fight_id)
    except (ValueError, TypeError):
        fight_id = 0
    try:
        v_id = int(add_version)
        v = Version.objects.get(pk=v_id)
        v.team = team
        v.save()
    except (ValueError, TypeError):
        pass
    try:
        robot_id = int(add_robot)
        r = Robot.objects.get(pk=robot_id)
        for v in r.version_set.all():
            v.team = team
            v.save()
    except (ValueError, TypeError):
        pass
    try:
        editing_version_id = int(editing_version_id)
    except (ValueError, TypeError):
        editing_version_id = 0

    if request.method == "POST":
        web_links = team.web_link_set.all()
        for i in range(len(web_links)):
            updated_url = request.POST["link" + str(i)]
            current = web_links[i]
            if updated_url != current.link:
                validator = URLValidator()
                try:
                    validator(updated_url)
                    current.link = updated_url
                    current.type = Web_Link.classify(updated_url)
                    current.save()
                except ValidationError:
                    pass

        new_link = request.POST["new-link"]
        if new_link != "" and new_link is not None:
            validator = URLValidator()
            wb = Web_Link()
            try:
                validator(new_link)
                wb.link = new_link
                wb.type = Web_Link.classify(new_link)
                wb.team = team
                wb.save()
            except ValidationError:
                pass
    response = render(request, "main/editor/team.html",
                      {"team": team, "editing_version_id": editing_version_id,
                       "robot_or_version": robot_or_version, "editing_fight":
                           fight_id != 0})
    response.set_cookie("editing_team", team_id, ONE_HOUR_TIMER)
    return response


def edt_select_team_view(request, fight_id):
    name = request.GET.get("name") or ""
    page = request.GET.get("page")
    robot_id = request.COOKIES.get("rv_id")
    selected_team = request.GET.get("team")
    try:
        robot_id = int(robot_id)
    except (ValueError, TypeError):
        robot_id = 0
    try:
        page = int(page)
    except (ValueError, TypeError):
        page = 1
    try:
        selected_team = int(selected_team)
        if robot_id != 0:
            return redirect(
                "%s?team_id=%s&fight_id=%s" % (reverse("main:newVersion", args=[robot_id]), selected_team, fight_id))
        else:
            return redirect("%s?team=%s&fight=%s" % (reverse("main:newRobot"), selected_team, fight_id))
    except (ValueError, TypeError):
        pass

    team_list = Team.objects.all()
    if name != "" and name is not None:
        team_list = team_list.filter(name__icontains=name)

    team_list = team_list.order_by("name")
    num = 50
    results = len(team_list)
    team_list = team_list[num * (page - 1):num * page]

    return render(request, "main/editor/select_team.html",
                  {"team_list": team_list,
                   "name": name, "fight_id": fight_id, "page": page, "v": robot_id,
                   "pages": results // num if results % num == 0 else results // num + 1
                   })


def edt_select_version_view(request, robot_id):
    robot = Robot.objects.get(id=robot_id)
    if request.COOKIES.get("editing_team"):
        obj_type = "team"
        obj_id = request.COOKIES.get("editing_team")
    else:
        obj_type = "fight"
        obj_id = request.COOKIES.get("editing_fight")
    return render(request, "main/editor/select_version.html",
                  {"robot": robot, "obj_type": obj_type, "obj_id": obj_id})


def edt_signup_version_view(request, fight_id, version_id):
    fight = Fight.objects.get(id=fight_id)
    version = Version.objects.get(id=version_id)
    contest = fight.contest
    fv = Fight_Version()
    fv.fight = fight
    fv.version = version
    fv.won = False
    fv.save()
    if Registration.objects.filter(version=version, contest=contest).count() == 0:
        reg = Registration()
        reg.contest = contest
        reg.version = version
        reg.approved = True
        reg.signee = version.owner
        reg.save()
    return redirect("%s?editor=True" % reverse("main:editFightVersion", args=[fight_id, fv.id]))


@login_required(login_url='/accounts/login/')
def delete_view(request, model, instance_id=None, next_id=None):
    redir = request.GET.get("redirect")
    if redir != "" and redir is not None:
        next_url = redir
    else:
        next_url = reverse("main:index")

    if model == "person":
        instance = Person.objects.get(pk=instance_id)
    elif model == "team":
        instance = Team.objects.get(pk=instance_id)
    elif model == "weight_class":
        instance = Weight_Class.objects.get(pk=instance_id)
    elif model == "robot":
        instance = Robot.objects.get(pk=instance_id)
        next_url = reverse("main:profile")
    elif model == "version":
        instance = Version.objects.get(pk=instance_id)
        next_url = reverse("main:robotDetail", args=[next_id])
    elif model == "franchise":
        instance = Franchise.objects.get(pk=instance_id)
    elif model == "event":
        instance = Event.objects.get(pk=instance_id)
        next_url = reverse("main:franchiseDetail", args=[next_id])
    elif model == "contest":
        instance = Contest.objects.get(pk=instance_id)
        next_url = reverse("main:eventDetail", args=[next_id])
    elif model == "registration":
        instance = Registration.objects.get(pk=instance_id)
        next_url = reverse("main:edtContest", args=[next_id])
    elif model == "fight":
        instance = Fight.objects.get(pk=instance_id)
        next_url = reverse("main:contestDetail", args=[next_id])
    elif model == "award":
        instance = Award.objects.get(pk=instance_id)
        next_url = reverse("main:eventDetail", args=[next_id])
    elif model == "person_team":
        instance = Person_Team.objects.get(pk=instance_id)
        next_url = reverse("main:profile")
    elif model == "fight_version":
        instance = Fight_Version.objects.get(pk=instance_id)
    elif model == "web_link":
        instance = Web_Link.objects.get(pk=instance_id)
    else:  # model == "person_franchise":
        instance = Person_Franchise.objects.get(pk=instance_id)
        next_url = reverse("main:profile")

    if request.GET.get("confirm") == "on":
        if isinstance(instance, Registration):
            can_change = instance.can_delete(request.user)
        else:
            can_change = instance.can_edit(request.user)

        if not can_change:
            return redirect("%s?m=%s" % (
                reverse("main:message"), "You do not have permission to delete this."))

        if isinstance(instance, Person):
            request.user.delete()
        else:
            instance.delete()

        return redirect(next_url)
    else:
        return render(request, "main/delete.html",
                      {"instance": instance, "model": model, "next_id": next_id, "redirect": redir})


def index_view(request):
    events = Event.objects.filter(start_date__gte=datetime.date.today()).order_by("start_date")[:5]
    try:
        random_robot = Robot.objects.order_by("?")[0]
    except:
        random_robot = None
    return render(request, "main/index.html", {"upcoming_event_list": events, "r": random_robot})


def event_index_view(request):
    name = request.GET.get("name") or ""
    page = request.GET.get("page")
    regions = request.GET.get("regions")
    country_code = request.GET.get("country") or ""
    past = request.GET.get("past")
    date_from = request.GET.get("date_from")  # TODO: Date stuff
    date_to = request.GET.get("date_to")
    distance = request.GET.get("distance")
    weight = request.GET.get("weight")

    num = 50
    try:
        weight = int(weight)
    except (ValueError, TypeError):
        weight = 0
    try:
        page = int(page)
    except (ValueError, TypeError):
        page = 1
    try:
        distance = int(distance)
    except (ValueError, TypeError):
        distance = 0

    if weight != 0:
        event_list = Event.get_by_rough_weight(weight)
    else:
        event_list = Event.objects.all()

    if country_code != "" and country_code is not None:
        country_code = country_code.upper()
        if regions == "on":
            try:
                event_list = event_list.filter(country__in=subdivisions.subs[country_code]).distinct()
            except KeyError:
                event_list = event_list.filter(country=country_code).distinct()
        elif country_code == "GB":
            event_list = event_list.filter(country__in=subdivisions.uk).distinct()
        else:
            event_list = event_list.filter(country=country_code).distinct()

    if name != "" and name is not None:
        event_list = event_list.filter(name__icontains=name).union(
            event_list.filter(contest__name__icontains=name)).union(
            event_list.filter(franchise__name__icontains=name))

    event_list = event_list.order_by("name").order_by("start_date")
    results = len(event_list)
    event_list = event_list[num * (page - 1):num * page]

    return render(request, "main/event_index.html",
                  {"event_list": event_list,
                   "page": page,
                   "pages": results // num if results % num == 0 else results // num + 1,
                   "weights": [(0, "")] + Weight_Class.LEADERBOARD_VALID,
                   "countries": [("", "")] + COUNTRY_CHOICES,
                   "chosen_country": country_code,
                   "chosen_weight": weight,
                   "name": name,
                   "distance": distance,
                   "date_from": date_from,
                   "date_to": date_to,
                   "past": past,
                   })


def event_detail_view(request, slug):
    event = Event.objects.get(slug=slug)
    fran = event.franchise
    if request.user.is_authenticated:
        can_change = fran.can_edit(request.user)
    else:
        can_change = False
    return render(request, "main/event_detail.html",
                  {"event": event,
                   "can_change": can_change,})


@login_required(login_url='/accounts/login/')#TODO: FORMS
def new_event_view(request, franchise_id):
    fran = Franchise.objects.get(pk=franchise_id)
    can_change = fran.can_edit(request.user)
    if not can_change:
        return redirect("%s?m=%s" % (
            reverse("main:message"), "You do not have permission to create a new event for this franchise."))
    if request.method == "POST":
        form = EventForm(request.POST,request.FILES)
        if form.is_valid():
            event = form.save(commit=False)
            event.franchise = fran
            event.make_slug()
            event.save()
            return redirect("main:edtEvent", event.id)
    else:
        form = EventForm()
    return render(request, "main/new_event.html", {"form": form, "fran": fran})


@login_required(login_url='/accounts/login/')
def modify_event_view(request, event_id):
    event = Event.objects.get(pk=event_id)
    can_change = event.can_edit(request.user)
    if not can_change:
        return redirect("%s?m=%s" % (reverse("main:message"), "You do not have permission to edit this event."))
    if request.method == "POST":
        form = EventForm(request.POST, request.FILES, instance=event)
        if form.is_valid():
            new = form.save()
            return redirect("main:edtEvent", new.id)
    else:
        form = EventForm(instance=event)
    return render(request, "main/forms/generic.html", {"form": form, "title": "Edit Event", "has_image":True,
                                                       "next_url": reverse("main:editEvent", args=[event_id])})


def contest_detail_view(request, contest_id):
    contest = Contest.objects.get(pk=contest_id)
    fights = Fight.objects.filter(contest=contest).order_by("number")
    registrations = contest.registration_set.all().order_by("signup_time")
    applied = False
    approved = False
    reserve = False
    app_ver = False
    if request.user.is_authenticated:
        can_change = contest.can_edit(request.user)
    else:
        can_change = False
    return render(request, "main/contest_detail.html",
                  {"contest": contest, "fights": fights, "applications": registrations, "can_change": can_change,
                   "applied": applied, "approved": approved, "reserve": reserve, "app_ver": app_ver})


@login_required(login_url='/accounts/login/')
def new_contest_view(request, event_id):
    event = Event.objects.get(pk=event_id)
    can_change = event.can_edit(request.user)
    if not can_change:
        return redirect(
            "%s?m=%s" % (reverse("main:message"), "You do not have permission to create a new contest for this event."))
    if request.method == "POST":
        form = ContestForm(request.POST)
        if form.is_valid():
            contest = form.save(commit=False)
            contest.event = event
            contest.save()
            return redirect("main:edtEvent", event.id)
    else:
        form = ContestForm()
    return render(request, "main/forms/generic.html", {"form": form, "title": "New Contest",
                                                       "next_url": reverse("main:newContest", args=[event_id])})


@login_required(login_url='/accounts/login/')
def edit_contest_view(request, contest_id):
    contest = Contest.objects.get(pk=contest_id)
    can_change = contest.can_edit(request.user)
    if not can_change:
        return redirect("%s?m=%s" % (reverse("main:message"), "You do not have permission to edit this contest."))
    if request.method == "POST":
        form = ContestForm(request.POST, instance=contest)
        if form.is_valid():
            form.save()
            return redirect("main:edtContest", contest.id)
    else:
        form = ContestForm(instance=contest)
    return render(request, "main/forms/generic.html", {"form": form, "title": "Edit Contest",
                                                       "next_url": reverse("main:editContest", args=[contest_id])})


def register(response):
    if response.method == "POST":
        form = RegistrationForm(response.POST)
        name = response.POST["name"]
        email = response.POST["email"]
        if form.is_valid():
            user = form.save()
            p = Person()
            p.name = name
            p.email = email
            p.user_id = user.id
            p.save()
            return redirect("main:index")
    else:
        form = RegistrationForm()
    return render(response, "main/register.html", {"form": form})


def robot_index_view(request):
    name = request.GET.get("name") or ""
    page = request.GET.get("page")
    regions = request.GET.get("regions")
    country_code = request.GET.get("country") or ""
    weight = request.GET.get("weight")
    has_awards = request.GET.get("has_awards")
    weapon = request.GET.get("weapon") or ""
    num = 50
    try:
        weight = int(weight)
    except (ValueError, TypeError):
        weight = 0
    try:
        page = int(page)
    except (ValueError, TypeError):
        page = 1

    if weight != 0:
        robot_list = Robot.get_by_rough_weight(weight)
    else:
        robot_list = Robot.objects.all()

    if country_code != "" and country_code is not None:
        country_code = country_code.upper()
        if regions == "on":
            try:
                robot_list = robot_list.filter(version__country__in=subdivisions.subs[country_code]).distinct()
            except KeyError:
                robot_list = robot_list.filter(version__country=country_code).distinct()
        elif country_code == "GB":
            robot_list = robot_list.filter(version__country__in=subdivisions.uk).distinct()
        else:
            robot_list = robot_list.filter(version__country=country_code).distinct()

    if name != "" and name is not None:
        robot_list = robot_list.filter(name__icontains=name).union(
            robot_list.filter(version__robot_name__icontains=name))

    if weapon != "" and weapon is not None:
        robot_list = robot_list.filter(version__weapon_type__icontains=weapon).distinct()

    if has_awards == "on":
        bad = []
        for robot in robot_list:
            if len(robot.awards()) == 0:
                bad.append(robot.id)
        robot_list = robot_list.exclude(id__in=bad)

    robot_list = robot_list.order_by("name")
    results = len(robot_list)
    robot_list = robot_list[num * (page - 1):num * page]
    return render(request, "main/robot_index.html",
                  {"robot_list": robot_list,
                   "page": page,
                   "pages": results // num if results % num == 0 else results // num + 1,
                   "weights": [(0, "")] + Weight_Class.LEADERBOARD_VALID,
                   "countries": [("", "")] + COUNTRY_CHOICES,
                   "chosen_country": country_code,
                   "chosen_weight": weight,
                   "name": name,
                   "has_awards": has_awards,
                   "weapon": weapon,
                   })


def leaderboard(request):
    #CSS Notes: row height up to 20em
    weight = request.GET.get("weight")
    year = request.GET.get("year")
    current_year = Event.objects.all().order_by("-end_date")[0].end_date.year
    years = [x for x in range(1994, current_year + 1)]
    try:
        year = int(year)
    except (ValueError,TypeError):
        year = current_year
    if year not in years:
        year = current_year
    if not weight or weight not in [x[0] for x in LEADERBOARD_WEIGHTS]:
        weight = "H"
    Leaderboard.update_class(weight)
    robot_list = Leaderboard.objects.filter(weight=weight, year=year).order_by("-ranking")
    top_three = []
    for i in range(robot_list.count() if robot_list.count() < 3  else 3):
        top_three.append( (robot_list[i],robot_list[i].robot.version_set.filter(first_fought__year__lte=year).order_by("-last_fought")[0]) )

    # robot_list = Leaderboard.get_current(weight)
    return render(request, "main/robot_leaderboard.html",
                  {"robot_list": robot_list,
                   "weights": [("H", "")] + LEADERBOARD_WEIGHTS[0:-1],
                   "chosen_weight": weight,
                   "chosen_year": year,
                   "years": years,
                   "top_three": top_three,
                   "is_this_year": year == current_year
                   })


def robot_detail_view(request, slug):
    r = Robot.objects.get(slug=slug)
    v = None
    if request.user.is_authenticated:
        can_change = r.can_edit(request.user)
    else:
        can_change = False

    if request.method == "GET":
        version_id = request.GET.get("v")
        try:
            version_id = int(version_id)
            v = Version.objects.get(pk=version_id)
        except (ValueError, TypeError):
            v = None
    fights = Fight.objects.filter(competitors__robot=r).order_by("contest__event__start_date", "contest__id", "number")
    awards = Award.objects.filter(version__robot=r)

    leaderboard_entries = Leaderboard.objects.filter(robot=r,ranking__gt=Robot.RANKING_DEFAULT).order_by("position","-year")
    best_lb_entry = leaderboard_entries.first()
    if leaderboard_entries.count() > 1:
        leaderboard_entries = leaderboard_entries[1:]
    else:
        leaderboard_entries = None

    return render(request, "main/robot_detail.html",
                  {"robot": r, "history":get_history(r), "fights": fights, "awards": awards, "ver": v, "can_change": can_change,
                   "version_set":r.version_set.all().order_by("number"),"best_lb_entry":best_lb_entry,"leaderboard_entries":leaderboard_entries})

def get_history(robot):
    fight_versions = Fight_Version.objects.filter(version__robot=robot,fight__fight_type="FC").order_by("fight__contest__event__start_date")
    rank = 1000
    history = [rank]
    for fv in fight_versions:
        rank += fv.ranking_change
        history.append(rank)
    return history


@login_required(login_url='/accounts/login/')
def robot_edit_view(request, robot_id):
    robot = Robot.objects.get(pk=robot_id)
    can_change = robot.can_edit(request.user)
    if not can_change:
        return redirect(
            "%s?m=%s" % (reverse("main:message"), "You do not have permission to edit this robot."))
    if request.method == "POST":
        form = RobotForm(request.POST, instance=robot)
        if form.is_valid():
            form.save()
            return redirect("main:robotDetail", robot.slug)
    else:
        form = RobotForm(instance=robot)
    return render(request, "main/forms/generic.html",
                  {"form": form, "title": "Edit Robot",
                   "next_url": reverse("main:editRobot", args=[robot_id])})

@login_required(login_url='/accounts/login/')
def version_edit_view(request, version_id):  # TODO: MASSIVE NEEDS TO BE DONE RIGHT HERE
    fight_id = request.COOKIES.get("editing_fight")  # If not 0, is editor.
    team_id = request.GET.get("team_id")# TODO: FORM
    try:
        fight_id = int(fight_id)
    except (ValueError, TypeError):
        fight_id = 0
    try:
        team_id = int(team_id)
    except (ValueError, TypeError):
        team_id = 0
    version = Version.objects.get(pk=version_id)
    can_change = version.can_edit(request.user)
    if not can_change:
        return redirect(
            "%s?m=%s" % (reverse("main:message"), "You do not have permission to edit this robot."))
    if request.method == "POST":
        form = VersionForm(request.POST, request.FILES, instance=version)
        if form.is_valid():
            form.save()
            response = redirect("main:versionDetail", version.id)
            response.delete_cookie("editing_version")
        else:
            response = render(request, "main/modify_version.html", {"form": form, "version": version, "new": False,
                                                                    "fight_id": fight_id, "team_id": team_id})
            response.set_cookie("editing_version", version.id, ONE_HOUR_TIMER)
    else:
        form = VersionForm(instance=version)
        response = render(request, "main/modify_version.html",
                          {"form": form, "version": version, "new": False, "fight_id": fight_id, "team_id": team_id})
        response.set_cookie("editing_version", version.id, ONE_HOUR_TIMER)
    return response


@login_required(login_url='/accounts/login/')
def new_version_view(request, robot_id): # TODO: FORM
    fight_id = request.COOKIES.get("editing_fight")  # If not 0, is editor.
    team_id = request.GET.get("team_id")
    try:
        team_id = int(team_id)
    except (ValueError, TypeError):
        team_id = 0

    robot = Robot.objects.get(pk=robot_id)
    can_change = robot.can_edit(request.user)
    if not can_change:
        return redirect(
            "%s?m=%s" % (reverse("main:message"), "You do not have permission to edit this robot."))
    valid_teams = Team.objects.filter(members__user=request.user)
    if fight_id != 0:
        valid_teams = Team.objects.filter(version__in=Version.objects.filter(robot=robot)).distinct()
        if team_id != 0:
            valid_teams = valid_teams | Team.objects.filter(pk=team_id).distinct()
    if request.method == "POST":
        form = NewVersionForm(request.POST, request.FILES)
        form.fields['team'].queryset = valid_teams
        if form.is_valid():
            version = form.save(robot, Person.objects.get(user=request.user))

            if fight_id != 0:
                response = redirect("main:edtSignupVersion", fight_id, version.id)
                response.delete_cookie("robot_or_version")
                response.delete_cookie("rv_id")
            else:
                response = redirect("main:versionDetail", version.id)
                response.delete_cookie("robot_or_version")
        else:
            response = render(request, "main/modify_version.html",
                              {"form": form, "robot": robot, "new": True, "fight_id": fight_id, "team_id": team_id})
            response.set_cookie("robot_or_version", "version", ONE_HOUR_TIMER)
            response.set_cookie("rv_id", robot_id, ONE_HOUR_TIMER)
    else:
        form = NewVersionForm()
        form.fields['team'].queryset = valid_teams
        if fight_id != 0:
            form.fields["weight_class"].initial = Fight.objects.get(id=fight_id).contest.weight_class
            selected_team = None
            if team_id != 0:
                selected_team = Team.objects.get(id=team_id)
            elif len(valid_teams) > 0:
                selected_team = valid_teams[0]
            if selected_team:
                form.fields['team'].initial = selected_team
                form.fields['country'].initial = selected_team.country
            else:
                form.fields['country'].initial = robot.country
        response = render(request, "main/modify_version.html",
                          {"form": form, "robot": robot, "new": True, "fight_id": fight_id, "team_id": team_id})
        response.set_cookie("robot_or_version", "version", ONE_HOUR_TIMER)
        response.set_cookie("rv_id", robot_id, ONE_HOUR_TIMER)
    return response


def team_detail_view(request, slug):
    team = Team.objects.get(slug=slug)
    pt = None
    if request.user.is_authenticated:
        can_change = team.can_edit(request.user)
        if can_change:
            try:
                pt = Person_Team.objects.get(team=team, person__user=request.user)
            except ObjectDoesNotExist:
                pass
    else:
        can_change = False
    return render(request, "main/team_detail.html",
                  {"team": team, "can_change": can_change, "leave_id": pt.id if pt else 1})


def team_index_view(request):
    name = request.GET.get("name") or ""
    page = request.GET.get("page")
    regions = request.GET.get("regions")
    country_code = request.GET.get("country") or ""
    num = 50
    try:
        page = int(page)
    except (ValueError, TypeError):
        page = 1
    team_list = Team.objects.all()

    if country_code != "" and country_code is not None:
        country_code = country_code.upper()
        if regions == "on":
            try:
                team_list = team_list.filter(country__in=subdivisions.subs[country_code]).distinct()
            except KeyError:
                team_list = team_list.filter(country=country_code).distinct()
        elif country_code == "GB":
            team_list = team_list.filter(country__in=subdivisions.uk).distinct()
        else:
            team_list = team_list.filter(country=country_code).distinct()

    if name != "" and name is not None:
        team_list = team_list.filter(name__icontains=name)

    team_list = team_list.order_by("name")
    results = len(team_list)
    team_list = team_list[num * (page - 1):num * page]
    return render(request, "main/team_index.html",
                  {"team_list": team_list,
                   "page": page,
                   "pages": results // num if results % num == 0 else results // num + 1,
                   "countries": [("", "")] + COUNTRY_CHOICES,
                   "chosen_country": country_code,
                   "name": name,
                   })


@login_required(login_url='/accounts/login/')  # TODO: No validation anymore
def new_robot_view(request): # TODO: FORM
    fight_id = request.COOKIES.get("editing_fight")
    team_id = request.GET.get("team")
    try:
        fight_id = int(fight_id)
    except (ValueError, TypeError):
        fight_id = 0
    try:
        team_id = int(team_id)
        team = Team.objects.get(id=team_id)
    except (ValueError, TypeError):
        team = None

    if request.method == "POST":
        form = NewRobotForm(request.POST, request.FILES)
        if form.is_valid():
            v = form.save(team, Person.objects.get(user=request.user))[1]
            #TODO: SLug
            if fight_id != 0:
                response = redirect("main:edtSignupVersion", fight_id, v.id)
                response.delete_cookie("robot_or_version")
            else:
                response = redirect("main:index")
                response.delete_cookie("robot_or_version")
        else:
            response = render(request, "main/new_robot.html", {"form": form, "team": team, "fight_id": fight_id})
            response.set_cookie("robot_or_version", "robot", ONE_HOUR_TIMER)
    else:
        form = NewRobotForm()
        if fight_id != 0:
            form.fields["weight_class"].initial = Fight.objects.get(id=fight_id).contest.weight_class
        if team_id:
            form.fields['country'].initial = team.country
        response = render(request, "main/new_robot.html", {"form": form, "team": team, "fight_id": fight_id})
        response.set_cookie("robot_or_version", "robot", ONE_HOUR_TIMER)
    return response


def version_detail_view(request, version_id):
    v = Version.objects.get(pk=version_id)
    robot_slug = v.robot.slug
    return redirect("%s?v=%d" % (reverse("main:robotDetail", args=[robot_slug]), version_id))


@login_required(login_url='/accounts/login/')
def team_modify_view(request, team_id=None):
    fight_id = request.COOKIES.get("editing_fight")
    try:
        fight_id = int(fight_id)
    except (ValueError, TypeError):
        fight_id = 0

    can_change = True
    if team_id is not None:
        team = Team.objects.get(pk=team_id)
        can_change = team.can_edit(request.user)
    if not can_change:
        return redirect("%s?m=%s" % (reverse("main:message"), "You do not have permission to edit this team."))

    if request.method == "POST":
        if team_id is None:
            form = TeamForm(request.POST, request.FILES)
        else:
            team = Team.objects.get(pk=team_id)
            form = TeamForm(request.POST, request.FILES, instance=team)
        if form.is_valid():
            new = form.save()
            if team_id is None:
                new.make_slug(save=True)
                person = Person.objects.get(user=request.user)
                Person_Team.objects.create(team=new, person=person)
            return redirect("main:edtTeam", new.id)
    else:
        if team_id is None:
            form = TeamForm()
            return render(request, "main/forms/generic.html",
                   {"form": form, "title": "New Team", "has_image": True,
                    "next_url": reverse("main:newTeam")})
        else:
            team = Team.objects.get(pk=team_id)
            form = TeamForm(instance=team)
            return render(request, "main/forms/generic.html",
                   {"form": form, "title": "Edit Team", "has_image": True,
                    "next_url": reverse("main:editTeam", args=[team_id])})



@login_required(login_url='/accounts/login/')
def franchise_modify_view(request, franchise_id=None):
    can_change = True
    if franchise_id is not None:
        franchise = Franchise.objects.get(pk=franchise_id)
        can_change = franchise.can_edit(request.user)
    if not can_change:
        return redirect("%s?m=%s" % (reverse("main:message"), "You do not have permission to edit this franchise."))
    if request.method == "POST":
        if franchise_id is None:
            form = FranchiseForm(request.POST, request.FILES)
        else:
            franchise = Franchise.objects.get(pk=franchise_id)
            form = FranchiseForm(request.POST, request.FILES, instance=franchise)
        if form.is_valid():
            new = form.save()
            if franchise_id is None:
                new.make_slug(save=True)
                person = Person.objects.get(user=request.user)
                Person_Franchise.objects.create(franchise=new, person=person)
            return redirect("main:index")
    else:
        if franchise_id is None:
            form = TeamForm()
        else:
            franchise = Franchise.objects.get(pk=franchise_id)
            form = FranchiseForm(instance=franchise)
    if franchise_id is None:
        return render(request, "main/forms/generic.html",
                      {"form": form, "title": "New Franchise", "has_image": True,
                       "next_url": reverse("main:newFranchise")})
    else:
        return render(request, "main/forms/generic.html",
                      {"form": form, "title": "Edit Franchise", "has_image": True,
                       "next_url": reverse("main:editFranchise", args=[franchise_id])})


def franchise_detail_view(request, slug):
    fran = Franchise.objects.get(slug=slug)
    can_change = True  # TODO: lol
    return render(request, "main/franchise_detail.html",
                  {"fran": fran, "can_change": can_change, "leave_id": 1})  # pf.id or 1}) #TODO: lol


def franchise_index_view(request):
    name = request.GET.get("name") or ""
    page = request.GET.get("page")
    num = 50
    try:
        page = int(page)
    except (ValueError, TypeError):
        page = 1
    fran_list = Franchise.objects.all()

    if name != "" and name is not None:
        fran_list = fran_list.filter(name__icontains=name)

    fran_list = fran_list.order_by("name")
    results = len(fran_list)
    fran_list = fran_list[num * (page - 1):num * page]
    return render(request, "main/franchise_index.html",
                  {"fran_list": fran_list,
                   "page": page,
                   "pages": results // num if results % num == 0 else results // num + 1,
                   "name": name,
                   })


@login_required(login_url='/accounts/login/')
def new_fight_view(request, contest_id):  # TODO: Make sure you can't add the same Version to the same fight.
    contest = Contest.objects.get(pk=contest_id)
    can_change = contest.can_edit(request.user)
    if not can_change:
        return redirect(
            "%s?m=%s" % (reverse("main:message"), "You do not have permission to add a fight to this contest."))
    f = Fight()
    f.contest = contest
    try:
        f.number = contest.fight_set.all().order_by("-number")[0].number + 1
    except IndexError:
        f.number = 1
    if contest.fight_type == "MU":
        f.save()
        if request.GET.get("editor") == "true":
            return redirect("main:edtFightOverview", f.id)
        else:
            return redirect("main:editJustFight", f.id)
    else:
        f.fight_type = contest.fight_type
        f.save()
        if request.GET.get("editor") == "true":
            return redirect("main:edtFightOverview", f.id)
        else:
            return redirect("main:editWholeFight", f.id)


@login_required(login_url='/accounts/login/')
def fight_editj_view(request, fight_id):  # Just the Fight TODO: refactor this to a name that makes more sense
    fight = Fight.objects.get(pk=fight_id)
    can_change = fight.can_edit(request.user)
    if not can_change:
        return redirect("%s?m=%s" % (reverse("main:message"), "You do not have permission to edit this fight."))
    if request.method == "POST":
        form = FightForm(request.POST, request.FILES, instance=fight)
        if form.is_valid():
            f = form.save()
            f.format_external_media()
            f.set_media_type()

            return redirect("main:editWholeFight", fight_id)
    else:
        form = FightForm(instance=fight)
        return render(request, "main/forms/generic.html",
                      {"form": form, "title": "Edit Fight", "has_image":True, "next_url": reverse("main:editJustFight", args=[fight_id])})


def fight_detail_view(request, fight_id):  # TODO: Sort this better
    fight = Fight.objects.get(pk=fight_id)
    if request.user.is_authenticated:
        can_change = fight.can_edit(request.user)
    else:
        can_change = False
    return render(request, "main/fight_detail.html", {"fight": fight, "can_change": can_change})


@login_required(login_url='/accounts/login/')  # Still Being Used
def modify_fight_version_view(request, fight_id, vf_id=None): #TODO SHIFT FORM
    # editor = request.GET.get("editor") or ""
    editor = request.COOKIES.get("editing_fight") is not None and request.COOKIES.get("editing_fight") != ""
    fight = Fight.objects.get(pk=fight_id)
    # editor = editor.lower() == "true"

    can_change = fight.can_edit(request.user)
    if not can_change:
        return redirect("%s?m=%s" % (reverse("main:message"), "You do not have permission to edit this fight."))
    registered = Version.objects.filter(registration__contest=fight.contest.id).order_by("name", "robot__name")

    if vf_id is not None:
        vf = Fight_Version.objects.get(pk=vf_id)
    else:
        vf = Fight_Version()
        vf.fight = fight
    form = RobotFightForm(request.POST or None, instance=vf)
    if form.is_valid():
        form.save()
        if editor:
            response = redirect("main:edtFightOverview", fight.id)
        else:
            response = redirect("main:editWholeFight", fight_id)
    else:
        form.fields['version'].queryset = registered
        response = render(request, "main/modify_fight_version.html",
                          {"form": form, "fight_id": fight_id, "fight_version_id": vf_id, "editor": editor})

    response.delete_cookie("editing_version")
    response.delete_cookie("editing_team")
    return response
    # TODO: This is basically identical to modify_fight and probably many more (maybe not anymore?)


def award_index_view(request, event_slug):
    event = Event.objects.get(slug=event_slug)
    awards = Award.objects.filter(event=event).order_by("-award_type", "name")
    if request.user.is_authenticated:
        can_change = event.can_edit(request.user)
    else:
        can_change = False
    return render(request, "main/award_index.html", {"award_list": awards, "event": event, "can_change": can_change})


@login_required(login_url='/accounts/login/')
def new_award_view(request, event_id):
    event = Event.objects.get(pk=event_id)
    can_change = event.can_edit(request.user)
    if not can_change:
        return redirect("%s?m=%s" % (reverse("main:message"), "You do not have permission to edit this event."))
    if request.method == "POST":
        form = AwardForm(request.POST)
        if form.is_valid():
            a = form.save(False)
            a.event = event
            a.save()
            return redirect("main:eventDetail", event.slug)
    else:
        form = AwardForm()
        form.fields['contest'].queryset = Contest.objects.filter(event=event)
        form.fields['version'].queryset = Version.objects.filter(
            registration__contest__in=event.contest_set.all()).order_by("name", "robot__name").distinct()
        return render(request, "main/forms/generic.html", {"form": form, "title": "New Award", "next_url": reverse("main:newAward",args=[event_id])})


# TODO: THis is almost identical to edit award should probably make a more generic one esp the template

@login_required(login_url='/accounts/login/')
def award_edit_view(request, award_id):
    a = Award.objects.get(pk=award_id)
    can_change = a.can_edit(request.user)
    if not can_change:
        return redirect("%s?m=%s" % (reverse("main:message"), "You do not have permission to edit this award."))
    if request.method == "POST":
        form = AwardForm(request.POST, instance=a)
        if form.is_valid():
            form.save()
            return redirect("main:eventDetail", a.event.slug)
    else:
        form = AwardForm(instance=a)
        form.fields['contest'].queryset = Contest.objects.filter(event=a.event)
        form.fields['version'].queryset = Version.objects.filter(registration__contest__in=a.event.contest_set.all()).distinct()
        return  render(request, "main/forms/generic.html", {"form": form, "title": "Edit Award", "next_url": reverse("main:editAward",args=[award_id])})


@login_required(login_url='/accounts/login/')
def person_edit_view(request, person_id):
    person = Person.objects.get(pk=person_id)
    can_change = person.can_edit(request.user)
    if not can_change:
        return redirect(
            "%s?m=%s" % (reverse("main:message"), "You do not have permission to edit this account."))
    if request.method == "POST":
        form = PersonForm(request.POST, instance=person)
        if form.is_valid():
            form.save()
            return redirect("main:profile")
    else:
        form = PersonForm(instance=person)
    return  render(request, "main/forms/generic.html", {"form": form, "title": "Edit Person", "next_url": reverse("main:editPerson",args=[person_id])})


def message_view(request):
    if request.method == "GET":
        message = request.GET.get("m")
        return render(request, "main/message.html", {"text": message})
    else:
        return redirect("main:index")


def search_view(request):
    franchises = None
    fran_len = 0
    teams = None
    team_len = 0
    robots = None
    robot_len = 0
    events = None
    event_len = 0
    search_term = None
    if request.method == "GET":
        search_term = request.GET.get("q")
        franchises = Franchise.objects.filter(name__icontains=search_term).distinct()
        fran_len = len(franchises)
        franchises = franchises[:10]
        teams = Team.objects.filter(name__icontains=search_term).distinct()
        team_len = len(teams)
        teams = teams[:10]
        robots = Robot.objects.filter(name__icontains=search_term).union(
            Robot.objects.filter(version__robot_name__icontains=search_term))
        robot_len = len(robots)
        robots = robots[:10]
        events = Event.objects.filter(name__icontains=search_term).union(
            Event.objects.filter(contest__name__icontains=search_term))
        event_len = len(events)
        events = events[:10]
    return render(request, "main/search.html",
                  {"events": events, "robots": robots, "teams": teams, "franchises": franchises,
                   "search_term": search_term, "fran_len": fran_len, "event_len": event_len, "robot_len": robot_len,
                   "team_len": team_len})


@login_required(login_url='/accounts/login/')
def new_weight_class_view(request, return_id):
    if request.method == "POST":
        form = WeightClassForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("main:newContest", return_id)
    else:
        form = WeightClassForm()
    return render(request, "main/forms/generic.html", {"form": form, "title": "New Weight Class", "next_url": reverse("main:newWeightClass",args=[return_id])})


@login_required(login_url='/accounts/login/')
def profile_view(request):
    user = request.user
    me = Person.objects.get(user=user)
    p_t = Person_Team.objects.filter(person=me)
    teams = []
    for value in p_t:
        teams.append(value.team)
    p_f = Person_Franchise.objects.filter(person=me)
    frans = []
    for value in p_f:
        frans.append(value.franchise)

    return render(request, "registration/profile.html",
                  {"user": user, "person": me, "teams": teams, "franchises": frans})


@login_required(login_url='/accounts/login/')
def add_member_view(request, obj_type=None, obj_id=None):
    if obj_type == "franchise":
        obj = Franchise.objects.get(pk=obj_id)
    else:  # obj is team
        obj = Team.objects.get(pk=obj_id)

    can_change = obj.can_edit(request.user)
    if not can_change:
        return redirect(
            "%s?m=%s" % (reverse("main:message"), "You do not have permission to edit this franchise."))

    username = request.GET.get("username") or ""
    if username == "" or username is None:
        return render(request, "main/add_member.html", {"error": False, "obj_type": obj_type, "obj_id": obj_id})

    try:
        new = Person.objects.get(user__username=username)
        if obj_type == "franchise":
            if Person_Franchise.objects.filter(franchise=obj, person=new).exists():  # No repeat members
                return redirect("main:franchiseDetail", obj_id)
            yes = Person_Franchise()
            yes.franchise = obj
        else:
            if Person_Team.objects.filter(team=obj, person=new).exists():
                return redirect("main:teamDetail", obj_id)
            yes = Person_Team()
            yes.team = obj

        yes.person = new
        yes.save()
        if obj_type == "franchise":
            return redirect("main:franchiseDetail", obj_id)
        else:
            return redirect("main:teamDetail", obj_id)
    except:
        return render(request, "main/add_member.html", {"error": True, "obj_type": obj_type, "obj_id": obj_id})


def robot_transfer_view(request, robot_id, team_id=None):
    if not team_id:
        robot = Robot.objects.get(pk=robot_id)
        can_change = robot.can_edit(request.user)
        if not can_change:
            return redirect(
                "%s?m=%s" % (reverse("main:message"), "You do not have permission to edit this robot."))
        if request.method == "POST":
            form = TransferRobotForm(request.POST)
            if form.is_valid():
                team = form.save()
                return redirect("main:transferRobot", robot_id, team.id)
        else:
            form = TransferRobotForm()
        return render(request, "main/transfer_robot_form.html", {"form": form, "robot": robot})

    else:
        robot = Robot.objects.get(pk=robot_id)
        team = Team.objects.get(pk=team_id)

        can_change = robot.can_edit(request.user)
        if not can_change:
            return redirect(
                "%s?m=%s" % (reverse("main:message"), "You do not have permission to edit this robot."))

        if request.GET.get("confirm") == "on":
            new_version = robot.version_set.last()
            new_version.pk = None
            new_version.team = team
            new_version.description += "\nThis version has been transferred to " + team.__str__() + " Please edit it to match your version, but don't delete it or the robot will revert back to previous owners."
            new_version.save()
            return redirect("main:robotDetail", robot.slug)
        else:
            return render(request, "main/transfer_robot.html", {"robot": robot, "team": team})

def hall_of_fame_view(request):
    members = Robot.objects.filter(hallofame__full_member=True).order_by("-first_fought")
    honoraries = Robot.objects.filter(hallofame__full_member=False).order_by("-first_fought")
    return render(request,"main/hall_of_fame.html",{"members":members,"honoraries":honoraries})


def credits_view(request):
    return render(request, "main/credits.html", {})


# ------IMPORT FROM OLD DATA--------
"""
def importView(aVariableNameThatWontBeUsed):
    oldDB = sqlite3.connect("D:/Jonathan/Robot Archive App/old/robotCombatArchive.db")
    cursor = oldDB.cursor()
    az = re.compile("[^a-zA-Z0-9]")
    robotDict = {}
    versionDict = {}
    franchiseStubDict = {}
    weightClassDict = {0: Weight_Class.objects.get(pk=1), 39: Weight_Class.objects.get(pk=1)}
    theMan = Person(name="Unknown Person", email="real@real.com")
    theMan.save()

    oldEvents = cursor.execute("Select * from events order by date").fetchall()

    for i in range(len(oldEvents)):  # FOR EVERY EVENT
        print("~~~~~~~~~~~~~~~~~ SAVING: " + oldEvents[i][1] + " ~~~~~~~~~~~~~~~~~")
        entrants = []
        try:
            fran = franchiseStubDict[oldEvents[i][2]]
        except KeyError:
            fran = Franchise()
            fran.name = oldEvents[i][2] + " Stub Franchise"
            franchiseStubDict[oldEvents[i][2]] = fran
            fran.save()
        e = Event()
        e.name = oldEvents[i][1]
        e.country = oldEvents[i][2]
        try:
            e.start_date = datetime.datetime.strptime(oldEvents[i][3], "%Y-%m-%d").date()
        except ValueError:
            e.start_date = datetime.datetime.strptime("1970-01-01", "%Y-%m-%d").date()
        e.end_date = e.start_date
        #e.start_time = e.end_time = datetime.time.fromisoformat("00:00")
        #e.registration_open = e.registration_close = datetime.datetime.strptime("1970-01-01", "%Y-%m-%d")
        e.latitude = e.longitude = 0
        e.franchise = fran
        e.save()
        c = Contest()
        c.name = e.name + " stub contest"
        c.fight_type = "MU"
        c.auto_awards = False
        c.event = e
        c.weight_class = weightClassDict[0]
        c.save()
        fights = cursor.execute(
            "Select * from fights where eventID = " + str(oldEvents[i][0]) + " order by number").fetchall()
        for j in range(len(fights)):  # SAVE EVERY FIGHT
            fvs = cursor.execute("Select * from robotFights where fightID = " + str(fights[j][0])).fetchall()
            fight = Fight()
            fight.number = fights[j][5]
            fight.contest = c
            if fights[j][3][:4].lower() == "http":
                fight.external_media = fights[j][3]
                fight.format_external_media()
            if fights[j][2] == "Full Combat":
                fight.fight_type = "FC"
            elif fights[j][2] == "Sportsman":
                fight.fight_type = "SP"
            else:
                fight.fight_type = "NC"

            for k in range(len(fvs)):  # SAVE FIGHT_VERSION FOR ALL FIGHTS
                # print(fvs[k])
                versionQ = cursor.execute("Select * from robotVersions where id = " + str(fvs[k][1])).fetchone()
                try:
                    ver = versionDict[versionQ[0]]
                    # print("hi ", versionQ)
                except KeyError:
                    ver = versionFunc(cursor, az, robotDict, versionDict, theMan, weightClassDict, e.start_date,
                                      versionQ=versionQ)
                if ver.id not in entrants:
                    entrants.append(ver.id)
                    Registration(approved=True,version=ver,signee=theMan,contest=c).save()

                    ver.last_fought = e.start_date
                    ver.robot.last_fought = e.start_date
                    ver.robot.save()
                    ver.save()
                # print("Ver: ", ver)
                fv = Fight_Version()
                fv.fight = fight
                fv.version = ver
                fv.won = fvs[k][3]
                fv.ranking_change = fvs[k][4] - fvs[k][5]
                fight.set_media_type() # performs fight.save()
                fv.save()
            if fight.__str__() != fights[j][1]:
                fight.name = fights[j][1]
                if len(fight.name) > 255:
                    fight.name = fight.name[:255]
                fight.save()
            print("Saved:", fight)
            # print(versionDict)
            # print(robotDict)
        awards = cursor.execute("Select * from awards where eventID = " + str(oldEvents[i][0])).fetchall()
        for j in range(len(awards)):  # SAVE AWARDS
            a = Award()
            a.name = awards[j][1]
            a.award_type = 0
            a.contest = c
            a.event = e
            try:
                a.version = versionDict[awards[j][3]]
            except KeyError:
                a.version = versionFunc(cursor, az, robotDict, versionDict, theMan, weightClassDict, e.start_date,
                                        versionID=awards[j][3])
            a.save()

    return render(aVariableNameThatWontBeUsed, "main/message.html", {"text": "Hmm yse"})


def versionFunc(cursor, az, robotDict, versionDict, per, weightClassDict, date, versionID=None, versionQ=None, ):
    if versionQ is None:
        versionQ = cursor.execute("Select * from robotVersions where id = " + str(versionID)).fetchone()
    robotQ = cursor.execute("Select * from robots where id = " + str(versionQ[1])).fetchone()
    try:
        rob = robotDict[versionQ[1]]
    except KeyError:
        rob = Robot()
        rob.name = robotQ[1]
        rob.set_alphanum(commit=False)
        if robotQ[7] is not None and robotQ[7] != "": # This overwrite is intentional as name needed for alphanum.
            rob.name = robotQ[7]
            rob.requires_translation = True
        rob.country = robotQ[2]
        rob.wins = robotQ[5]
        rob.losses = robotQ[6]
        rob.ranking = robotQ[4]
        rob.first_fought = date
        rob.last_fought = date
        rob.save()
        robotDict[versionQ[1]] = rob

    ver = Version()
    ver.robot = rob
    if versionQ[2] != rob.name:
        ver.robot_name = versionQ[2]
    if len(versionQ[5]) < 6:
        ver.name = versionQ[5]
    ver.description = versionQ[5]
    ver.weapon_type = "Unspecified"
    ver.owner = per
    ver.first_fought = date
    ver.last_fought = date
    ver.set_alphanum(commit=False)
    ver.country = robotQ[2]

    try:
        wc = weightClassDict[versionQ[4]]
    except KeyError:
        wcQ = cursor.execute("Select * from weightClasses where id = " + str(versionQ[4])).fetchone()
        wc = Weight_Class()
        wc.name = wcQ[1]
        wc.weight_grams = wcQ[2]
        weightClassDict[versionQ[4]] = wc
        wc.save()
    ver.weight_class = wc
    if versionQ[6] != "https://image.flaticon.com/icons/png/512/36/36601.png":
        if versionQ[6][:4].lower() == "http":
            l = 0
            while True:
                if l > 10:
                    break
                try:
                    urllib.request.urlretrieve(versionQ[6], "robotImage")
                    break
                except:
                    print("failed to save image:", versionQ[6], "attempt:", l + 1)
                    time.sleep(2)
                    l += 1
            if l > 10:
                print("IMAGE FAILED TO SAVE: " + versionQ[2])
            img = Image.open("robotImage")
        else:
            img = Image.open("D:/Jonathan/Robot Archive App/old/robotImages/" + versionQ[6][6:])
        rawData = BytesIO()
        img.save(rawData, img.format)
        name = re.sub(az, "", versionQ[2])
        if len(name) > 25:
            name = name[:25]
        ver.image.save(str(versionQ[0]) + "_" + name + "." + img.format.lower(), File(rawData))
    ver.save()
    versionDict[versionQ[0]] = ver
    return ver
"""


def recalc_all(request):
    #Need top update more robots than currently doing to add the X to them
    Robot.objects.all().update(ranking=Robot.RANKING_DEFAULT, wins=0, losses=0, lb_weight_class="X")

    fights = Fight.objects.all().order_by("contest__event__start_date", "contest__event__end_date",
                                          "contest__weight_class__weight_grams", "contest_id", "number")
    contest_cache = None
    fvs = []
    version_dictionary = {}
    for fight in fights:
        if contest_cache != fight.contest:
            if contest_cache is not None:
                #print("updating robots")
                #for reg in contest_cache.registration_set.all():
                #    Leaderboard.update_robot_weight_class(reg.version.robot, year=contest_cache.event.end_date.year)
                if contest_cache.event.end_date.year != fight.contest.event.end_date.year:
                    if fight.contest.event.end_date.year == 1998:
                        return
                    #breakpoint()
                    print("~~~~~~~~~~~~~~~~~~~~~~~~~~Saving year " + str(contest_cache.event.end_date.year)+"~~~~~~~~~~~~~~~~~~~~~~~~~~")
                    with transaction.atomic():
                        for fv in fvs:
                            fv.save()
                        for v in version_dictionary.values():
                            v.save()
                            v.robot.save()


                    print("updating leaderboard")
                    for v in version_dictionary.values():
                        Leaderboard.update_robot_weight_class(v.robot, year=contest_cache.event.end_date.year)
                    Leaderboard.update_all(contest_cache.event.end_date.year)
                    fvs = []
                    version_dictionary = {}
            contest_cache = fight.contest
            event_cache = contest_cache.event
            print("Saving:", contest_cache, fight.contest.event)
        result = fight.calculate(False,version_dictionary)
        fvs += result[0]
        version_dictionary = result[1]

    print("Saving Final Batch")
    with transaction.atomic(): # Save the leftovers
        for fv in fvs:
            fv.save()
            fv.version.save()
            fv.version.robot.save()
    print("Done!")
    return render(request, "main/credits.html", {})


def tournament_tree(request):
    # 97
    # 3216
    contest = Contest.objects.get(pk=97)
    all_fights = Fight.objects.filter(contest=contest)
    entry = Fight.objects.get(pk=3216)
    fights = [entry]
    links = {}
    out = ""
    entrantDict = {}
    for i, version in enumerate(Version.objects.filter(fight__in=all_fights).distinct()):
        entrantDict[version.id] = i + 1

    for fight in fights:
        # print(fight)
        for fv in fight.fight_version_set.all():
            prev = all_fights.filter(fight_version__version=fv.version)
            prev = prev.exclude(number__gte=fight.number).order_by("-number")
            if len(prev) > 0:
                fights.append(prev[0])
                links[prev[0].fight_version_set.get(version=fv.version)] = fight
    localIDDict = {}
    i = 0
    # print(links)
    for fight in all_fights:
        out += "<fight"
        try:
            localID = localIDDict[fight]
        except KeyError:
            i += 1
            localID = localIDDict[fight] = i
        out += ' id="' + str(localID) + '">\n'
        out += "\t<db_id>" + str(fight.id) + "</db_id>\n"
        for fv in fight.fight_version_set.all():
            out += '\t<competitor entrant="' + str(entrantDict[fv.version.id]) + '">\n'
            try:
                next_fight = links[fv]
                try:
                    nextLocalID = localIDDict[next_fight]
                except KeyError:
                    i += 1
                    nextLocalID = localIDDict[next_fight] = i
                out += "\t\t<next>" + str(nextLocalID) + "</next>\n"
            except KeyError:
                out += "\t\t<eliminated/>\n"
            out += "\t</competitor>\n"
        out += "</fight>\n"
    print(out)

    return render(request, "main/credits.html", {})


def graph_test(request):
    return render(request, 'graph_test.html')


def graph_data(request):
    labels = []
    data = []
    wedge = Robot.objects.get(id=88)
    for version in wedge.version_set.all():
        for fv in version.fight_version_set.all():
            labels.append("hi")
            data.append(fv.ranking_change)
    return JsonResponse(data={
        'labels': labels,
        'data': data,
    })
