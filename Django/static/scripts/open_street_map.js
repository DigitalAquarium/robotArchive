 //stolen from https://stackoverflow.com/questions/925164/openstreetmap-embedding-map-in-webpage-like-google-maps
 
 // Where you want to render the map.
var element = document.getElementById('osm-map');

// Height has to be set. You can do this in CSS too.
//element.style = 'height:300px;';

// Create Leaflet map on map element.
var map = L.map(element);

// Add OSM tile layer to the Leaflet map.
L.tileLayer('http://{s}.tile.osm.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="http://osm.org/copyright">OpenStreetMap</a> contributors'
}).addTo(map);

// Target's GPS coordinates.
var target = L.latLng(element.getAttribute("lat"), element.getAttribute("lng"));

// Set map's center to target with zoom 14.
map.setView(target, 14);

// Place a marker on the same location.
var marker = L.marker(target).addTo(map)
	.bindPopup(element.getAttribute("location_name"))
	.openPopup();