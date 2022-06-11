function viewRobot(versionID, robotID) {
    let versions = document.getElementsByClassName("version-block");
    let tabs = document.getElementsByClassName("tab-button");
    for (let i = 0; i < versions.length; i++) {
        versions[i].style.display = "none";
        tabs[i].className = tabs[i].className.replace(" active", "")
    }
    document.getElementById("ver-" + versionID).style.display = "block";
    document.getElementById("but-" + versionID).className += " active";
    //document.getElementById("edit-version-button").textContent = "Edit " + document.getElementById("but-" + versionID).textContent
    document.getElementById("edit-version-button").href = "/versions/" + versionID + "/edit"
    document.getElementById("delete-version-button").href = "/delete/version/" + versionID + "/" + robotID
    //document.getElementById("edit-version-button").href =
    //document.getElementById("edit-version-button").href.replace("/[0-9]{1,}/",versionID);
}