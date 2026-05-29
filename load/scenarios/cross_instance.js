import http from "k6/http";
import { check } from "k6";

const baseUrl = __ENV.BASE_URL || "http://localhost:8080";

export const options = {
  vus: 20,
  duration: "10s",
};

export default function () {
  const res = http.get(`${baseUrl}/v1/demo`, {
    headers: { "X-Client-Id": "client-free-1" },
  });
  check(res, {
    "status is 200 or 429": (r) => r.status === 200 || r.status === 429,
  });
}
