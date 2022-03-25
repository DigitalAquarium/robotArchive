import datetime

from django.urls import reverse

from EventManager import stuff

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.shortcuts import render
from django.views import generic

from .forms import *
from main import subdivisions


class IndexView(generic.ListView):
    template_name = "main/index.html"
    context_object_name = "upcoming_event_list"

    def get_queryset(self):
        return Event.objects.filter(start_date__gte=datetime.date.today()).order_by("start_date")[:5]


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
    me = Person.objects.get(user=request.user)
    event = Event.objects.get(pk=event_id)
    fran = event.franchise
    can_change = fran.is_member(me)
    return render(request, "main/event_detail.html",
                  {"event": event,
                   "map": stuff.map,
                   "can_change": can_change})


def new_event_view(request, franchise_id):
    fran = Franchise.objects.get(pk=franchise_id)  # TODO: Add verification
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


def modify_event_view(request, event_id):
    event = Event.objects.get(pk=event_id)
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
                return redirect("main:index")
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
                return redirect("main:index")
        else:
            anon_form = AnonSignupForm()
        return render(response, "main/contest_signup.html", {"anon_form": anon_form, "contest": contest})


def contest_detail_view(request, contest_id):
    contest = Contest.objects.get(pk=contest_id)
    fights = Fight.objects.filter(contest=contest)
    registrations = Registration.objects.filter(contest=contest)
    return render(request, "main/contest_detail.html",
                  {"contest": contest, "fights": fights, "applications": registrations,
                   "future": contest.event.registration_open > timezone.now()})


def new_contest_view(request, event_id):
    event = Event.objects.get(pk=event_id)  # TODO: Add verification
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


def edit_contest_view(request, contest_id):
    contest = Contest.objects.get(pk=contest_id)
    if request.method == "POST":
        form = ContestForm(request.POST, instance=contest)
        if form.is_valid():
            form.save()
            return redirect("main:eventDetail", contest.event.id)
    else:
        form = ContestForm(instance=contest)
    return render(request, "main/edit_contest.html", {"form": form, "contest_id": contest_id})


def register(response):
    # TODO: This should proabably be moved
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
    robot_list = Robot.get_leaderboard(weight, datetime.date(2001, 12, 31))
    return render(request, "main/robot_leaderboard.html",
                  {"robot_list": robot_list,
                   "weights": [(0, "")] + Weight_Class.LEADERBOARD_VALID,
                   "chosen_weight": weight,
                   })

def robot_detail_view(request, robot_id):
    r = Robot.objects.get(pk=robot_id)
    version_id = -1
    if request.method == "GET":
        version_id = request.GET.get("v")
        try:
            version_id = int(version_id)
        except (ValueError, TypeError):
            version_id = -1
    fights = Fight.objects.filter(competitors__robot=r).order_by("contest__event__start_date", "number")
    awards = Award.objects.filter(version__robot=r)
    return render(request, "main/robot_detail.html",
                  {"robot": r, "fights": fights, "awards": awards, "version_id": version_id})


def team_detail_view(request, team_id):
    me = Person.objects.get(user=request.user)
    team = Team.objects.get(pk=team_id)
    member = len(Person_Team.objects.filter(person=me, team=team)) > 0  # TODO: Potentially a bad check
    # for if you can edit and such, should probably use a better system in future
    return render(request, "main/team_detail.html", {"team": team, "member": member})


def team_index_view(request):
    pass


@login_required(login_url='/accounts/login/')
def new_robot_view(request, team_id):
    team = Team.objects.get(pk=team_id)  # TODO: Add verification
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


def team_edit_view(request, team_id=None):
    if request.method == "POST":
        if team_id is None:
            form = TeamForm(request.POST)
        else:
            team = Team.objects.get(pk=team_id)
            form = TeamForm(request.POST, instance=team)
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


def franchise_modify_view(request, franchise_id=None):
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
    me = Person.objects.get(user=request.user)
    fran = Franchise.objects.get(pk=fran_id)
    member = fran.is_member(me)  # TODO: Potentially a bad check
    # for if you can edit and such, should probably use a better system in future
    return render(request, "main/franchise_detail.html", {"fran": fran, "member": member})


def franchise_index_view(request):
    pass


def new_fight_view(request, contest_id):  # TODO: Make sure you can't add the same Version to the same fight.
    contest = Contest.objects.get(pk=contest_id)
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


def fight_editj_view(request, fight_id):  # Just the Fight
    fight = Fight.objects.get(pk=fight_id)
    if request.method == "POST":
        form = FightForm(request.POST, request.FILES, instance=fight)
        if form.is_valid():
            form.save()
            return redirect("main:editWholeFight", fight_id)
    else:
        form = FightForm(instance=fight)
        return render(request, "main/modify_fight.html", {"form": form, "fight_id": fight_id})


def fight_edith_view(request, fight_id):  # The fight and the robots and media etc
    fight = Fight.objects.get(pk=fight_id)
    return render(request, "main/edit_whole_fight.html", {"fight": fight})


def fight_detail_view(request, fight_id):
    fight = Fight.objects.get(pk=fight_id)
    return render(request, "main/fight_detail.html", {"fight": fight})


def modify_fight_version_view(request, fight_id, vf_id=None):
    fight = Fight.objects.get(pk=fight_id)
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
    return render(request, "main/award_index.html", {"award_list": awards, "event": event})


def new_award_view(request, event_id):
    event = Event.objects.get(pk=event_id)
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


def award_edit_view(request, award_id):
    a = Award.objects.get(pk=award_id)
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


@login_required
def profile_view(request):
    # TODO: Should this be moved too?
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
