$(document).ready(function(){
     $.ajax({
         type: 'GET',
         url: "/ajax/yt_video_status/" + $("#fight-id").text(),
         success: function (response) {
            if (!response['embeddable']){
                $("#yt-video").remove();
                $(".fight-media").append('<div id="yt-error">This video has embedding disabled. Click below to watch on YouTube.</div>')
                $(".fight-media").append('<a id="back-up-vid-link" href="'  +response["url"] + '"></a>')
                $("#back-up-vid-link").append("<h2>" + escape(response['title']) + "</h2>")
                $("#back-up-vid-link").append("<img src=" + response['thumb'] + ">")
            };
            if (response['allowed_countries'].length > 0){
                $(".fight-media").prepend('<div id="yt-error" style="display:flex; justify-content:center">This video is only available in the following countries: </div>')
                for (let i = 0; i < response["allowed_countries"].length;i++){
                    $("#yt-error").append('<img class="flag-image" src="/static/flags/4x3/' + response["allowed_countries"][i].toLowerCase() + '.svg">')
                }
            }
            if (response['blocked_countries'].length > 0){
                $(".fight-media").prepend('<div id="yt-error" style="display:flex; justify-content:center">This video is not available in the following countries: </div>')
                for (let i = 0; i < response["blocked_countries"].length;i++){
                    $("#yt-error").append('<img class="flag-image" src="/static/flags/4x3/' + response["blocked_countries"][i].toLowerCase() + '.svg">')
                }
            }
         },
         error: function (response) {
            console.log(response);
         }
     });
});