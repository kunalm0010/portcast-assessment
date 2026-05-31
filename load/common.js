// Shared clients and routes aligned with configs/clients.yaml and configs/limits.yaml.
export const baseUrl = __ENV.BASE_URL || "http://localhost:8080";

// Clients aligned with configs/clients.yaml.
export const clients = [
  "client-free-1",
  "client-standard-1",
  "client-enterprise-1",
  "client-enterprise-2",
];

// Enterprise tier without per-client overrides (uses tier/route defaults only).
export const enterpriseDefaultClients = ["client-enterprise-2"];

// Enterprise tier with per-client overrides in clients.yaml.
export const enterpriseOverrideClients = ["client-enterprise-1"];

// Five routes: tier defaults, route overrides, and client override on shipments.
export const routes = [
  "/v1/demo",
  "/v1/search",
  "/v1/shipments",
  "/v1/quotes",
  "/v1/reports",
];

export const hotRoutes = [
  "/v1/demo",
  "/v1/search",
  "/v1/shipments",
  "/v1/quotes",
  "/v1/reports",
];

export function pickRandom(items) {
  return items[Math.floor(Math.random() * items.length)];
}

export function requestGet(route, clientId) {
  return {
    method: "GET",
    url: `${baseUrl}${route}`,
    params: { headers: { "X-Client-Id": clientId } },
  };
}

export function requestPost(route, clientId) {
  return {
    method: "POST",
    url: `${baseUrl}${route}`,
    params: { headers: { "X-Client-Id": clientId } },
  };
}

export function routeRequest(route, clientId) {
  if (route === "/v1/reports") {
    return requestPost(route, clientId);
  }
  return requestGet(route, clientId);
}

export const statusOkOr429 = {
  "status is 200 or 429": (r) => r.status === 200 || r.status === 429,
};

export const statusOk429Or503 = {
  "status is 200, 429, or 503": (r) =>
    r.status === 200 || r.status === 429 || r.status === 503,
};
