import http from "k6/http";
import { check } from "k6";
import { baseUrl, statusOkOr429 } from "../common.js";

export const options = {
  scenarios: {
    cross_instance: {
      executor: "constant-arrival-rate",
      rate: Number(__ENV.TARGET_RPS || 50),
      timeUnit: "1s",
      duration: __ENV.DURATION || "15s",
      preAllocatedVUs: 30,
      maxVUs: 100,
    },
  },
  thresholds: {
    checks: ["rate>0.99"],
  },
};

export default function () {
  const res = http.get(`${baseUrl}/v1/demo`, {
    headers: { "X-Client-Id": "client-free-1" },
  });
  check(res, statusOkOr429);
}
