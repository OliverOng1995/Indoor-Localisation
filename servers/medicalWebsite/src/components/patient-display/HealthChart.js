import React from "react";
import { render } from "react-dom";
import { withStyles } from "@material-ui/core/styles";
// import Chart from "./Chart";
import 'chartjs-plugin-streaming';
import { Line } from 'react-chartjs-2';

const styles = theme => ({
  "chart-container": {
    height: 400
  }
});

class HealthChart extends React.Component {
  state = {
    lineChartData: {

      datasets: [
        {
          label: "BTC-USD",
          backgroundColor: "rgba(0, 0, 0, 0)",
          showLine: true,
          borderColor: this.props.theme.palette.primary.main,
          pointBackgroundColor: this.props.theme.palette.secondary.main,
          pointBorderColor: this.props.theme.palette.secondary.main,
          borderWidth: "2",
          lineTension: 0,
          pointRadius: 0,
          data: []
        }
      ]
    },
    lineChartOptions: {
      events: [],
      responsive: true,
      maintainAspectRatio: false,
      showLine: true,

      legend: {
        display: false,
      },

      elements: {

      },
      tooltips: {
        enabled: true
      },
      plugins: {
        streaming: {
          frameRate: 30
        }
      },
      scales: {
        xAxes: [
          {
            type: 'realtime',
            realtime: {
              duration: 30000,
              delay: 1000,
              pause: false,

            },
            ticks: {
              autoSkip: false,
              maxTicksLimit: 10
            }
          }
        ]
      }
    }
  };

  componentDidUpdate(prevProps, prevState) {
    if(this.props !== prevProps && prevProps.hr != null ) {
      let vitals = this.props.hr

      const oldBtcDataSet = this.state.lineChartData.datasets[0];

      let value = vitals.value
      let epoch = vitals.timestamp;
      let date = new Date(epoch)

      const newBtcDataSet = { ...oldBtcDataSet };
      let vitalSign = {x: date, y: value}
      console.log(vitalSign)

      newBtcDataSet.data.push(vitalSign);

      const newChartData = {
        ...this.state.lineChartData,
        datasets: [newBtcDataSet],

      };


      this.setState({ lineChartData: newChartData });

    }
  }

  componentWillUnmount() {
    // this.ws.close();
  }

  render() {
    const { classes } = this.props;

    return (
      <div className={classes["chart-container"]}>
      <Line
        data={this.state.lineChartData}
        options={this.state.lineChartOptions}
      />

      </div>
    );
  }
}

export default withStyles(styles, { withTheme: true })(HealthChart);
