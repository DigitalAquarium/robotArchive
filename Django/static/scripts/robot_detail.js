function viewRobot(versionID, robotID) {
    let versions = document.getElementsByClassName("version-block");
    let tabs = document.getElementsByClassName("tab-button");
    for (let i = 0; i < versions.length; i++) {
        versions[i].style.display = "none";
        tabs[i].className = tabs[i].className.replace(" active", "")
    }
    document.getElementById("ver-" + versionID).style.display = "block";
    document.getElementById("but-" + versionID).className += " active";
}

function toggleDropdown() {
    if (document.getElementById("all-lb-entries").style.display == "none"){
        document.getElementById("all-lb-entries").style.display = "block";
        document.getElementById("best-lb-entry").innerHTML = document.getElementById("best-lb-entry").innerHTML.replace("🠟","🠝");
        document.getElementById("best-lb-entry").style.margin = "0px 0px 10px 0px";
        }
    else{
        document.getElementById("all-lb-entries").style.display = "none";
        document.getElementById("best-lb-entry").innerHTML = document.getElementById("best-lb-entry").innerHTML.replace("🠝","🠟");
        document.getElementById("best-lb-entry").style.margin = "0px 0px 20px 0px";
        }
}