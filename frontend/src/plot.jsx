// Shared Plotly component built from the minified dist bundle (includes the
// finance/candlestick traces) to keep bundling predictable.
import createPlotlyComponent from "react-plotly.js/factory";
import Plotly from "plotly.js-dist-min";

export const Plot = createPlotlyComponent(Plotly);
