declare module "plotly.js-dist-min" {
  export type Data = any;
  export type Layout = any;
  const Plotly: any;
  export default Plotly;
}

declare module "react-plotly.js" {
  import * as React from "react";
  const Plot: React.ComponentType<any>;
  export default Plot;
}

