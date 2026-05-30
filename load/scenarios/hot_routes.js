import http from "k6/http";
import { check } from "k6";
import {
  clients,
  hotRoutes,
  pickRandom,
  routeRequest,
  statusOkOr429,
} from "../common.js";

export const options = {
  scenarios: {
    hot_routes: {
      executor: "constant-arrival-rate",
      rate: Number(__ENV.TARGET_RPS || 150),
      timeUnit: "1s",
      duration: __ENV.DURATION || "30s",
      preAllocatedVUs: 40,
      maxVUs: 200,
    },
  },
  thresholds: {
    checks: ["rate>0.99"],
    http_req_duration: ["p(99)<100"],
  },
};

export default function () {
  const client = pickRandom(clients);
  const route = Math.random() < 0.8 ? pickRandom(hotRoutes) : "/v1/demo";
  const req = routeRequest(route, client);
  const res =
    req.method === "POST"
      ? http.post(req.url, null, req.params)
      : http.get(req.url, req.params);
  check(res, statusOkOr429);
}
