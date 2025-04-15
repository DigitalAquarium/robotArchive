$(document).ready(function(){
     $.ajax({
         type: 'GET',
         url: "/ajax/disclaimer",
         success: function (response) {
            txt = response['txt'];
            let nav_txt = "Placeholder nav_txt"
            let desc_txt = "Placeholder desc_txt"
            if (txt == "Russia"){
                nav_txt = "Russian events only";
                desc_txt = " This site only covers the Russian scene. For others see the main site.";
            }
            else{
                nav_txt = "Data accurate to " + txt;
                desc_txt = " The archive is currently complete up to " + txt + ".";
            }

            $("#navbar-info-text").text(nav_txt)
            $("meta[name=description]").attr("content",$("meta[name=description]").attr("content") + desc_txt)
            $("#index-disclaimer").text(desc_txt)
         },
         error: function (response) {
            console.log(response);
         }
     });
});