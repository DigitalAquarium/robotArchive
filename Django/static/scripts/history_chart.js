//https://www.highcharts.com/blog/download/

$(document).ready(function(){
     $.ajax({
         type: 'GET',
         url: "/ajax/get_history",
         data: {"robot_slug": $("#robot-slug").attr("robot-slug")},
         success: function (response) {
             fights = response["fights"]
             if (fights.length < 3){
                $("#history-chart").attr("hidden","hidden")
             }
             else{
                  const chart = Highcharts.chart('history-chart', {
                    chart: {
                        type: 'line'
                    },
                    title: {
                        text: 'Rank over time'
                    },
                    legend:{ enabled:false },
                    yAxis: {
                        title: {
                            text: 'Rank'
                        },
                        plotLines: [{
                            value: 1000,
                            color: 'darkgrey',
                            dashStyle: 'longdash',
                            width: 2,
                        }],
                    },
                    series: [{
                        name: document.getElementById("title").innerHTML,
                        data: response["history"],
                    }],
                    tooltip: {
                        formatter: function () {
                            return "<b>" + fights[this.x].rank + "</b>" + "<br>" + fights[this.x].name
                        }
                    },
                  })
             }
         },
         error: function (response) {
            console.log(response);
         }
     });
});