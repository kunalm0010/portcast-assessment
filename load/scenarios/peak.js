import http from "k6/http";
import { check } from "k6";
import {
  clients,
  routes,
  pickRandom,
  routeRequest,
  statusOkOr429,
} from "../common.js";

// Ramp toward peak load on local hardware (production target ~15k RPS).
export const options = {
  scenarios: {
    peak: {
      executor: "ramping-arrival-rate",
      startRate: Number(__ENV.START_RPS || 100),
      timeUnit: "1s",
      preAllocatedVUs: 50,
      maxVUs: 500,
      stages: [
        { duration: "15s", target: Number(__ENV.MID_RPS || 300) },
        { duration: "15s", target: Number(__ENV.PEAK_RPS || 600) },
        { duration: "10s", target: 0 },
      ],
    },
  },
  thresholds: {
    checks: ["rate>0.99"],
    http_req_duration: ["p(99)<200"],
  },
};

export default function () {
  const client = pickRandom(clients);
  const route = pickRandom(routes);
  const req = routeRequest(route, client);
  const res =
    req.method === "POST"
      ? http.post(req.url, null, req.params)
      : http.get(req.url, req.params);
  check(res, statusOkOr429);
}
