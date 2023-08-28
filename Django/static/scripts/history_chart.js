//https://www.highcharts.com/blog/download/

//const data = [1000,1012.5,1025.0,1037.658334230474,1050.1520968917494,1062.6302620211297,1075.141734404867,1063.953383350177,1065.5745409851293,1075.8000347470706,1086.5304937084748,1097.7297904981492,1108.7090463978764,1095.4693752400894,1105.9296311867,1117.001523863319,1128.7625753719667,1141.9936927963602,1154.8607895966206,1143.3327641617923,1131.095156833958,1138.799038389122,1124.0409735632672,1108.3214876799334,1092.8315617582934,1093.0441696353075,1093.4782350280434,1090.2579621894383,1092.7031898316318,1102.8504757933165,1111.6853301391905,1105.3701303552268,1101.191269326774,1097.0542622943806,1093.2850429270657];
/*var events = ["Robot Wars Series 3", "Series 4", "Series 5","Extreme 1", "Series 6", "Extreme 2"],
  i;*/
document.addEventListener('DOMContentLoaded', function () {
        var dataElement = document.getElementById('history-data');
        var historyData = dataElement.getAttribute('history');
        historyData = historyData.substring(1,historyData.length-1);
        historyData = historyData.split(", ");
        for (var i = 0; i < historyData.length; i++){
            historyData[i] = Number(historyData[i]);
        }
        const chart = Highcharts.chart('history-chart', {
            chart: {
                type: 'line'
            },
            title: {
                text: 'Rank over time'
            },
            /*xAxis: [{
                tickPositions: [0,7.2,13.2,20.2,27.2,31.2],
                gridLineWidth: 1,
                labels: {
                    enabled:false
                }
             },
            {
               	tickPositions: [3.5,10,16.5,23.5,29,33],
                linkedTo:0,
                tickWidth: 0,
                offset:0,
                labels: {
                    formatter: function() {
                    i++;
                    if (this.isFirst === true){
                    i = 0
                    }
                    return events[i];
                    }
                }
            }],*/
            yAxis: {
                title: {
                    text: 'Rank'
                }
            },
            series: [{
                name: document.getElementById("title").innerHTML,
                data: historyData
            }]
        })
        });