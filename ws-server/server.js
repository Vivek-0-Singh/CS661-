/**
 * CryptoLens WebSocket relay.
 *
 * Frontend clients connect to ws://localhost:8080 and send:
 *     { "type": "subscribe", "symbol": "BTC" }
 * The server maintains one upstream Binance depth stream per symbol and
 * fans out normalised cumulative-depth snapshots to subscribed clients.
 *
 * Binance public stream (no auth):
 *     wss://stream.binance.com:9443/ws/<pair>@depth20@100ms
 */
import express from "express";
import http from "http";
import { WebSocket, WebSocketServer } from "ws";

const PORT = process.env.PORT || 8080;
const PAIRS = { BTC: "btcusdt", ETH: "ethusdt", BNB: "bnbusdt", SOL: "solusdt", XRP: "xrpusdt" };

const app = express();
app.get("/health", (_req, res) => res.json({ status: "ok", symbols: Object.keys(PAIRS) }));

const server = http.createServer(app);
const wss = new WebSocketServer({ server });

// symbol -> { upstream, clients:Set, last }
const feeds = new Map();

function cumulate(levels) {
  // levels: [[priceStr, sizeStr], ...]
  let cum = 0;
  return levels.map(([p, s]) => {
    const price = parseFloat(p);
    const size = parseFloat(s);
    cum += size;
    return { price, size, cum };
  });
}

function normalise(symbol, raw) {
  const bids = cumulate(raw.bids || []); // descending prices
  const asks = cumulate(raw.asks || []); // ascending prices
  const mid =
    bids.length && asks.length ? (bids[0].price + asks[0].price) / 2 : null;
  return { type: "depth", symbol, mid, bids, asks, synthetic: false, ts: Date.now() };
}

function ensureUpstream(symbol) {
  if (feeds.has(symbol)) return feeds.get(symbol);
  const pair = PAIRS[symbol];
  const url = `wss://stream.binance.com:9443/ws/${pair}@depth20@100ms`;
  const feed = { upstream: null, clients: new Set(), last: null, url };
  feeds.set(symbol, feed);

  const connect = () => {
    const up = new WebSocket(url);
    feed.upstream = up;
    up.on("message", (buf) => {
      let raw;
      try { raw = JSON.parse(buf.toString()); } catch { return; }
      const msg = normalise(symbol, raw);
      feed.last = msg;
      const payload = JSON.stringify(msg);
      for (const c of feed.clients) {
        if (c.readyState === WebSocket.OPEN) c.send(payload);
      }
    });
    up.on("close", () => {
      // Reconnect only while clients are still listening.
      if (feed.clients.size > 0) setTimeout(connect, 1000);
    });
    up.on("error", (err) => {
      console.error(`upstream ${symbol} error:`, err.message);
      up.close();
    });
  };
  connect();
  return feed;
}

function unsubscribeAll(client) {
  for (const [symbol, feed] of feeds) {
    if (feed.clients.delete(client) && feed.clients.size === 0) {
      feed.upstream?.close();
      feeds.delete(symbol);
    }
  }
}

wss.on("connection", (client) => {
  client.on("message", (buf) => {
    let msg;
    try { msg = JSON.parse(buf.toString()); } catch { return; }
    if (msg.type === "subscribe" && PAIRS[msg.symbol]) {
      unsubscribeAll(client);
      const feed = ensureUpstream(msg.symbol);
      feed.clients.add(client);
      if (feed.last) client.send(JSON.stringify(feed.last)); // instant first paint
    } else if (msg.type === "unsubscribe") {
      unsubscribeAll(client);
    }
  });
  client.on("close", () => unsubscribeAll(client));
  client.send(JSON.stringify({ type: "hello", symbols: Object.keys(PAIRS) }));
});

server.listen(PORT, () => console.log(`CryptoLens ws relay on ws://localhost:${PORT}`));
