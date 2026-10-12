declare module "plotly.js-gl3d-dist-min" {
  interface PlotlyHTMLElement extends HTMLElement {
    on(event: string, handler: (data: { points: { customdata?: unknown }[] }) => void): void;
  }
  const Plotly: {
    react(el: HTMLElement, data: unknown[], layout?: unknown, config?: unknown): Promise<PlotlyHTMLElement>;
    purge(el: HTMLElement): void;
  };
  export default Plotly;
}
