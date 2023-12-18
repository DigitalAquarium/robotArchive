//https://www.highcharts.com/blog/download/

$(document).ready(function(){
     $.ajax({
         type: 'GET',
         url: "/ajax/get_history",
         data: {"robot_slug": $("#robot-slug").attr("robot-slug")},
         success: function (response) {
             fights = response["fights"]

              const chart = Highcharts.chart('history-chart', {
                chart: {
                    type: 'line'
                },
                title: {
                    text: 'Rank over time'
                },
                yAxis: {
                    title: {
                        text: 'Rank'
                    }
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
         },
         error: function (response) {
            console.log(response);
         }
     });
});