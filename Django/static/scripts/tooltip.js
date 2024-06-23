var mouse_x;

document.addEventListener('mousemove', (event) => {
        mouse_x = event.pageX;
});

$(document).ready(function(){
    $(".mouseover-target").mouseenter(function(){
        let tooltip = $(this).siblings(".tooltip")
        let target_height = $(this).height()
        let tooltip_height = tooltip.height() + Number(tooltip.css("padding-top").replace("px","")) + Number(tooltip.css("padding-bottom").replace("px",""))
        let offset_css = {"top": ($(this).offset().top + (target_height/2) - (tooltip_height)/2),"left": mouse_x + 24}

        tooltip.css(offset_css);
        tooltip.show();
    })

    $(".mouseover-target").mouseleave(function(){
        $(this).siblings(".tooltip").hide();
    })
})