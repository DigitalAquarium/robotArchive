$(document).ready(function(){
    $(".botSuggestion").hide();
    //https://stackoverflow.com/questions/4220126/run-javascript-function-when-user-finishes-typing-instead-of-on-key-up
    var typingTimer;
    var timeoutMS = 250;
    //on keyup, start the countdown
    $("#guess").on('keyup', function () {
      clearTimeout(typingTimer);
      typingTimer = setTimeout(doneTyping, timeoutMS);
    });

    //on keydown, clear the countdown
    $("#guess").on('keydown', function () {
      clearTimeout(typingTimer);
    });

    //user is "finished typing," do something
    function doneTyping () {
        $.ajax({
            type:"GET",
            url:"getByName",
            data: {"name": $("#guess").val()},
            success: function (response){
                $(".botSuggestion").hide();
                let i = 0
                for (i; i<response["robots"].length; i++) {
                    $("#suggestion"+(i+1)+"Name").text(response["robots"][i]["name"]);
                    $("#suggestion"+(i+1)+"ID").text(response["robots"][i]["id"]);
                    $("#suggestion"+(i+1)+"Img").attr("src",response["robots"][i]["image"]);
                    $("#suggestion"+(i+1)).show();
                };
                $("#descriptionSpacer").css("height",50+(3-i)*(200-16)+"px");
            }
        })
    }

    const ANIMATION_TIME = 400;
    var guessNumber = 1;
    var guessUnlocked = true;
    var guessed = [];
    now = new Date();
    var gameStartDay = now.toDateString().slice(0,3);
    var tzOffset = now.getTimezoneOffset();
    cookieText = document.cookie;
    cookieText = cookieText.split("; ");
    for (let i = 0; i < cookieText.length; i++){
        if (cookieText[i].slice(0,8) == "guessed="){
            guessed = cookieText[i].slice(8).split(",")
            guessNumber = guessed.length + 1;
        }
        else if (cookieText[i].slice(0,13) == "gameStartDay="){
            gameStartDay = cookieText[i].slice(13);
        }
    };
    now.setDate(now.getDate() + 7);
    document.cookie = "gameStartDay=" + gameStartDay + "; expires=" + now;
    document.cookie = "tzOffset=" + tzOffset + "; expires=" + now;

    function revealAnswer(){
        $.ajax({
            type:"GET",
            url:"getBotOfTheDay",
            data: {"gameStartDay": gameStartDay},
            success: function (response){
                $("#botOfTheDayName").text(response["name"]);
                $("#botOfTheDayImg").attr("src",response["image"]);
                $("#botOfTheDay").show();
                $("#shareResult").show();
                $("#guess").hide();
                $(".botSuggestion").hide();
            }
        })
    }

    function showColour (field,response,callback){
        $("#"+field+guessNumber).transition({"rotateY":90},ANIMATION_TIME/2,"linear", function(){
            if (response[field] == "match") $("#"+field+guessNumber).css("background","green");
            else{
                if (response[field] == "close") $("#"+field+guessNumber).css("background","yellow")
                else $("#"+field+guessNumber).css("background","#202020");
            }
        }).transition({"rotateY":180},ANIMATION_TIME/2,"linear",function(){
            callback();
        });
    };

    $(".botSuggestion").click(function(){
        let suggestionNum = $(this).attr("id")[$(this).attr("id").length-1]
        let botID = $("#suggestion"+suggestionNum+"ID").text();
        if (guessUnlocked && !guessed.includes(botID)){
        guessUnlocked = false;
        $.ajax({
            type:"GET",
            url:"match",
            data: {"id": botID, "gameStartDay": gameStartDay},
            success: function (response){
                guessed.push(botID);
                $("#guessFeedback"+guessNumber).text($("#suggestion"+suggestionNum+"Name").text());
                expiryDate = new Date();
                expiryDate.setDate(expiryDate.getDate() + 7);
                document.cookie = "guessed=" + guessed + ";expires=" + expiryDate;

                showColour("letter",response, function(){
                 showColour("debut",response, function(){
                  showColour("weapon",response,function(){
                   showColour("finish",response,function(){
                    showColour("colour",response, function (){
                     showColour("country",response, function (){
                      guessNumber++;
                      if (response["victory"]){
                          document.cookie = "won=True;expires=" + expiryDate;
                          setTimeout(revealAnswer, ANIMATION_TIME);
                      }
                      else if (guessNumber > 6){
                          setTimeout(revealAnswer, ANIMATION_TIME);
                      }
                      else {
                        guessUnlocked = true;
                      };
                     })
                    })
                   })
                  })
                 })
                })
            }
        });
        }
    });
    $("#shareResult").click(function(){
        let dateFormatOptions = {
            day:"numeric",
            month:"long",
            year:"numeric"
        };
        toClip = "BattleBordle: " + new Date().toLocaleDateString("en-GB",dateFormatOptions) + " " + (guessNumber-1) + "/6" + "\n\n";
        let i = 0;
        let j = 0;
        test = $(".resultGrid").each(function(){
        if (i < guessNumber - 1) {
            bgColour = $(this).css("background-color");
            if (bgColour == "rgb(0, 128, 0)"){
                toClip = toClip.concat("🟩");
            }
            else if (bgColour == "rgb(32, 32, 32)"){
                toClip = toClip.concat("⬛");
            }
            else{
                toClip = toClip.concat("🟨");
            };
            if (j >= 5){
                toClip = toClip.concat("\n");
                j = 0;
                i++;
             }
            else j++;
        }
        });
        navigator.clipboard.writeText(toClip);
        $(this).text("Copied!");
    });
})