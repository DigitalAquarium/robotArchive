var fb_app_id = '282093964915903'

$(document).ready(function(){
function facebookEmbedWidth(mobile) {
  if (mobile.matches) {
    $("#fight-video-fb").attr("data-height",400);
  } else {
    $("#fight-video-fb").attr("data-height",800);
  }
}
var mobile = window.matchMedia("(max-width: 700px)")
facebookEmbedWidth(mobile);
mobile.addEventListener("change", function() {
  facebookEmbedWidth(mobile);
});


window.fbAsyncInit = function() {
      FB.init({
        appId      : fb_app_id,
        xfbml      : true,
        version    : 'v3.2'
      });
      var fight_video_player;
      FB.Event.subscribe('xfbml.ready', function(msg) {
        if (msg.type === 'video') {
         url = $("#fight-video-fb").attr("data-href");
         const timestamp_re = new RegExp("[\?&]t=[0-9]+");
         var timestamp = timestamp_re.exec(url);
         if (timestamp == null){
            timestamp = 0;
         }
         else{
            timestamp = parseInt(timestamp[0].substring(3));
         }

         fight_video_player = msg.instance;
         fight_video_player.setVolume(0.2);
         fight_video_player.seek(timestamp);
        }
      });
    };
    });