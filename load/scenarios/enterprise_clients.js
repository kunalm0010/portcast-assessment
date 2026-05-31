import http from "k6/http";
import { check } from "k6";
import { baseUrl, statusOkOr429 } from "../common.js";

// Compare enterprise clients on shipments: enterprise-1 has client override,
// enterprise-2 uses enterprise tier default (separate Redis buckets).
export const options = {
  scenarios: {
    enterprise_shipments: {
      executor: "shared-iterations",
      vus: 2,
      iterations: 400,
      maxDuration: "30s",
    },
  },
  thresholds: {
    checks: ["rate>0.99"],
  },
};

const clients = ["client-enterprise-1", "client-enterprise-2"];

export default function () {
  const client = clients[__VU % clients.length];
  const res = http.get(`${baseUrl}/v1/shipments`, {
    headers: { "X-Client-Id": client },
  });
  check(res, statusOkOr429);
}
