$(document).ready(function(){
$("#existing-locations").change(function(){
    if ($(this).val() != -1){
        $.ajax({
            type: 'GET',
            url: "/ajax/location-request",
            data: {"id": $(this).val()},
            success: function (response) {
                $("#location-name").val(response["name"]);
                $("#location-lat").val(response["latitude"]);
                $("#location-lng").val(String(response["longitude"]));
                target = L.latLng(response["latitude"], response["longitude"]);
                map.setView(target, 14);
                map.removeLayer(marker)
                marker = L.marker(target).addTo(map)
	                .bindPopup(response['name'])
	                .openPopup();

            },
            error: function (response) {
                console.log(response);
            }
        });}
    else{
        $("#location-name").val("");
        $("#location-lat").val("");
        $("#location-lng").val("");
    }});

$("#location-name").on("input", function(){
    $("#existing-locations").val(-1)
    map.removeLayer(marker)
    marker = L.marker(target).addTo(map)
	    .bindPopup($(this).val())
        .openPopup();
});
$("#location-lat, #location-lng").on("input", function(){
    $("#existing-locations").val(-1)
    map.removeLayer(marker)
    target = L.latLng($("#location-lat").val(), $("#location-lng").val());
    map.setView(target, 14);
    marker = L.marker(target).addTo(map)
	    .bindPopup($("#location-name").val())
        .openPopup();
});
});