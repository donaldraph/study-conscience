"""A throwaway local ingest endpoint that stands in for API Gateway in Phase 1.

It exists only to prove the rollup can POST its JSON somewhere and get a 200 back,
without needing any AWS yet. The real ingest is a Lambda behind API Gateway in
Phase 2. Run:

    python3 -m rollup.mock_ingest        # listens on 127.0.0.1:8099

Received rollups are printed and saved under rollup/out/received/ so you can eyeball
exactly what would have been shipped.
"""
import datetime as dt
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

SAVE_DIR = os.path.join(os.path.dirname(__file__), "out", "received")


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'{"error":"bad json"}')
            return

        os.makedirs(SAVE_DIR, exist_ok=True)
        stamp = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
        name = f"{payload.get('date', 'unknown')}-{stamp}.json"
        with open(os.path.join(SAVE_DIR, name), "w") as fh:
            json.dump(payload, fh, indent=2)

        summary = {
            "ok": True,
            "date": payload.get("date"),
            "events_kept": payload.get("totals", {}).get("events_kept"),
            "skills_touched": payload.get("skills_touched"),
        }
        print(f"received rollup for {summary['date']}: "
              f"{summary['events_kept']} events, "
              f"{len(summary['skills_touched'] or [])} skills -> saved {name}")
        body = json.dumps(summary).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass  # quiet the default per-request stderr spam


def main(host="127.0.0.1", port=8099):
    server = HTTPServer((host, port), Handler)
    print(f"mock ingest listening on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
