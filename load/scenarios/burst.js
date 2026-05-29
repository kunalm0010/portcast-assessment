import http from "k6/http";
import { check } from "k6";

const baseUrl = __ENV.BASE_URL || "http://localhost:8080";

export const options = {
  scenarios: {
    burst: {
      executor: "shared-iterations",
      vus: 1,
      iterations: 120,
      maxDuration: "5s",
    },
  },
};

export default function () {
  const res = http.get(`${baseUrl}/v1/demo`, {
    headers: { "X-Client-Id": "client-enterprise-1" },
  });
  check(res, {
    "status is 200 or 429": (r) => r.status === 200 || r.status === 429,
  });
}
