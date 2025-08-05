export type MetricsListener = (data: any) => void;

class MetricsSocket {
  private ws: WebSocket | null = null;
  private listeners: MetricsListener[] = [];

  connect() {
    if (this.ws) return;
    const url = `${location.origin.replace(/^http/, "ws")}/ws/metrics`;
    this.ws = new WebSocket(url);
    this.ws.onmessage = (ev) => {
      const payload = JSON.parse(ev.data);
      this.listeners.forEach((l) => l(payload));
    };
    this.ws.onclose = () => {
      this.ws = null;
    };
  }

  on(listener: MetricsListener) {
    this.listeners.push(listener);
  }
}

export const metricsSocket = new MetricsSocket();
