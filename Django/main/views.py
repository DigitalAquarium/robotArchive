import datetime
import random
from os.path import isdir
from shutil import copy2

from os import listdir, replace, makedirs

from django.contrib.auth.decorators import login_required, permission_required
from django.core.validators import URLValidator
from django.db.models import F, When, Case
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.http import Http404

from main import subdivisions
from .forms import *

ONE_HOUR_TIMER = 3600


@permission_required("main.change_event", raise_exception=True)
@permission_required("main.add_event", raise_exception=True)
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
                   "title": "Editor Home",
                   })


@permission_required("main.add_event", raise_exception=True)
def edt_new_event_view(request):
    fran_id = request.GET.get("franchise") or ""
    if fran_id:
        fran_id = int(fran_id)
        fran = Franchise.objects.get(pk=fran_id)
        # Set up form
        if request.method == "POST":
            form = NewEventFormEDT(request.POST, request.FILES)
        else:
            form = NewEventFormEDT()
            if fran.event_set.count() > 0:
                countries = fran.event_set.values('country')
                cdict = {}
                for c in countries:
                    if c['country'] in cdict:
                        cdict[c['country']] += 1
                    else:
                        cdict[c['country']] = 1
                form.fields["country"].initial = max(cdict, key=cdict.get)
        if fran.event_set.count() > 0:
            form.fields["prev_logo"].choices = [("", "")] + [(x["logo"], x["logo"]) for x in
                                                             fran.event_set.values("logo").distinct()]

        # Save form if required
        if request.method == "POST" and form.is_valid():
            event = form.save(fran)
            event.make_slug(save=True)
            return redirect("main:edtEvent", event.id)

    else:
        fran = None
        form = NewEventFormEDT()
    return render(request, "main/editor/new_event.html", {"form": form, "fran": fran, "title": "New Event"})


@permission_required("main.add_contest", raise_exception=True)
@permission_required("main.change_event", raise_exception=True)
@permission_required("main.add_location", raise_exception=True)
@permission_required("main.change_location", raise_exception=True)
def edt_event_view(request, event_id):
    try:
        event = Event.objects.get(pk=event_id)
    except Event.DoesNotExist:
        raise Http404

    if request.method == "POST":
        if request.POST["save"] == "save-source":
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
                        current.last_accessed = timezone.now()
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
                    src.name = new_name
                    src.link = new_link
                    src.archived = "web.archive.org" in new_link
                    src.last_accessed = timezone.now()
                    src.event = event
                    src.save()
                except ValidationError:
                    pass
        elif request.POST["save"] == "save-location":
            location_dropdown = request.POST["location-id"]

            if location_dropdown == "-1":
                new_location = Location()
                new_location.name = request.POST["new-location-name"]
                new_location.latitude = request.POST["new-location-lat"]
                new_location.longitude = request.POST["new-location-lng"]
                new_location.save()

            else:
                location_dropdown = int(location_dropdown)
                new_location = Location.objects.get(id=location_dropdown)

            event.location = new_location
            event.save()

    locations = Location.objects.all().order_by("name")
    return render(request, "main/editor/event.html",
                  {"event": event, "locations": locations, "title": "edt " + str(event)})


@permission_required("main.change_franchise", raise_exception=True)
def edt_fran_view(request):
    name = request.GET.get("name") or ""

    fran_list = Franchise.objects.all()

    if name != "" and name is not None:
        fran_list = fran_list.filter(name__icontains=name)

    fran_list = fran_list.order_by("name")

    return render(request, "main/editor/franchise.html",
                  {"fran_list": fran_list,
                   "name": name,
                   "title": "Choose a franchise"
                   })


@permission_required("main.change_contest", raise_exception=True)
@permission_required("main.change_fight", raise_exception=True)
@permission_required("main.add_fight", raise_exception=True)
def edt_contest_view(request, contest_id):
    try:
        contest = Contest.objects.get(pk=contest_id)
    except Contest.DoesNotExist:
        raise Http404
    fights = Fight.objects.filter(contest=contest).order_by("number")
    registrations = contest.registration_set.all()
    other_contests = Contest.objects.filter(event=contest.event).exclude(pk=contest_id)

    def move_to_contest(fight, target_contest):
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
                # Create a permanent fight record that does not change when fights are removed from the contest
                # prevents indexoutofbound
                fight_dict[i] = fights[i]
            for i in range(len(fight_dict)):
                if int(request.POST["fight-" + str(i)]) != contest_id:
                    if "recursive-" + str(i) in request.POST.keys():
                        versions_checked = []
                        versions_to_check = [fv.version for fv in Fight_Version.objects.filter(fight=fight_dict[i])]
                        fights_to_move = [fight_dict[i]]
                        while len(versions_to_check) > 0:
                            v = versions_to_check.pop()
                            fights_to_check = Fight.objects.filter(contest=contest, fight_version__version=v).exclude(
                                fight_version__version__in=versions_checked).exclude(
                                fight_version__version__in=versions_to_check)
                            for fight in fights_to_check:
                                fights_to_move.append(fight)
                                for fv in fight.fight_version_set.all().exclude(version=v):
                                    if fv.version not in versions_to_check and fv.version not in versions_checked:
                                        versions_to_check.append(fv.version)
                            versions_checked.append(v)
                        for fight in fights_to_move:
                            move_to_contest(fight, Contest.objects.get(pk=request.POST["fight-" + str(i)]))

                    else:
                        move_to_contest(fight_dict[i], Contest.objects.get(pk=request.POST["fight-" + str(i)]))
        elif request.POST["save"] == "prune":
            versions = Version.objects.filter(fight_version__fight__contest=contest).distinct()
            Registration.objects.filter(contest=contest).exclude(version__in=versions).delete()
            i = 1
            for f in fights:
                f.number = i
                i += 1
            Fight.objects.bulk_update(fights, ["number"])
        elif request.POST["save"] == "reorder":
            fight_update_list = []
            for value in request.POST:
                if value[0] == "n":
                    fight = Fight.objects.get(id=value[7:])
                    new_fight_number = int(request.POST[value])
                    if fight.number != new_fight_number:
                        if Fight.objects.filter(contest=fight.contest, number=new_fight_number).count() > 0:
                            higher_fights = Fight.objects.filter(contest=fight.contest, number__gte=new_fight_number)
                            for f in higher_fights:
                                f.number += 1
                            Fight.objects.bulk_update(higher_fights, ['number'])
                        fight.number = new_fight_number
                        fight_update_list.append(fight)

            Fight.objects.bulk_update(fight_update_list, ['number'])
    return render(request, "main/editor/contest.html",
                  {"contest": contest, "other_contests": other_contests, "fights": fights,
                   "applications": registrations, "title": "edt" + str(contest)})


@permission_required("main.change_fight", raise_exception=True)
def edt_fight_view(request, fight_id):
    try:
        fight = Fight.objects.get(pk=fight_id)
    except Fight.DoesNotExist:
        raise Http404
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
                for fv in fight.fight_version_set.all():
                    fv.version.update_fought_range(fight.contest)
                    Leaderboard.update_robot_weight_class(fv.version.robot)  # TODO: See if we need to do this
                fight.calculate(commit=True)
                response = redirect("main:edtContest", fight.contest.id)
                response.delete_cookie("editing_fight")
            else:
                response = redirect("main:edtFightOverview", fight_id)
                response.delete_cookie("editing_fight")
        else:
            response = render(request, "main/editor/fight.html",
                              {"form": form, "has_winner": has_winner, "fight": fight, "title": "edt" + str(fight), })
            response.set_cookie("editing_fight", fight_id, ONE_HOUR_TIMER)
    else:
        if fight.fight_version_set.count() == 0:
            response = redirect('main:newFightVersion', fight_id)
            response.set_cookie("editing_fight", fight_id, ONE_HOUR_TIMER)
        else:
            form = FightForm(instance=fight)
            response = render(request, "main/editor/fight.html",
                              {"form": form, "has_winner": has_winner, "fight": fight, "title": "edt" + str(fight), })
            response.set_cookie("editing_fight", fight_id, ONE_HOUR_TIMER)
    return response


@permission_required("main.change_fight", raise_exception=True)
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
            robot_list.filter(latin_name__icontains=name)).union(
            robot_list.filter(version__latin_robot_name__icontains=name)).union(
            robot_list.filter(version__team__name__icontains=name))

    robot_list = robot_list.order_by("name")
    num = 50
    results = len(robot_list)
    robot_list = robot_list[num * (page - 1):num * page]

    return render(request, "main/editor/select_robot.html",
                  {"robot_list": robot_list,
                   "name": name, "obj_id": obj_id, "obj_type": obj_type, "page": page,
                   "pages": results // num if results % num == 0 else results // num + 1, "title": "Choose Robot",
                   })


@permission_required("main.change_version", raise_exception=True)
@permission_required("main.change_team", raise_exception=True)
@permission_required("main.change_robot", raise_exception=True)
def edt_team_view(request, team_id):
    try:
        team = Team.objects.get(pk=team_id)
    except Team.DoesNotExist:
        raise Http404
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
                           fight_id != 0, "title": "edt" + str(team), })
    response.set_cookie("editing_team", team_id, ONE_HOUR_TIMER)
    return response


@permission_required("main.change_team", raise_exception=True)
@permission_required("main.add_version", raise_exception=True)
@permission_required("main.add_robot", raise_exception=True)
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
                   "pages": results // num if results % num == 0 else results // num + 1,
                   "title": "Select Team",
                   })


@permission_required("main.change_fight", raise_exception=True)
@permission_required("main.change_team", raise_exception=True)
@permission_required("main.change_version", raise_exception=True)
@permission_required("main.change_robot", raise_exception=True)
def edt_select_version_view(request, robot_id):
    robot = Robot.objects.get(id=robot_id)
    if request.COOKIES.get("editing_team"):
        obj_type = "team"
        obj_id = request.COOKIES.get("editing_team")
    else:
        obj_type = "fight"
        obj_id = request.COOKIES.get("editing_fight")
    return render(request, "main/editor/select_version.html",
                  {"robot": robot, "obj_type": obj_type, "obj_id": obj_id, "title": "Select Version", })


@permission_required("main.change_fight", raise_exception=True)
@permission_required("main.change_version", raise_exception=True)
@permission_required("main.change_robot", raise_exception=True)
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


@permission_required("main.delete_person", raise_exception=True)
@permission_required("main.delete_team", raise_exception=True)
@permission_required("main.delete_weight_class", raise_exception=True)
@permission_required("main.delete_robot", raise_exception=True)
@permission_required("main.delete_version", raise_exception=True)
@permission_required("main.delete_franchise", raise_exception=True)
@permission_required("main.delete_location", raise_exception=True)
@permission_required("main.delete_event", raise_exception=True)
@permission_required("main.delete_contest", raise_exception=True)
@permission_required("main.delete_registration", raise_exception=True)
@permission_required("main.delete_fight", raise_exception=True)
@permission_required("main.delete_award", raise_exception=True)
@permission_required("main.delete_person_team", raise_exception=True)
@permission_required("main.delete_person_franchise", raise_exception=True)
@permission_required("main.delete_fight_version", raise_exception=True)
@permission_required("main.delete_leaderboard", raise_exception=True)
@permission_required("main.delete_web_link", raise_exception=True)
@permission_required("main.delete_source", raise_exception=True)
@permission_required("main.delete_hallofame", raise_exception=True)
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
    elif model == "source":
        instance = Source.objects.get(pk=instance_id)
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
                      {"instance": instance, "model": model, "next_id": next_id, "redirect": redir,
                       "title": "Delete " + str(instance)})


def index_view(request):
    editor_stay = request.GET.get("edt") or ""
    if request.user.is_authenticated and request.user.is_superuser and editor_stay != "stay":
        return redirect("main:edtHome")

    events = ["steel-conflict-1", "robot-wars-uk-open", "robot-wars-the-first-wars", "battlebots-1-point-0",
              "mechwars-iii", "robotica-season-1"]
    robot = Robot.objects.filter(hallofame__full_member=True).order_by("?")[0]
    event = Event.objects.get(slug=random.choice(events))
    return render(request, "main/index.html", {"example_robot": robot, "example_event": event})


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

    countries_list = Event.objects.values("country").distinct()
    countries = []
    for country in countries_list:
        countries.append((country["country"], pycountry.countries.get(alpha_2=country["country"]).name))
    countries.sort(key=lambda x: x[1])
    countries = [("", "")] + countries

    event_list = event_list.order_by("name").order_by("start_date")
    results = len(event_list)
    event_list = event_list[num * (page - 1):num * page]
    if len(event_list) > 0:
        description = "List of robot combat events " + timespan(event_list[0].start_date,
                                                                event_list[-1].end_date, True) + "."
    else:
        description = "Search for robot combat events returned no results."

    return render(request, "main/event_index.html",
                  {"event_list": event_list,
                   "page": page,
                   "pages": results // num if results % num == 0 else results // num + 1,
                   "weights": [(0, "")] + Weight_Class.LEADERBOARD_VALID,
                   "countries": countries,
                   "chosen_country": country_code,
                   "chosen_weight": weight,
                   "name": name,
                   "distance": distance,
                   "date_from": date_from,
                   "date_to": date_to,
                   "past": past,
                   "title": "Events",
                   "description": description,
                   "url": reverse("main:eventIndex"),
                   })


def event_detail_view(request, slug):
    try:
        event = Event.objects.get(slug=slug)
    except Event.DoesNotExist:
        raise Http404

    fran = event.franchise
    contests = Contest.objects.filter(event=event).order_by("start_date","-weight_class__weight_grams")
    num_competitors = Version.objects.filter(registration__contest__in=contests).distinct().count()
    if request.user.is_authenticated:
        can_change = fran.can_edit(request.user)
    else:
        can_change = False
    return render(request, "main/event_detail.html",
                  {"event": event,
                   "contests": contests,
                   "can_change": can_change,

                   "title": event.name,
                   "description": "Information about " + str(event) + ", an event organised by " + str(
                       event.franchise) + " " + event.timespan(True) + " with " + str(
                       num_competitors) + " robots competing.",
                   "thumbnail": event.logo.url if event.logo else (
                       event.franchise.logo.url if event.franchise.logo else None),
                   "url": reverse("main:eventDetail", args=[event.slug]),
                   })


@permission_required("main.add_event", raise_exception=True)  # TODO: FORMS
def new_event_view(request, franchise_id):
    fran = Franchise.objects.get(pk=franchise_id)
    can_change = fran.can_edit(request.user)
    if not can_change:
        return redirect("%s?m=%s" % (
            reverse("main:message"), "You do not have permission to create a new event for this franchise."))
    if request.method == "POST":
        form = EventForm(request.POST, request.FILES)
        if form.is_valid():
            event = form.save(commit=False)
            event.franchise = fran
            event.make_slug()
            event.save()
            return redirect("main:edtEvent", event.id)
    else:
        form = EventForm()
    return render(request, "main/new_event.html", {"form": form, "fran": fran, "title": "New Event"})


@permission_required("main.change_event", raise_exception=True)
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
    return render(request, "main/forms/generic.html", {"form": form, "title": "Edit " + str(event), "has_image": True,
                                                       "next_url": reverse("main:editEvent", args=[event_id])})


def contest_detail_view(request, contest_id):
    try:
        contest = Contest.objects.get(pk=contest_id)
    except Contest.DoesNotExist:
        raise Http404
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
                   "applied": applied, "approved": approved, "reserve": reserve, "app_ver": app_ver,

                   "title": str(contest) + ": " + contest.event.name,
                   "description": "Overview of the fights and competitors at the " + contest.name + " at " + contest.event.name,
                   "url": reverse("main:contestDetail", args=[contest_id]),
                   })


@permission_required("main.add_contest", raise_exception=True)
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
            if contest.end_date > event.end_date:
                event.end_date = contest.end_date
                event.save()
            contest.save()
            return redirect("main:edtEvent", event.id)
    else:
        form = ContestForm()
        form.fields["start_date"].initial = event.start_date
        form.fields["end_date"].initial = event.end_date
    return render(request, "main/forms/generic.html", {"form": form, "title": "New Contest",
                                                       "next_url": reverse("main:newContest", args=[event_id])})


@permission_required("main.change_contest", raise_exception=True)
def edit_contest_view(request, contest_id):
    contest = Contest.objects.get(pk=contest_id)
    can_change = contest.can_edit(request.user)
    if not can_change:
        return redirect("%s?m=%s" % (reverse("main:message"), "You do not have permission to edit this contest."))
    if request.method == "POST":
        form = ContestForm(request.POST, instance=contest)
        if form.is_valid():
            if contest.end_date > contest.event.end_date:
                contest.event.end_date = contest.end_date
                contest.event.save()
            form.save()
            return redirect("main:edtContest", contest.id)
    else:
        form = ContestForm(instance=contest)
    return render(request, "main/forms/generic.html", {"form": form, "title": "Edit Contest",
                                                       "next_url": reverse("main:editContest", args=[contest_id])})


@permission_required("main.change_contest", raise_exception=True)
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

    if weapon != "" and weapon is not None:
        robot_list = robot_list.filter(version__weapon_type__icontains=weapon).distinct()

    if name != "" and name is not None:  # union must be last.
        robot_list = robot_list.filter(name__icontains=name).union(
            robot_list.filter(version__robot_name__icontains=name)).union(
            robot_list.filter(latin_name__icontains=name)).union(
            robot_list.filter(version__latin_robot_name__icontains=name))

    if has_awards == "on":
        bad = []
        for robot in robot_list:
            if len(robot.awards()) == 0:
                bad.append(robot.id)
        robot_list = robot_list.exclude(id__in=bad)

    robot_list = robot_list.order_by("name")
    results = len(robot_list)
    robot_list = robot_list[num * (page - 1):num * page]

    countries_list = Robot.objects.values("country").distinct()
    countries = []
    for country in countries_list:
        if country["country"] in ["XE", "XS", "XW", "XI", "XX"]:
            pass
        else:
            countries.append((country["country"], pycountry.countries.get(alpha_2=country["country"]).name))
    countries.extend([('XE', "England"), ('XS', "Scotland"), ('XW', "Wales"), ('XI', "Northern Ireland")])
    countries.sort(key=lambda x: x[1])
    countries = [("", "")] + countries

    return render(request, "main/robot_index.html",
                  {"robot_list": robot_list,
                   "page": page,
                   "pages": results // num if results % num == 0 else results // num + 1,
                   "weights": [(0, "")] + Weight_Class.LEADERBOARD_VALID,
                   "countries": countries,
                   "chosen_country": country_code,
                   "chosen_weight": weight,
                   "name": name,
                   "has_awards": has_awards,
                   "weapon": weapon,

                   "title": "Robots",
                   "description": ("A list of combat robots in alphabetical order from " + robot_list[
                       0].name + " to " + robot_list[-1].name + ".") if len(robot_list) > 1 else "",
                   "url": reverse("main:robotIndex"),
                   })


def leaderboard(request):
    visible_weights = [
        ("F", "Featherweight"),
        ("L", "Lightweight"),
        ("M", "Middleweight"),
        ("H", "Heavyweight"),
        ("S", "Super Heavyweight"),
    ]

    # CSS Notes: row height up to 20em
    weight = request.GET.get("weight")
    # Decision made to hide the basically
    if not weight or weight not in [x[0] for x in visible_weights]:  # LEADERBOARD_WEIGHTS]:
        weight = "H"
    year = request.GET.get("year")
    current_year = Event.objects.all().order_by("-end_date")[0].end_date.year
    if weight == "F":
        years = [1996, 1997]  # TODO: if weight class changes are in place add 1995
    else:
        years = [x['year'] for x in
                 Leaderboard.objects.filter(weight=weight).order_by("year").values("year").distinct()]
    # years = [x for x in range(1994, current_year + 1)]
    try:
        year = int(year)
    except (ValueError, TypeError):
        year = current_year
    if not years:
        years = [current_year]
    if year not in years:
        year = current_year
    if weight != "F":
        Leaderboard.update_class(weight)
        # pass

    robot_list = Leaderboard.objects.filter(weight=weight, year=year, position__lte=100).order_by("-ranking")

    if year == current_year and robot_list.count() == 0:
        # Catch to stop the superheavyweight list (or any others that go out of use) from being unreachable in the menu
        year = years[-1]
        robot_list = Leaderboard.objects.filter(weight=weight, year=year, position__lte=100).order_by("-ranking")

    eliminations = Leaderboard.objects.filter(weight=weight, year=year, position=101).order_by("difference")

    top_three = []
    for i in range(robot_list.count() if robot_list.count() < 3 else 3):
        top_three.append(robot_list[i])

    chosen_weight_text = {"F": "featherweight", "L": "lightweight", "M": "middleweight", "H": "heavyweight",
                                     "S": "super heavyweight"}[weight]

    return render(request, "main/robot_leaderboard.html",
                  {"robot_list": robot_list,
                   "weights": visible_weights,
                   "chosen_weight": weight,
                   "chosen_weight_text": chosen_weight_text,
                   "chosen_year": year,
                   "first_year": not Leaderboard.objects.filter(weight=weight, year=year - 1).exists(),
                   "years": years,
                   "top_three": top_three,
                   "is_this_year": year == current_year,
                   "low_classes": ["A", "U", "B", "Y", "F"],
                   "eliminations": eliminations,

                   "title": "Leaderboard",
                   "description": "Leaderboard of " + chosen_weight_text + " fighting robots in the year " + str(
                       year) + ".",
                   "thumbnail": top_three[0].version.image.url,
                   "url": reverse("main:leaderboard") + "?weight=" + weight + "&year=" + str(year),
                   })


def robot_detail_view(request, slug):
    try:
        r = Robot.objects.get(slug=slug)
    except Robot.DoesNotExist:
        raise Http404

    v = None
    is_random = False

    if request.user.is_authenticated:
        can_change = r.can_edit(request.user)
    else:
        can_change = False

    if request.method == "GET":
        version_id = request.GET.get("v")
        is_random = request.GET.get("source") == "random"
        try:
            version_id = int(version_id)
            v = Version.objects.get(pk=version_id)
        except (ValueError, TypeError, ObjectDoesNotExist):
            v = None
    fights = Fight.objects.filter(competitors__robot=r).order_by("contest__start_date", "contest__id", "number")
    awards = Award.objects.filter(version__robot=r)

    leaderboard_entries = Leaderboard.objects.filter(robot=r, ranking__gt=Robot.RANKING_DEFAULT).order_by("position",
                                                                                                          "-year")
    best_lb_entry = leaderboard_entries.first()
    current_lb_entry = leaderboard_entries.order_by(
        "-year").first() if leaderboard_entries.first() and leaderboard_entries.order_by("-year").first().year == \
                            Leaderboard.objects.all().order_by("-year")[0].year else None
    if leaderboard_entries.count() > 1:
        leaderboard_entries = leaderboard_entries[1:]
    else:
        leaderboard_entries = None

    # Calculate rowspans for fight table
    contests_attended = Contest.objects.filter(fight__fight_version__version__robot=r).order_by("start_date",
                                                                                                "id").distinct()
    rowspans_unformatted = []
    previous_contest = None
    for c in contests_attended:
        if previous_contest is not None and previous_contest.event == c.event:
            rowspans_unformatted[-1] += fights.filter(contest=c).count()  # TODO: is this the fastest way to do this?
        else:
            rowspans_unformatted.append(fights.filter(contest=c).count())
        previous_contest = c

    rowspans = []
    for length in rowspans_unformatted:
        rowspans.append(length)
        rowspans += [0] * (length - 1)

    fights_tuple = [(rowspans[i], fights[i]) for i in range(len(fights))]

    description = "Information about " + str(r) + ", a combat robot that has fought " + str(fights.count()) + \
                  " fight" + ("" if fights.count() == 1 else "s") + " " + r.timespan(True) + "."
    if r.wins > 0 or r.losses > 0:
        description += " Winning " + str(r.wins) + " and losing " + str(r.losses) + " in head to head battle."

    return render(request, "main/robot_detail.html",
                  {"robot": r,
                   "fights_tuple": fights_tuple,
                   "awards": awards,
                   "ver": v,
                   "can_change": can_change,
                   "version_set": r.version_set.all().order_by("number"),
                   "best_lb_entry": best_lb_entry,
                   "leaderboard_entries": leaderboard_entries,
                   "current_lb_entry": current_lb_entry,
                   "is_random": is_random,
                   "missing_brackets_flag": True if fights.filter(
                       contest__event__missing_brackets=True).exists() else False,
                   "title": r.name,
                   "description": description,
                   "thumbnail": v.image.url if v and v.image else None if v else r.get_image() if r.get_image != settings.STATIC_URL + "unknown.png" else None,
                   "url": reverse("main:robotDetail", args=[r.slug]),
                   })


def random_robot_view(unused):
    random_robot = Robot.objects.all().order_by("?")[0]
    flag = True
    while flag:
        for version in random_robot.version_set.all():
            if version.image:
                flag = False
        if flag:
            random_robot = Robot.objects.all().order_by("?")[0]
    version = random_robot.version_set.all().order_by("?")[0]
    while version.image is None:
        version = random_robot.version_set.all().order_by("?")[0]
    return redirect("%s?v=%d&source=random" % (reverse("main:robotDetail", args=[random_robot.slug]), version.id))


@permission_required("main.change_robot", raise_exception=True)
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


@permission_required("main.change_version", raise_exception=True)
@permission_required("main.change_robot", raise_exception=True)
@permission_required("main.change_team", raise_exception=True)
def version_edit_view(request, version_id):  # TODO: MASSIVE NEEDS TO BE DONE RIGHT HERE
    fight_id = request.COOKIES.get("editing_fight")  # If not 0, is editor.
    team_id = request.GET.get("team_id")  # TODO: FORM
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
                                                                    "fight_id": fight_id, "team_id": team_id,
                                                                    "title": "Edit" + str(version)})
            response.set_cookie("editing_version", version.id, ONE_HOUR_TIMER)
    else:
        form = VersionForm(instance=version)
        response = render(request, "main/modify_version.html",
                          {"form": form, "version": version, "new": False, "fight_id": fight_id, "team_id": team_id,
                           "title": "Edit" + str(version)})
        response.set_cookie("editing_version", version.id, ONE_HOUR_TIMER)
    return response


@permission_required("main.add_version", raise_exception=True)
@permission_required("main.change_team", raise_exception=True)
@permission_required("main.change_robot", raise_exception=True)
def new_version_view(request, robot_id):  # TODO: FORM
    fight_id = request.COOKIES.get("editing_fight")  # If not 0, is editor.
    team_id = request.GET.get("team_id")
    try:
        team_id = int(team_id)
    except (ValueError, TypeError):
        team_id = 0
    if not fight_id:
        fight_id = 0

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
                              {"form": form, "robot": robot, "new": True, "fight_id": fight_id, "team_id": team_id,
                               "title": "Add new version to " + str(robot)})
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
                          {"form": form, "robot": robot, "new": True, "fight_id": fight_id, "team_id": team_id,
                           "title": "Add new version to " + str(robot)})
        response.set_cookie("robot_or_version", "version", ONE_HOUR_TIMER)
        response.set_cookie("rv_id", robot_id, ONE_HOUR_TIMER)
    return response


def team_detail_view(request, slug):
    try:
        team = Team.objects.get(slug=slug)
    except Team.DoesNotExist:
        raise Http404
    if request.user.is_authenticated:
        can_change = team.can_edit(request.user)
    else:
        can_change = False
    robots = team.owned_robots().order_by("-last_fought")
    loaners = team.loaners().order_by("-last_fought")

    return render(request, "main/team_detail.html",
                  {"team": team, "robots": robots, "loaners": loaners, "can_change": can_change,

                   "title": team,
                   "description": "Overview of " + str(team) + ", a robot combat team that built " + str(
                       robots.count()) + " robots " + team.timespan(True) + ".",
                   "thumbnail": team.logo.url if team.logo else None,
                   "url": reverse("main:teamDetail", args=[slug]),
                   })


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

    countries_list = Team.objects.values("country").distinct()
    countries = []
    for country in countries_list:
        if country["country"] in ["XE", "XS", "XW", "XI", "XX"]:
            continue
        countries.append((country["country"], pycountry.countries.get(alpha_2=country["country"]).name))
    countries.extend([('XE', "England"), ('XS', "Scotland"), ('XW', "Wales"), ('XI', "Northern Ireland")])
    countries.sort(key=lambda x: x[1])
    countries = [("", "")] + countries

    team_list = team_list.order_by("name")
    results = len(team_list)
    team_list = team_list[num * (page - 1):num * page]
    if results > 0:
        description = "A list of robot combat teams in alphabetical order from " + team_list[
            0].name + " to " + team_list[-1].name + "."
    else:
        description = "Search for robot combat teams returned no results."
    return render(request, "main/team_index.html",
                  {"team_list": team_list,
                   "page": page,
                   "pages": results // num if results % num == 0 else results // num + 1,
                   "countries": countries,
                   "chosen_country": country_code,
                   "name": name,

                   "title": "Teams",
                   "description": description,
                   "url": reverse("main:teamIndex"),
                   })


@permission_required("main.add_robot", raise_exception=True)
@permission_required("main.add_version", raise_exception=True)
@permission_required("main.change_team", raise_exception=True)
def new_robot_view(request):  # TODO: FORM
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
            form.fields["country"].initial = Fight.objects.get(id=fight_id).contest.event.country
        if team_id:
            form.fields['country'].initial = team.country
        response = render(request, "main/new_robot.html", {"form": form, "team": team, "fight_id": fight_id})
        response.set_cookie("robot_or_version", "robot", ONE_HOUR_TIMER)
    return response


def version_detail_view(request, version_id):
    try:
        v = Version.objects.get(pk=version_id)
    except Version.DoesNotExist:
        raise Http404
    robot_slug = v.robot.slug
    return redirect("%s?v=%d" % (reverse("main:robotDetail", args=[robot_slug]), version_id))


@permission_required("main.change_team", raise_exception=True)
@permission_required("main.add_team", raise_exception=True)
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


@permission_required("main.add_franchise", raise_exception=True)
@permission_required("main.change_franchise", raise_exception=True)
def franchise_modify_view(request, franchise_id=None):
    redir = request.GET.get("redirect")
    if redir is None:
        redir = ""

    if request.method == "POST":
        if franchise_id is None:
            form = FranchiseForm(request.POST, request.FILES)
            old_logo = ""
        else:
            franchise = Franchise.objects.get(pk=franchise_id)
            form = FranchiseForm(request.POST, request.FILES, instance=franchise)
            old_logo = franchise.logo

        if form.is_valid():
            new = form.save()
            if franchise_id is None:
                new.make_slug(save=True)
                franchise_id = new.id
            else:
                if old_logo and new.logo != old_logo:
                    event_logo_dir = "event_logos/" + str(datetime.date.today().year)
                    if not isdir(settings.MEDIA_URL[1:] + event_logo_dir):
                        new.logo = old_logo
                        new.save()
                        raise Exception
                    else:
                        new_events_logo = event_logo_dir + "/" + old_logo.url.split("/")[-1]
                        copy2(old_logo.url[1:], settings.MEDIA_URL[1:] + new_events_logo)
                        Event.objects.filter(franchise__id=franchise.id, logo="").update(logo=new_events_logo)

            franchise = new
            web_links = franchise.web_link_set.all()
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
                    wb.franchise = franchise
                    wb.save()
                except ValidationError:
                    pass

            if request.POST["save"] == "continue":
                if redir == "":
                    return redirect(reverse("main:franchiseDetail", args=[franchise.slug]))
                elif redir == "/editor/newEvent":
                    return redirect("%s?franchise=%s" % (reverse("main:edtNewEvent"), franchise_id))

    if franchise_id is None:
        form = FranchiseForm()
        return render(request, "main/forms/franchise.html",
                      {"form": form, "title": "New Franchise", "has_image": True, "franchise": None,
                       "next_url": reverse("main:newFranchise") + "?redirect=" + str(redir)})
    else:
        franchise = Franchise.objects.get(pk=franchise_id)
        form = FranchiseForm(instance=franchise)
        return render(request, "main/forms/franchise.html",
                      {"form": form, "title": "Edit Franchise", "has_image": True, "franchise": franchise,
                       "next_url": reverse("main:editFranchise", args=[franchise_id]) + "?redirect=" + redir})


def franchise_detail_view(request, slug):
    try:
        fran = Franchise.objects.get(slug=slug)
    except Franchise.DoesNotExist:
        raise Http404
    events = fran.event_set.all().order_by("start_date")
    return render(request, "main/franchise_detail.html",
                  {"fran": fran, "events": events, "leave_id": 1,  # TODO: lol
                   "title": fran,
                   "description": "Information about " + fran.name + ", a robot combat event organiser who organised " + str(
                       events.count()) + " event" + ("" if events.count == 1 else "s") + " " + fran.timespan(
                       True) + ".",
                   "thumbnail": fran.logo.url if fran.logo else None,
                   "url": reverse("main:franchiseDetail", args=[fran.slug]),
                   "can_edit": fran.can_edit(request.user)
                   })


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

                   "title": "Franchises",
                   "description": "A list of robot combat franchises in alphabetical order from " + fran_list[
                       0].name + " to " + fran_list[-1].name + ".",
                   "url": reverse("main:franchiseIndex"),
                   })


@permission_required("main.add_fight", raise_exception=True)
@permission_required("main.change_contest", raise_exception=True)
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


@permission_required("main.change_fight", raise_exception=True)
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
                      {"form": form, "title": "Edit Fight", "has_image": True,
                       "next_url": reverse("main:editJustFight", args=[fight_id])})


def fight_detail_view(request, fight_id):  # TODO: Sort this better
    try:
        fight = Fight.objects.get(pk=fight_id)
    except Fight.DoesNotExist:
        raise Http404
    if request.user.is_authenticated:
        can_change = fight.can_edit(request.user)
    else:
        can_change = False

    next_fight = previous_fight = None
    if Fight.objects.filter(contest=fight.contest, number__gt=fight.number).exists():
        next_fight = Fight.objects.filter(contest=fight.contest, number__gt=fight.number).order_by("number")[0]
    if Fight.objects.filter(contest=fight.contest, number__lt=fight.number).exists():
        previous_fight = Fight.objects.filter(contest=fight.contest, number__lt=fight.number).order_by("-number")[0]
    return render(request, "main/fight_detail.html", {"fight": fight, "can_change": can_change,
                                                      "next_fight": next_fight, "previous_fight": previous_fight,

                                                      "title": fight.non_latin_name,
                                                      "description": (
                                                                         "Image of " if fight.media_type == "LI" or fight.media_type == "EI" else (
                                                                             "Video of " if fight.media_type != "XX" and fight.media_type != "UN" else "Overview of ")) + str(
                                                          fight) + ". A " + (
                                                                         "round of " if fight.fight_type == "NC" else "fight at ") + "the " + str(
                                                          fight.contest) + " contest at " + str(
                                                          fight.contest.event) + ".",
                                                      "thumbnail": fight.internal_media.url if fight.media_type == "LI" else (
                                                          fight.external_media if fight.media_type == "EI" else None),
                                                      "url": reverse("main:fightDetail", args=[fight_id]),
                                                      "type": "video.other" if fight.media_type in ["LV", "IF", "TW",
                                                                                                    "IG", "TT",
                                                                                                    "FB"] else None,
                                                      })


@permission_required("main.change_fight", raise_exception=True)
def modify_fight_version_view(request, fight_id, vf_id=None):  # TODO SHIFT FORM
    # editor = request.GET.get("editor") or ""
    editor = request.COOKIES.get("editing_fight") is not None and request.COOKIES.get("editing_fight") != ""
    fight = Fight.objects.get(pk=fight_id)
    # editor = editor.lower() == "true"

    can_change = fight.can_edit(request.user)
    if not can_change:
        return redirect("%s?m=%s" % (reverse("main:message"), "You do not have permission to edit this fight."))

    registered = Version.objects.filter(registration__contest=fight.contest.id).annotate(alphabetical=Case(
        When(robot_name="",
             then=Case(
                 When(robot__display_latin_name=True, then=F("robot__latin_name")), default=F("robot__name")),
             ),
        default=Case(
            When(display_latin_name=True, then=F("latin_robot_name")), default=F("robot_name")
        )
    ))
    registered = registered.order_by("alphabetical")

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
        form.fields['version'].choices = [(None, "----------")] + [(v.id, v.english_readable_name) for v in registered]
        response = render(request, "main/modify_fight_version.html",
                          {"form": form, "fight_id": fight_id, "fight_version_id": vf_id, "editor": editor,
                           "title": "Modify Fight Version"})

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
    return render(request, "main/award_index.html", {"award_list": awards, "event": event, "can_change": can_change,
                                                     "title": str(event) + ": Awards - Robot Combat Archive",
                                                     "description": "List of awards given out to robots at " + str(
                                                         event),
                                                     "thumbnail": settings.STATIC_URL + "awards/trophy_gold.png",
                                                     "url": reverse("main:awardIndex", args=[event_slug]),
                                                     })


@permission_required("main.change_contest", raise_exception=True)
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
            return redirect("main:edtEvent", event.id)
    else:
        form = AwardForm()
        form.fields['contest'].queryset = Contest.objects.filter(event=event)
        registered = Version.objects.filter(registration__contest__in=event.contest_set.all()).annotate(
            alphabetical=Case(
                When(robot_name="",
                     then=Case(
                         When(robot__display_latin_name=True, then=F("robot__latin_name")), default=F("robot__name")),
                     ),
                default=Case(
                    When(display_latin_name=True, then=F("latin_robot_name")), default=F("robot_name")
                )
            ))
        registered = registered.order_by("alphabetical").distinct()
        form.fields['version'].choices = [(None, "----------")] + [(v.id, v.english_readable_name) for v in registered]
        return render(request, "main/forms/generic.html",
                      {"form": form, "title": "New Award", "next_url": reverse("main:newAward", args=[event_id])})


# TODO: THis is almost identical to edit award should probably make a more generic one esp the template

@permission_required("main.change_contest", raise_exception=True)
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
        registered = Version.objects.filter(registration__contest__in=a.event.contest_set.all()).annotate(
            alphabetical=Case(
                When(robot_name="",
                     then=Case(
                         When(robot__display_latin_name=True, then=F("robot__latin_name")), default=F("robot__name")),
                     ),
                default=Case(
                    When(display_latin_name=True, then=F("latin_robot_name")), default=F("robot_name")
                )
            ))
        registered = registered.order_by("alphabetical").distinct()
        form.fields['version'].choices = [(None, "----------")] + [(v.id, v.english_readable_name) for v in registered]
        return render(request, "main/forms/generic.html",
                      {"form": form, "title": "Edit Award", "next_url": reverse("main:editAward", args=[award_id])})


@permission_required("main.change_person", raise_exception=True)
@permission_required("main.add_person", raise_exception=True)
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
    return render(request, "main/forms/generic.html",
                  {"form": form, "title": "Edit Person", "next_url": reverse("main:editPerson", args=[person_id])})


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
            Robot.objects.filter(version__robot_name__icontains=search_term)).union(
            Robot.objects.filter(latin_name__icontains=search_term)).union(
            Robot.objects.filter(version__latin_robot_name__icontains=search_term))
        robot_len = len(robots)
        robots = robots[:10]
        events = Event.objects.filter(name__icontains=search_term).union(
            Event.objects.filter(contest__name__icontains=search_term))
        event_len = len(events)
        events = events[:10]

    if fran_len + team_len + robot_len + event_len == 1:
        redir = None
        if fran_len == 1:
            redir = redirect("main:franchiseDetail", franchises[0].slug)
        elif team_len == 1:
            redir = redirect("main:teamDetail", teams[0].slug)
        elif robot_len == 1:
            redir = redirect("main:robotDetail", robots[0].slug)
        elif event_len == 1:
            redir = redirect("main:eventDetail", events[0].slug)
        return redir
    else:
        return render(request, "main/search.html",
                      {"events": events, "robots": robots, "teams": teams, "franchises": franchises,
                       "search_term": search_term, "fran_len": fran_len, "event_len": event_len, "robot_len": robot_len,
                       "team_len": team_len,

                       "title": '"' + search_term + '"',
                       "description": "Search results for: " + search_term,
                       "url": reverse("main:search"),
                       })


@permission_required("main.add_weight_class", raise_exception=True)
def new_weight_class_view(request, return_id):
    if request.method == "POST":
        form = WeightClassForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("main:newContest", return_id)
    else:
        form = WeightClassForm()
    return render(request, "main/forms/generic.html", {"form": form, "title": "New Weight Class",
                                                       "next_url": reverse("main:newWeightClass", args=[return_id])})


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


@permission_required("main.change_team", raise_exception=True)
@permission_required("main.change_franchise", raise_exception=True)
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


@permission_required("main.change_robot", raise_exception=True)
@permission_required("main.change_version", raise_exception=True)
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
            new_version = robot.last_version()
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
    return render(request, "main/hall_of_fame.html", {"members": members, "honoraries": honoraries,
                                                      "title": "Hall of Fame",
                                                      "description": "All robots on the robot combat archive that also appear on RunAmok's Hall of Fame.",
                                                      "thumbnail": "/media/team_logos/2022/newhotcoin1.png",
                                                      "url": reverse("main:hallOfFame"),
                                                      })


def credits_view(request):
    random_country = "XX"
    while random_country == "XX":
        random_country = random.choice(COUNTRY_CHOICES)[0]
    google_icon_choices = ["home", "query_stats", "destruction", "favorite", "scale", "hourglass", "gif",
                           "imagesmode", "videocam", "new_label", "where_to_vote", "close", "timer", "wrong_location",
                           "stat_minus_3", "stat_minus_1", "stat_3", "stat_1", "remove"]

    return render(request, "main/credits.html", {
        "flag": get_flag(random_country),
        "trophy": settings.STATIC_URL + "awards/trophy_" + random.choice(["bronze", "silver", "gold"]) + ".png",
        "google_icon": random.choice(google_icon_choices),

        "title": "Credits",
        "description": "Credits for assets used by the Robot Combat Archive.",
        "url": reverse("main:credits"),
    })


def weapon_types_view(request):
    recognised_weapon_types = [
        'Rammer', 'Wedge', 'Thwackbot', 'Meltybrain',
        'Horizontal Spinner', 'Undercutter', 'Overhead Spinner', 'Shell Spinner', 'Ring Spinner',
        'Vertical Spinner', 'Drum Spinner', 'Eggbeater',
        'Propeller Spinner', 'Angled Spinner', 'Articulated Spinner',
        'Axe', 'Horizontal Axe', 'Hammersaw', 'Spear',
        'Lifter', 'Grabber', 'Horizontal Grabber', 'Grabber-Lifter', 'Crusher', 'Horizontal Crusher',
        'Flipper', 'Front-Hinged Flipper', 'Side-Hinged Flipper',
        'Saw', 'Chainsaw', 'Drill',
        'Interchangeable', 'Multibot',
        'Cannon', 'Entanglement', 'Halon Gas'
    ]
    version_dict = {}
    for w in recognised_weapon_types:
        if Version.objects.filter(weapon_type=w).exclude(robot__lb_weight_class="X").count() > 0:
            valid_versions = Version.objects.filter(weapon_type=w).exclude(robot__lb_weight_class="X")
        else:
            valid_versions = Version.objects.filter(weapon_type=w)
        valid_versions = valid_versions.order_by("-robot__ranking", "-number")
        top_5 = []
        done_robots = []
        for v in valid_versions:
            if v.robot in done_robots:
                continue
            most_recent = v.robot.version_set.all().order_by("-number")[0]
            if most_recent.weapon_type == v.weapon_type:
                top_5.append(v)
                if len(top_5) == 5:
                    break
            done_robots.append(v.robot)

        if len(top_5) > 0:
            version_dict[w.replace(" ", "_").replace("-", "_").lower()] = random.choice(top_5)
        else:
            version_dict[w.replace(" ", "_").replace("-", "_").lower()] = valid_versions[0]

    return render(request, "main/weapon_types.html", {"version_dict": version_dict,
                                                      "title": "Weapon Types",
                                                      "description": "Definitions of all weapon types recognised by the robot combat archive.",
                                                      "url": reverse("main:weaponTypes"),
                                                      })


def weight_class_view(unused):
    wc = Weight_Class.objects.all().order_by("weight_grams")

    rename_this = []
    for x in Weight_Class.LEADERBOARD_VALID_GRAMS:
        rename_this.append(
            {
                "value": x,
                "ub": x + 0.21 * x,
                "lb": x - 0.21 * x,
            }
        )

    placement_dict = {}
    for w in wc:
        offset = 0
        for i in range(len(rename_this)):
            if (0 if i == 0 else rename_this[i - 1]["ub"]) <= w.weight_grams < rename_this[i]["lb"]:
                if i == 0:
                    lb = 0
                else:
                    lb = rename_this[i - 1]["ub"]
                ub = rename_this[i]["lb"]
                percentage = (w.weight_grams - lb) / (ub - lb)
                if i == 0:
                    percentage = percentage * 5
                else:
                    percentage = offset + percentage * 2
                break

            offset += 5 if i == 0 else 2 if i != 8 else 0

            if rename_this[i]["lb"] <= w.weight_grams < rename_this[i]["ub"]:
                lb = rename_this[i]["lb"]
                ub = rename_this[i]["ub"]
                percentage = (w.weight_grams - lb) / (ub - lb)
                if i <= 2:
                    percentage = offset + percentage * 7
                else:
                    percentage = offset + percentage * 10
                break

            offset += 7 if i <= 2 else 10

        if percentage in placement_dict:
            placement_dict[percentage].append(w)
        else:
            placement_dict[percentage] = [w]

    return render(unused, "main/weight_class.html", {"weights": placement_dict})


def futures_features_view(request):
    pass


def ranking_system_view(request):
    pass


def calc_test(request):
    test_type = request.GET.get("test") or ""
    results_text = "Before: \n"
    test_fight = "N/A"
    if test_type == "recalculate":
        recalc_all()
        return render(request, "main/editor/calc_test.html",
                      {"fight": "N/A", "test": test_type, "results": "Recalculated Ranks!"})
    if test_type == "tag_team":
        test_fight = Fight.objects.get(pk=1791)
    if test_type == "regular":
        test_fight = Fight.objects.get(pk=2000)  # Hypno-Disc vs Bigger Brother
    if test_type == "rumble":
        test_fight = Fight.objects.get(pk=1991)  # Wild Thing vs S3 vs Spawn Again
    if test_type == "big_rumble":
        test_fight = Fight.objects.get(pk=1358)  # Battlebots 3.0 Lightweight Royal Rumble
    if test_type == "annihilator":
        test_fight = Fight.objects.get(pk=985)  # Northern Annihilator Round 1
    if test_type == "first_round_melee":
        test_fight = Fight.objects.get(pk=7419)
    if test_type == "unbalanced_tag_team":
        test_fight = Fight.objects.get(pk=7057)  # Stinger vs Kan Opener & Thz
    if test_type == "unbalanced_tag_team_2":
        test_fight = Fight.objects.get(pk=4057)

    if test_type != "":
        for fv in test_fight.fight_version_set.all():
            results_text += str(fv.version) + " " + str(fv.version.robot.ranking) + "\n"
        results_text += "\n"

        results = test_fight.calculate(commit=False)

        results_text += "After: \n"
        for i in range(len(results[0])):
            results_text += str(results[1][i]) + " " + str(results[1][i].robot.ranking) + " Change " + str(
                results[0][i].ranking_change) + "\n"

    return render(request, "main/editor/calc_test.html",
                  {"fight": test_fight, "test": test_type, "results": results_text})


def recalc_all():
    start_time = time.time()

    def save_year(year, version_dictionary, robot_dictionary, fvs):
        print("Saving data for year: " + str(year))
        vers = [v for v in version_dictionary.values()]
        robs = [r for r in robot_dictionary.values()]
        Version.objects.bulk_update(vers, ["first_fought", "last_fought"])
        for r in robs:
            Leaderboard.update_robot_weight_class(r, commit=False, year=year)
        Robot.objects.bulk_update(robs, ["ranking", "wins", "losses", "first_fought", "last_fought", "lb_weight_class"])
        Fight_Version.objects.bulk_update(fvs, ["ranking_change"])

        '''for rob in robs: # Test to ensure that the sum of rank changes adds up to the same as the robot's ranking
            thingy = Fight_Version.objects.filter(version__robot=rob,
                                                  fight__contest__end_date__lte=datetime.datetime(year,12,31))
            calculated_rank = 1000 + sum([x.ranking_change for x in thingy])
            if abs(rob.ranking - calculated_rank) > 0.0001:
                print(rob)
                print(rob.ranking)
                print(thingy)
                print(1000 + sum([x.ranking_change for x in thingy]))
                raise IndexError'''

        print("Creating Leaderboard for year: " + str(year))
        Leaderboard.update_all(year)

    # Need top update more robots than currently doing to add the X to them
    Robot.objects.all().update(ranking=Robot.RANKING_DEFAULT, wins=0, losses=0, lb_weight_class="X", first_fought=None,
                               last_fought=None)
    Version.objects.all().update(first_fought=None, last_fought=None)
    Fight_Version.objects.all().update(ranking_change=0)

    fights = Fight.objects.all().order_by("contest__start_date", "contest__end_date",
                                          "contest__weight_class__weight_grams", "contest_id", "number")
    version_dictionary = {}
    robot_dictionary = {}
    fvs = []
    contest_cache = None
    for fight in fights:
        if contest_cache != fight.contest:
            if contest_cache is not None:
                for ver in Version.objects.filter(fight__contest=contest_cache):
                    ver = version_dictionary[ver.id]
                    ver.update_fought_range(contest_cache, False)

                if contest_cache.end_date.year != fight.contest.end_date.year:
                    save_year(contest_cache.end_date.year, version_dictionary, robot_dictionary, fvs)
                    version_dictionary = {}
                    robot_dictionary = {}
                    fvs = []
            contest_cache = fight.contest
            print("Saving:", contest_cache, fight.contest.event)

        competitors = []
        for fv in fight.fight_version_set.all():
            # if fv.version.robot.id == 30:
            #    breakpoint()
            if fv.version.id not in version_dictionary.keys():
                version_dictionary[fv.version.id] = fv.version
                if fv.version.robot.id not in robot_dictionary.keys():
                    robot_dictionary[fv.version.robot.id] = fv.version.robot
                else:
                    version_dictionary[fv.version.id].robot = robot_dictionary[fv.version.robot.id]
            competitors.append(version_dictionary[fv.version.id])

        result = fight.calculate(competitors)
        fvs += result[0]

    print("Saving Final Batch")
    for ver in Version.objects.filter(fight__contest=contest_cache):
        ver = version_dictionary[ver.id]
        ver.update_fought_range(contest_cache, False)
    save_year(fight.contest.end_date.year, version_dictionary, robot_dictionary, fvs)
    print("Done!")
    print("Took: " + str(time.time() - start_time) + " seconds.")


# This shouldn't delete any data that is in use but just in case here's some permissions.
@permission_required("main.change_robot", raise_exception=True)
@permission_required("main.change_team", raise_exception=True)
@permission_required("main.change_event", raise_exception=True)
@permission_required("main.change_franchise", raise_exception=True)
@permission_required("main.change_fight", raise_exception=True)
def prune_media(request):
    bad_images = []

    def check_media(used_files, dir):
        cyear = datetime.date.today().year
        for year in range(2022, cyear + 1):
            filenames = listdir(settings.MEDIA_ROOT + "/" + dir + str(year))
            for filename in filenames:
                f = dir + str(year) + "/" + filename
                if f not in used_files:
                    bad_images.append(f)

    robot_images = Version.objects.all().values("image").distinct()
    robot_images = [i['image'] for i in robot_images]
    check_media(robot_images, "robot_images/")

    team_logos = Team.objects.all().values("logo").distinct()
    team_logos = [i['logo'] for i in team_logos]
    check_media(team_logos, "team_logos/")

    franchise_logos = Franchise.objects.all().values("logo").distinct()
    franchise_logos = [i['logo'] for i in franchise_logos]
    check_media(franchise_logos, "franchise_logos/")

    event_logos = Event.objects.all().values("logo").distinct()
    event_logos = [i['logo'] for i in event_logos]
    check_media(event_logos, "event_logos/")

    fight_media = Fight.objects.all().values("internal_media").distinct()
    fight_media = [i['internal_media'] for i in fight_media]
    check_media(fight_media, "fight_media/")

    print("deleting", bad_images)
    for i in bad_images:
        try:
            replace(settings.MEDIA_ROOT + "/" + i, settings.MEDIA_ROOT + "/deleted/" + i)
        except:
            dir = settings.MEDIA_ROOT + "/deleted/" + i.split("/")[0] + "/" + i.split("/")[1]
            makedirs(dir)
            replace(settings.MEDIA_ROOT + "/" + i, settings.MEDIA_ROOT + "/deleted/" + i)


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
