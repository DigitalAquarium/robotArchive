function showHide(targetID,senderID,replacementText='') {
    target = $("#"+targetID);
    sender = $("#"+senderID);
    if (target.is(":hidden")){
        if (target.hasClass("showhide-block")){
            target.css("display","block");
            target.show();
        }
        else if (target.hasClass("showhide-flex")){
            target.css("display","flex");
            target.show();
        }
        else{
            target.show();
        };
    }
    else{
        target.css("display","none");
    };
    if (replacementText != ''){
        originalText = sender.text();
        sender.text(replacementText);
        sender.attr("onclick","showHide('"+targetID+"','"+senderID+"','"+originalText+"')");
    }
}