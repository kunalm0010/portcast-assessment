import http from "k6/http";
import { check } from "k6";
import { baseUrl, statusOkOr429 } from "../common.js";

export const options = {
  scenarios: {
    burst: {
      executor: "constant-arrival-rate",
      rate: Number(__ENV.BURST_RPS || 100),
      timeUnit: "1s",
      duration: __ENV.DURATION || "2s",
      preAllocatedVUs: 20,
      maxVUs: 50,
    },
  },
  thresholds: {
    checks: ["rate>0.99"],
  },
};

export default function () {
  const res = http.get(`${baseUrl}/v1/demo`, {
    headers: { "X-Client-Id": "client-enterprise-1" },
  });
  check(res, statusOkOr429);
}
