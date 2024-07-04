var leftMovement = 0;
var lefts = [];
var containerRHS;
function setupWidth(){
    let desiredWidth = -10;
    $(".tab-button").each(function(i){
        lefts.push($(this).offset().left)
        desiredWidth += $(this).outerWidth() + 10;
    });
    console.log(lefts,lefts[0])
    let availableWidth = $(".version-block:visible").outerWidth();
    let containerLHS = $(".tab-button:first").offset().left;
    containerRHS = containerLHS+availableWidth;
    if (desiredWidth > availableWidth){
        leftMovement = containerRHS - ($(".tab-button:last").offset().left + 20 + 12 + $(".tab-button:last").outerWidth());
    }
    let i = 0;
    $(".tab-button").animate({left: leftMovement + "px" }, function(){
        i++;
    });
    if (leftMovement != 0){
        $("#btn-scroll-left").show()
    };
}

function scrollVersions(direction){
    if (direction == "left"){
      leftMovement+= 200;
      if (leftMovement >= 0){
        leftMovement = 0;
        $("#btn-scroll-left").hide()
      }
       $("#btn-scroll-right").show()
    }
    else {
        leftMovement -= 200;
        if (leftMovement < containerRHS - (lefts[lefts.length - 1] + 20 + 12 + $(".tab-button:last").outerWidth())){
            leftMovement = containerRHS - (lefts[lefts.length - 1] + 20 + 12 + $(".tab-button:last").outerWidth());
            $("#btn-scroll-right").hide()
        }
        $("#btn-scroll-left").show()
    };
    $(".tab-button").animate({left: leftMovement + "px" });
}
$(document).ready(function(){
    setupWidth();
});
$( window ).on("resize",function(){
    setupWidth();
});


function viewRobot(versionID) {
    let versions = document.getElementsByClassName("version-block");
    let tabs = document.getElementsByClassName("tab-button");
    for (let i = 0; i < versions.length; i++) {
        versions[i].style.display = "none";
        tabs[i].className = tabs[i].className.replace(" active", "")
    }
    document.getElementById("ver-" + versionID).style.display = "block";
    document.getElementById("but-" + versionID).className += " active";
}