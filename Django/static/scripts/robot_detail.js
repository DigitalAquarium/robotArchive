function viewRobot(versionID) {
    let versions = document.getElementsByClassName("version-block");
    let tabs = document.getElementsByClassName("tab-button");
    for (let i = 0; i < versions.length; i++) {
        versions[i].style.display = "none";
        tabs[i].className = tabs[i].className.replace(" active","")
    }
    document.getElementById("ver-" + versionID).style.display = "block";
    document.getElementById("but-" + versionID).className += " active";
}