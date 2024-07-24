from datetime import timedelta

from django.db import IntegrityError, OperationalError
from django.http import JsonResponse

from bbguessinggame.models import *

from django.shortcuts import render

from django.utils import timezone


def setBotOfTheDay():
    # Sets bot of the day - Four days in advance to prevent the answer from randomly changing on people.
    global today
    newRandomBot = BattleBot.objects.all().order_by("?")[0]
    today = timezone.now()
    fourDaysTime = (today + timedelta(days=4)).strftime("%a")
    HBToday = HiddenBot.objects.get(day=fourDaysTime)
    HBToday.bot = newRandomBot
    HBToday.save()


today = timezone.now()
try:
    if HiddenBot.objects.count() != 7:
        HiddenBot.objects.all().delete()
        for i in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]:
            HiddenBot(day=i, bot=BattleBot.objects.all().order_by("?")[0]).save()
except (IntegrityError, OperationalError):
    print("Please add some robots before continuing!!")


def indexView(request):
    global today
    if today.day != timezone.now().day:
        setBotOfTheDay()
    try:
        won = request.COOKIES["won"]
    except KeyError:
        won = False
    try:
        tzOffset = -int(request.COOKIES["tzOffset"])
        gameStartDay = request.COOKIES["gameStartDay"]
        if (timezone.now() + timedelta(minutes=tzOffset)).strftime("%a") == gameStartDay:
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
        "serverTime": timezone.now().strftime("%d-%m-%y %H:%M"),
        "clientTime": (timezone.now() + timedelta(minutes=tzOffset)).strftime("%d-%m-%y %H:%M"),
        "gameStart": gameStartDay,
        "clientToday": (timezone.now() + timedelta(minutes=tzOffset)).strftime("%a")
    }
        , status=200)
