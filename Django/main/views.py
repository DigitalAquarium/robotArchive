import datetime

from django.urls import reverse

from EventManager import stuff

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.shortcuts import render
from django.views import generic
from django.core.exceptions import ObjectDoesNotExist

from .forms import *
from main import subdivisions


# TODO: Email stuff (low prio),Fight edit cleanup, auto person merging, Home page, leaderboard still needs smol css

@login_required(login_url='/accounts/login/')
def delete_view(request, model, instance_id, next_id=None):
    next_url = reverse("main:index")

    if model == "person":
        instance = Person.objects.get(pk=instance_id)
    elif model == "team":
        instance = Team.objects.get(pk=instance_id)
    elif model == "weight_class":
        instance = Weight_Class.objects.get(pk=instance_id)
    elif model == "robot":
        instance = Robot.objects.get(pk=instance_id)
        next_url = reverse("main:teamDetail", args=[next_id])
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
        return render(request, "main/delete.html", {"instance": instance, "model": model, "next_id": next_id})


def index_view(request):
    events = Event.objects.filter(start_date__gte=datetime.date.today()).order_by("start_date")[:5]
    random_robot = Robot.objects.order_by("?")[0]
    return render(request, "main/index.html", {"upcoming_event_list": events, "r": random_robot})


def event_index_view(request):
    name = request.GET.get("name") or ""
    page = request.GET.get("page")
    regions = request.GET.get("regions")
    country_code = request.GET.get("country") or ""
    reg_open = request.GET.get("reg_open")
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

    if past != "on":
        event_list = event_list.filter(start_date__gt=timezone.now())

    if reg_open == "on":
        bad = []
        for event in event_list:
            if event.is_registration_full():
                bad.append(event.id)
        event_list = event_list.exclude(id__in=bad)

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


def event_detail_view(request, event_id):
    event = Event.objects.get(pk=event_id)
    fran = event.franchise
    if request.user.is_authenticated:
        can_change = fran.can_edit(request.user)
    else:
        can_change = False
    return render(request, "main/event_detail.html",
                  {"event": event,
                   "map": stuff.map,
                   "can_change": can_change,
                   "reg_future": event.registration_open > timezone.now()})


@login_required(login_url='/accounts/login/')
def new_event_view(request, franchise_id):
    fran = Franchise.objects.get(pk=franchise_id)  # TODO: Add verification
    can_change = fran.can_edit(request.user)
    if not can_change:
        return redirect("%s?m=%s" % (
            reverse("main:message"), "You do not have permission to create a new event for this franchise."))
    if request.method == "POST":
        form = EventForm(request.POST)
        if form.is_valid():
            event = form.save(commit=False)
            event.franchise = fran
            event.save()
            return redirect("main:eventDetail", event.id)
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
        form = EventForm(request.POST, instance=event)
        if form.is_valid():
            new = form.save()
            return redirect("main:eventDetail", new.id)
    else:
        form = EventForm(instance=event)
    return render(request, "main/edit_event.html", {"form": form, "event_id": event_id})


def contest_signup_view(response, contest_id):
    contest = Contest.objects.get(pk=contest_id)

    if not contest.is_registration_open():
        if contest.is_registration_past():
            return redirect("%s?m=%s" % (reverse("main:message"), "Registration for this contest has closed."))
        else:
            return redirect("%s?m=%s" % (reverse("main:message"), "Registration for this contest has not yet opened."))

    if contest.is_registration_full():
        return redirect("%s?m=%s" % (reverse("main:message"), "Entries for this contest are full."))

    if response.user.is_authenticated:
        owned_versions = Version.objects.filter(team__members__user=response.user)
        applied = contest.registration_set.filter(version__in=owned_versions).exists()
        if applied:
            return redirect("%s?m=%s" % (reverse("main:message"), "You've Already signed up for this contest."))

        user = response.user
        me = Person.objects.get(user=user)
        if response.method == "POST":
            form = SignupForm(response.POST)
            t = Person_Team.objects.filter(person=me)
            teams = []
            for result in t:
                teams.append(result.team)
            form.fields['version'].queryset = Version.objects.filter(team__in=teams)
            if form.is_valid():
                if contest.entries != 0 and (contest.registration_set.count() >= contest.entries + contest.reserves):
                    # A Second Check in case slots filled up between the time the page was loaded and the time the
                    # form was completed
                    return redirect("%s?m=%s" % (reverse("main:message"), "Entries for this contest are full."))
                form.save(contest, me)
                return redirect("%s?m=%s" % (reverse("main:message"), "Successfully signed up to " + contest.__str__()))
        else:
            form = SignupForm()
            t = Person_Team.objects.filter(person=me)
            teams = []
            for result in t:
                teams.append(result.team)
            form.fields['version'].queryset = Version.objects.filter(team__in=teams,
                                                                     weight_class=contest.weight_class)
        return render(response, "main/contest_signup.html", {"form": form, "contest": contest})

    else:
        if response.method == "POST":
            anon_form = AnonSignupForm(response.POST)
            if anon_form.is_valid():
                if contest.entries != 0 and (contest.registration_set.count() >= contest.entries + contest.reserves):
                    # A Second Check in case slots filled up between the time the page was loaded and the time the
                    # form was completed
                    return redirect("%s?m=%s" % (reverse("main:message"), "Entries for this contest are full."))
                anon_form.save(contest)
                return redirect("%s?m=%s" % (reverse("main:message"), "You've successfully signed up to " + contest.event.__str__() + " at " + contest.__str__() ))
        else:
            anon_form = AnonSignupForm()
        return render(response, "main/contest_signup.html", {"anon_form": anon_form, "contest": contest})


def contest_detail_view(request, contest_id):
    contest = Contest.objects.get(pk=contest_id)
    fights = Fight.objects.filter(contest=contest)
    registrations = contest.registration_set.all().order_by("signup_time")
    applied = False
    approved = False
    reserve = False
    app_ver = False
    if request.user.is_authenticated:
        if contest.event.start_date > timezone.now().date() and timezone.now() > contest.event.registration_open:
            owned_versions = Version.objects.filter(team__members__user=request.user)
            applied = contest.registration_set.filter(version__in=owned_versions).exists()
            if applied:
                app_ver = contest.registration_set.get(version__in=owned_versions)
                approved = contest.registration_set.filter(version__in=owned_versions, approved=True).exists()
                reserve = contest.registration_set.filter(version__in=owned_versions, reserve=True).exists()
        can_change = contest.can_edit(request.user)
    else:
        can_change = False
    return render(request, "main/contest_detail.html",
                  {"contest": contest, "fights": fights, "applications": registrations,
                   "future": contest.event.registration_open > timezone.now(), "can_change": can_change,
                   "applied": applied, "approved": approved, "reserve": reserve, "app_ver": app_ver})


@login_required(login_url='/accounts/login/')
def modify_registration_view(request, reg_id):
    approval = request.GET.get("approval")
    reserve = request.GET.get("reserve")
    registration = Registration.objects.get(pk=reg_id)
    if not registration.can_edit(request.user):
        redirect("%s?m=%s" % (reverse("main:message"), "You do not have permission to edit this registration."))

    if approval == "true":
        approval = True
    elif approval == "false":
        approval = False
    else:
        approval = registration.approved

    if reserve == "true":
        reserve = True
    elif reserve == "false":
        reserve = False
    else:
        reserve = registration.reserve

    registration.approved = approval
    registration.reserve = reserve
    registration.save()
    return redirect("main:contestDetail", registration.contest.id)


@login_required(login_url='/accounts/login/')
def new_contest_view(request, event_id):
    event = Event.objects.get(pk=event_id)  # TODO: Add verification
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
            return redirect("main:eventDetail", event.id)
    else:
        form = ContestForm()
    return render(request, "main/new_contest.html", {"form": form, "event": event})


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
            return redirect("main:eventDetail", contest.event.id)
    else:
        form = ContestForm(instance=contest)
    return render(request, "main/edit_contest.html", {"form": form, "contest_id": contest_id})


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
                robot_list = robot_list.filter(version__team__country__in=subdivisions.subs[country_code]).distinct()
            except KeyError:
                robot_list = robot_list.filter(version__team__country=country_code).distinct()
        elif country_code == "GB":
            robot_list = robot_list.filter(version__team__country__in=subdivisions.uk).distinct()
        else:
            robot_list = robot_list.filter(version__team__country=country_code).distinct()

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
    weight = request.GET.get("weight")
    try:
        weight = int(weight)
    except (ValueError, TypeError):
        weight = 100000
    robot_list = Robot.get_leaderboard(weight)
    return render(request, "main/robot_leaderboard.html",
                  {"robot_list": robot_list,
                   "weights": [(0, "")] + Weight_Class.LEADERBOARD_VALID,
                   "chosen_weight": weight,
                   })


def robot_detail_view(request, robot_id):
    r = Robot.objects.get(pk=robot_id)
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
    fights = Fight.objects.filter(competitors__robot=r).order_by("contest__event__start_date", "number")
    awards = Award.objects.filter(version__robot=r)
    return render(request, "main/robot_detail.html",
                  {"robot": r, "fights": fights, "awards": awards, "ver": v, "can_change": can_change})


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
            return redirect("main:robotDetail", robot.id)
    else:
        form = RobotForm(instance=robot)
    return render(request, "main/edit_robot.html", {"form": form, "robot": robot})


@login_required(login_url='/accounts/login/')
def version_edit_view(request, version_id):  # TODO: MASSIVE NEEDS TO BE DONE RIGHT HERE
    version = Version.objects.get(pk=version_id)
    can_change = version.can_edit(request.user)
    if not can_change:
        return redirect(
            "%s?m=%s" % (reverse("main:message"), "You do not have permission to edit this robot."))
    if request.method == "POST":
        form = VersionForm(request.POST, request.FILES, instance=version)
        if form.is_valid():
            form.save()
            return redirect("main:versionDetail", version.id)
    else:
        form = VersionForm(instance=version)
    return render(request, "main/edit_version.html", {"form": form, "version": version, "new": False})


@login_required(login_url='/accounts/login/')
def new_version_view(request, robot_id):
    robot = Robot.objects.get(pk=robot_id)
    can_change = robot.can_edit(request.user)
    # if request.is_staff:
    #    valid_teams = Team.objects.all()
    # else:
    valid_teams = Team.objects.filter(members__user=request.user)
    if not can_change:
        return redirect(
            "%s?m=%s" % (reverse("main:message"), "You do not have permission to edit this robot."))
    if request.method == "POST":
        form = NewVersionForm(request.POST, request.FILES)
        form.fields['team'].queryset = valid_teams
        if form.is_valid():
            version = form.save(robot)
            return redirect("main:versionDetail", version.id)
    else:
        form = NewVersionForm()
        form.fields['team'].queryset = valid_teams
    return render(request, "main/edit_version.html", {"form": form, "robot": robot, "new": True})


def team_detail_view(request, team_id):
    team = Team.objects.get(pk=team_id)
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
    return render(request, "main/team_detail.html", {"team": team, "can_change": can_change, "leave_id": pt.id if pt else 1})


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


@login_required(login_url='/accounts/login/')
def new_robot_view(request, team_id):
    team = Team.objects.get(pk=team_id)
    can_change = team.can_edit(request.user)
    if not can_change:
        return redirect(
            "%s?m=%s" % (reverse("main:message"), "You do not have permission to create a new robot for this team."))
    if request.method == "POST":
        form = NewRobotForm(request.POST, request.FILES)
        if form.is_valid():
            form.save(team)
            return redirect("main:index")
    else:
        form = NewRobotForm()
    return render(request, "main/new_robot.html", {"form": form, "team": team})


def version_detail_view(request, version_id):
    v = Version.objects.get(pk=version_id)
    robot_id = v.robot.id
    return redirect("%s?v=%d" % (reverse("main:robotDetail", args=[robot_id]), version_id))


@login_required(login_url='/accounts/login/')
def team_edit_view(request, team_id=None):
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
                person = Person.objects.get(user=request.user)
                Person_Team.objects.create(team=new, person=person)
            return redirect("main:index")
    else:
        if team_id is None:
            form = TeamForm()
        else:
            team = Team.objects.get(pk=team_id)
            form = TeamForm(instance=team)
    if team_id is None:
        return render(request, "main/edit_team.html", {"form": form, "team_id": team_id})
    else:
        return render(request, "main/edit_team.html", {"form": form, "team_id": team_id})


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
            form = FranchiseForm(request.POST)
        else:
            franchise = Franchise.objects.get(franchise_id)
            form = FranchiseForm(request.POST, instance=franchise)
        if form.is_valid():
            new = form.save()
            if franchise_id is None:
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
        return render(request, "main/modify_franchise.html", {"form": form, "franchise_id": franchise_id})
    else:
        return render(request, "main/modify_franchise.html", {"form": form, "franchise_id": franchise_id})


def franchise_detail_view(request, fran_id):
    fran = Franchise.objects.get(pk=fran_id)
    pf = None
    if request.user.is_authenticated:
        can_change = fran.can_edit(request.user)
        if can_change:
            try:
                pf = Person_Franchise.objects.get(franchise=fran, person__user=request.user)
            except ObjectDoesNotExist:
                pass
    else:
        can_change = False
    return render(request, "main/franchise_detail.html",
                  {"fran": fran, "can_change": can_change, "leave_id": pf.id or 1})


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
    f.number = 1
    for prevFight in contest.fight_set.all():  # Should Probably find a more efficient way of doing
        # this but it'll work for now
        if prevFight.number >= f.number:
            f.number = prevFight.number + 1
    if contest.fight_type == "MU":
        f.save()
        return redirect("main:editJustFight", f.id)
    else:
        f.fight_type = contest.fight_type
        f.save()
        return redirect("main:editWholeFight", f.id)


@login_required(login_url='/accounts/login/')
def fight_editj_view(request, fight_id):  # Just the Fight
    fight = Fight.objects.get(pk=fight_id)
    can_change = fight.can_edit(request.user)
    if not can_change:
        return redirect("%s?m=%s" % (reverse("main:message"), "You do not have permission to edit this fight."))
    if request.method == "POST":
        form = FightForm(request.POST, request.FILES, instance=fight)
        if form.is_valid():
            form.save()
            return redirect("main:editWholeFight", fight_id)
    else:
        form = FightForm(instance=fight)
        return render(request, "main/modify_fight.html", {"form": form, "fight_id": fight_id})


@login_required(login_url='/accounts/login/')
def fight_edith_view(request, fight_id):  # The fight and the robots and media etc

    fight = Fight.objects.get(pk=fight_id)
    can_change = fight.can_edit(request.user)
    if not can_change:
        return redirect("%s?m=%s" % (reverse("main:message"), "You do not have permission to edit this fight."))

    if request.GET.get("save") == "true":
        fight.calculate(commit=True)
        return redirect("main:contestDetail", fight.contest.id)

    return render(request, "main/edit_whole_fight.html", {"fight": fight})


def fight_detail_view(request, fight_id):  # TODO: Sort this better
    fight = Fight.objects.get(pk=fight_id)
    if request.user.is_authenticated:
        can_change = fight.can_edit(request.user)
    else:
        can_change = False
    return render(request, "main/fight_detail.html", {"fight": fight, "can_change": can_change})


@login_required(login_url='/accounts/login/')
def modify_fight_version_view(request, fight_id, vf_id=None):
    fight = Fight.objects.get(pk=fight_id)
    can_change = fight.can_edit(request.user)
    if not can_change:
        return redirect("%s?m=%s" % (reverse("main:message"), "You do not have permission to edit this fight."))
    registered = Version.objects.filter(registration__contest=fight.contest.id)
    if vf_id is not None:
        vf = Fight_Version.objects.get(pk=vf_id)
    else:
        vf = Fight_Version()
        vf.fight = fight
    form = RobotFightForm(request.POST or None, instance=vf)
    if form.is_valid():
        form.save()
        return redirect("main:editWholeFight", fight_id)
    form.fields['version'].queryset = registered

    return render(request, "main/modify_fight_version.html",
                  {"form": form, "fight_id": fight_id, "fight_version_id": vf_id})
    # TODO: This is basically identical to modify_fight and probably many more


def award_index_view(request, event_id):
    event = Event.objects.get(pk=event_id)
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
            return redirect("main:eventDetail", event_id)
    else:
        form = AwardForm()
        form.fields['contest'].queryset = Contest.objects.filter(event=event)
        form.fields['version'].queryset = Version.objects.filter(registration__contest__in=event.contest_set.all())
        return render(request, "main/new_award.html", {"form": form, "event_id": event_id})


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
            return redirect("main:eventDetail", a.event.id)
    else:
        form = AwardForm(instance=a)
        form.fields['contest'].queryset = Contest.objects.filter(event=a.event)
        form.fields['version'].queryset = Version.objects.filter(registration__contest__in=a.event.contest_set.all())
        return render(request, "main/edit_award.html", {"form": form, "award_id": award_id})


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
    return render(request, "main/edit_person.html", {"form": form, "person": person})


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
    return render(request, "main/new_weight_class.html", {"form": form, "return_id": return_id})


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
            return redirect("main:robotDetail", robot.id)
        else:
            return render(request, "main/transfer_robot.html", {"robot": robot, "team": team})


def credits_view(request):
    return render(request, "main/credits.html", {})
