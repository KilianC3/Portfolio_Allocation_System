export type MessageHandler = (data: any) => void;

/**
 * Simple wrapper around the browser WebSocket that reconnects automatically
 * and dispatches JSON messages to a callback.
 */
export class MetricsSocket {
  private url: string;
  private handler: MessageHandler;
  private ws?: WebSocket;

  constructor(url: string, handler: MessageHandler) {
    this.url = url;
    this.handler = handler;
    this.connect();
  }

  private connect() {
    this.ws = new WebSocket(this.url);
    this.ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data);
        this.handler(data);
      } catch (err) {
        console.error("failed to parse message", err);
      }
    };
    this.ws.onclose = () => {
      setTimeout(() => this.connect(), 1000);
    };
  }
}
