$(document).ready(function(){
    if (window.location.hash){
        let hash_target = $(window.location.hash);
        let scroll_height = hash_target.offset().top - 250;
        if (scroll_height < 0) scroll_height = 0;
        window.scrollTo({top:scroll_height,behavior:"smooth"})
        if (hash_target.is("tr")) hash_target.css("border","5px solid var(--font-colour)");
    }
})