import http from "k6/http";
import { check } from "k6";
import {
  clients,
  pickRandom,
  routeRequest,
  statusOkOr429,
} from "../common.js";

export const options = {
  scenarios: {
    concurrent: {
      executor: "constant-vus",
      vus: Number(__ENV.VUS || 30),
      duration: __ENV.DURATION || "20s",
    },
  },
  thresholds: {
    checks: ["rate>0.99"],
  },
};

const routes = ["/v1/demo", "/v1/search", "/v1/quotes"];

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
