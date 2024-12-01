from datetime import timedelta

from django.db import IntegrityError, OperationalError
from django.http import JsonResponse

from bbguessinggame.models import *

from django.shortcuts import render

from django.utils import timezone

todayTz = timezone.now()
today = todayTz.timetuple().tm_yday


def setHiddenBots(all=False):
    hiddenBots = HiddenBot.objects.all()
    if len(hiddenBots) < 366:
        HiddenBot.objects.all().delete()
        abot = BattleBot.objects.all()[0]
        newhbs = []
        for i in range(len(hiddenBots), 366):
            hb = HiddenBot()
            hb.day = i + 1
            hb.bot = abot
            newhbs.append(hb)
        HiddenBot.objects.bulk_create(newhbs)

    uniqueRobots = BattleBot.objects.count()
    uniqueDays = 60 if uniqueRobots > 60 else uniqueRobots

    hbs = HiddenBot.objects.all().order_by("-day")[0:uniqueDays // 2] | HiddenBot.objects.all().order_by("day")[
                                                                        0:uniqueDays // 2]
    justBots = [hb.bot for hb in hbs]
    hbs = list(HiddenBot.objects.all().order_by("day"))

    def setBot(justBots, hbs, i):
        newBot = BattleBot.objects.all().order_by("?")[0]
        while newBot in justBots:  # This is slower on a hit but will average to a lower use of the database than checking for uniqueness at the database layer
            newBot = BattleBot.objects.all().order_by("?")[0]
        hbs[i].bot = newBot
        justBots.pop(0)
        justBots.append(newBot)

    global today
    if all:
        for i in range(0, 366):
            setBot(justBots, hbs, i)
    else:
        if today == 1:
            for i in range(2, 363):
                setBot(justBots, hbs, i)
        else:
            for i in [363, 364, 365, 0, 1]:
                setBot(justBots, hbs, i)
    print(hbs)
    HiddenBot.objects.bulk_update(hbs, ["bot"])


try:
    if HiddenBot.objects.count() != 366:
        setHiddenBots(all=True)
except:  # (IntegrityError, OperationalError):
    print("Please add some robots before continuing!!")


def indexView(request):
    global today, todayTz
    if todayTz.day != timezone.now().day:
        if today == 1 or today == 10:
            # reset bots on the first of jan, then cover the areas around that date on the 10th so that it
            # doesn't change people's result mid-game
            setHiddenBots()
        todayTz = timezone.now()
        today = todayTz.timetuple().tm_yday
    try:
        won = request.COOKIES["won"]
    except KeyError:
        won = False
    try:
        tzOffset = -int(request.COOKIES["tzOffset"])
        gameStartDay = int(request.COOKIES["gameStartDay"])
        if (timezone.now() + timedelta(minutes=tzOffset)).timetuple().tm_yday == gameStartDay:
            resetGame = False
            guessed = request.COOKIES["guessed"].split(",")
            botOfTheDay = HiddenBot.objects.get(day=gameStartDay).bot
        else:
            guessed = []
            resetGame = True
    except KeyError:
        guessed = []
        resetGame = False
    colourGrid = [[None] * 6, [None] * 6, [None] * 6, [None] * 6, [None] * 6, [None] * 6]
    bbNames = []
    for i in range(len(guessed)):
        guess = BattleBot.objects.get(id=guessed[i])
        matchResults = botOfTheDay.match(guess)
        bbNames.append(guess.name)
        j = 0
        for x in ["letter", "debut", "weapon", "finish", "colour", "country"]:
            colourGrid[i][j] = "green" if matchResults[x] == "match" else "yellow" if matchResults[
                                                                                          x] == "close" else "#202020"
            j += 1
    answer = None
    if (won or len(guessed) == 6) and not resetGame:
        answer = botOfTheDay
    response = render(request, "bbGuessGame/game.html",
                      {"colourGrid": colourGrid, "bbNames": bbNames, "answer": answer})
    if resetGame:
        response.delete_cookie("guessed", path="/battlebordle")
        response.delete_cookie("gameStartDay", path="/battlebordle")
        response.delete_cookie("won", path="/battlebordle")
    return response


def dataView(request):
    return render(request, "bbGuessGame/data.html", {"bots": BattleBot.objects.all().order_by("debut", "name")})


def matchView(request):
    guess = BattleBot.objects.get(id=request.GET["id"])
    botOfTheDay = HiddenBot.objects.get(day=request.GET["gameStartDay"]).bot

    return JsonResponse(guess.match(botOfTheDay), status=200)


def getBotOfTheDayView(request):
    r = HiddenBot.objects.get(day=request.GET["gameStartDay"]).bot
    return JsonResponse({"name": r.name, "image": r.image.url}, status=200)


def getByNameView(request):
    name = request.GET.get("name")
    name = name.lower()
    name = name.replace("jag", "Jäg")
    name = name.replace("ock j", "ock-j")
    name = name.replace("er the", "er: the")
    name = name.replace(" o ", " o' ")
    name = name.replace("disko i", "disk o' i")
    name = name.replace("rotator", "RotatoЯ")
    name = name.replace("ragnarok", "Ragnarök")
    name = name.replace("war e", "war? e")
    name = name.replace("? ez", "? ez!")
    robots = BattleBot.objects.filter(name__icontains=name).order_by("name")
    i = 0
    response = {"robots": []}
    if name == "":
        return JsonResponse(response, status=200)
    for r in robots:
        response["robots"].append({"id": r.id, "name": r.name, "image": r.image.url})
        i += 1
        if i == 3:
            break
    return JsonResponse(response, status=200)


def getDebugTimes(request):
    tzOffset = -int(request.COOKIES["tzOffset"])
    gameStartDay = request.COOKIES["gameStartDay"]
    return JsonResponse({
        "serverToday": todayTz.strftime("%d-%m-%y %H:%M"),
        "serverTime": (timezone.now() + timedelta(minutes=tzOffset)).strftime("%d-%m-%y %H:%M"),
        "clientTime": (timezone.now() + timedelta(minutes=tzOffset)).strftime("%d-%m-%y %H:%M"),
        "gameStart": gameStartDay,
        "clientToday": (timezone.now() + timedelta(minutes=tzOffset)).timetuple().tm_yday
    }
        , status=200)
