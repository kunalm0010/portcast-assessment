import http from "k6/http";
import { check, sleep } from "k6";

const baseUrl = __ENV.BASE_URL || "http://localhost:8080";

export const options = {
  scenarios: {
    baseline: {
      executor: "constant-arrival-rate",
      rate: 100,
      timeUnit: "1s",
      duration: "30s",
      preAllocatedVUs: 50,
      maxVUs: 200,
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.05"],
    http_req_duration: ["p(99)<500"],
  },
};

const clients = [
  "client-free-1",
  "client-standard-1",
  "client-enterprise-1",
];

const routes = ["/v1/demo", "/v1/search", "/v1/shipments"];

export default function () {
  const client = clients[Math.floor(Math.random() * clients.length)];
  const route = routes[Math.floor(Math.random() * routes.length)];
  const res = http.get(`${baseUrl}${route}`, {
    headers: { "X-Client-Id": client },
  });
  check(res, {
    "status is 200 or 429": (r) => r.status === 200 || r.status === 429,
  });
  sleep(0.01);
}
