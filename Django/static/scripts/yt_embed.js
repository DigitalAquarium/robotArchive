let flag_blacklist =["YT","RE","BL","MF","PM","UM","WF","CP","HM","GP","GF","BQ","SJ"] //Flags that look identical to others
function render_flags(flags){
    for (let i = 0; i < flags.length;i++){
        if (!flag_blacklist.includes(flags[i])){
            $("#yt-error").append('<img class="flag-image" src="/static/flags/4x3/' + flags[i].toLowerCase() + '.svg">')
        }
    }
    $(".fight-media").css("max-height","none")
}

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
                $(".fight-media").prepend('<div id="yt-error" style="display:flex; flex-wrap:wrap; justify-content:center"><span>This video is <u>only</u> available in the following countries: </span></div>')
                render_flags(response['allowed_countries'])
            }
            if (response['blocked_countries'].length > 0){
                $(".fight-media").prepend('<div id="yt-error" style="display:flex; flex-wrap:wrap; justify-content:center"><span>This video is <u>not</u> available in the following countries: </span></div>')
                render_flags(response['blocked_countries'])
            }
         },
         error: function (response) {
            console.log(response);
         }
     });
});