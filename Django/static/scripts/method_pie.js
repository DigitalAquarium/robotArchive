const method_name_lookup = {
	"KO": "Knockout",
	"DK": "Double KO",
	"JD": "Judge's Decision",
	"CV": "Crowd Vote",
	"TO": "Tap Out",
	"OA": "Out of the Arena",
	"PT": "Pit",
	"PN": "Pin",
	"DR": "Draw",
	"WU": "Winner Unknown",
	"NW": "No Winner Declared",
	"NM": "Method not Declared",
	"OT": "Other Win Method"
}
const method_name_lookup_loss = {
	"KO": "Knocked Out",
	"DK": "Double KO",
	"JD": "Judge's Decision",
	"CV": "Crowd Vote",
	"TO": "Tapped Out",
	"OA": "Thrown Out of the Arena",
	"PT": "Pitted",
	"PN": "Pinned",
	"DR": "Draw",
	"WU": "Winner Unknown",
	"NW": "No Winner Declared",
	"NM": "Method not Declared",
	"OT": "Other Win Method"
}

const colour_map = {
  "KO": "#fe6a35",
  "TO": "#c94e24",
  "DK": "#ff9a73",

  "JD": "#6ec6ff",
  "CV": "#1f8fd1",

  "OA": "#00e272",
  "PT": "#00a65a",
  "PN": "#7ff0b3",

  "OT": "#AAAAAA"
}

function method_pie(data,div_id,title,subtitle,click_function) {
	$.ajax({
		type: 'GET',
		url: "/ajax/win_method_statistics",
		data: data,
		success: function (response) {
			if (response["pie_total"] > 1) {
				let chart_data = []
				Object.keys(response).forEach(function(key) {
					if (key !== "NM" && key !== "NW" && key !== "WU" && key !== "DR" && key !== "pie_total") {
						let name
						if (data["robot"] !== undefined) {
							if (data["won"]==="False"){
								name = method_name_lookup_loss[key]
							}
							else{
								name = method_name_lookup[key]
							}
						}
						else{
							name = method_name_lookup[key]
						}
						chart_data.push({
							name:name,
							color: colour_map[key],
							y:response[key]
						});
					}
				})
				return Highcharts.chart(div_id, {
					chart: {
						type: 'pie',
						backgroundColor:null
					},
					title: {
						text: title
					},
					subtitle: {
						text: subtitle// + "<br>Totalling " +response["pie_total"]
					},
					tooltip:{
						valueSuffix: ' of ' + response["pie_total"]
					},
					plotOptions: {
						pie: {
							allowPointSelect: true,
							cursor: 'pointer',
							dataLabels: [{
								enabled: true,
								distance: 20
							}, {
								enabled: true,
								distance: -40,
								format: '{point.percentage:.1f}%',
								style: {
									fontSize: '1.2em',
									textOutline: 'none',
									opacity: 0.7
								},
								filter: {
									operator: '>',
									property: 'percentage',
									value: 10
								}
							}]
						}
					},
					series: [
						{
							name: 'Fights',
							colorByPoint: true,
							data: chart_data,
							point: {
								events: {
									click(e) {
										click_function(e.point,data["won"]);
									}
								}
							}
						}
					]
				});
			}},
		error: function (response) {
			console.log(response);
		}
	});
}