import http from "node:http";
import os from "node:os";
import path from "node:path";
import { mkdtemp, rm, writeFile } from "node:fs/promises";

import { afterEach, describe, expect, it, vi } from "vitest";

import { BASIC_AUTH_REALM, buildServer } from "./gateway.js";

const tempDirs = [];
const servers = [];

async function createDistDir() {
  const distDir = await mkdtemp(path.join(os.tmpdir(), "neotrade3-gateway-test-"));
  tempDirs.push(distDir);
  await writeFile(
    path.join(distDir, "index.html"),
    "<!doctype html><html><body>gateway test page</body></html>",
    "utf-8",
  );
  return distDir;
}

function startServer(server) {
  servers.push(server);
  return new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      server.off("error", reject);
      resolve(server);
    });
  });
}

function closeServer(server) {
  return new Promise((resolve, reject) => {
    server.close((error) => {
      if (error) {
        reject(error);
        return;
      }
      resolve();
    });
  });
}

function serverOrigin(server) {
  const address = server.address();
  if (!address || typeof address === "string") {
    throw new Error("server address is unavailable");
  }
  return `http://127.0.0.1:${address.port}`;
}

function basicAuthHeader(password, username = "user") {
  return `Basic ${Buffer.from(`${username}:${password}`).toString("base64")}`;
}

function httpRequest(url, { method = "GET", headers = {} } = {}) {
  return new Promise((resolve, reject) => {
    const request = http.request(
      url,
      {
        method,
        headers,
      },
      (response) => {
        const chunks = [];
        response.on("data", (chunk) => {
          chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
        });
        response.on("end", () => {
          resolve({
            statusCode: response.statusCode || 0,
            headers: response.headers,
            body: Buffer.concat(chunks).toString("utf-8"),
          });
        });
      },
    );
    request.on("error", reject);
    request.end();
  });
}

afterEach(async () => {
  await Promise.all(servers.splice(0).map((server) => closeServer(server)));
  await Promise.all(tempDirs.splice(0).map((dir) => rm(dir, { recursive: true, force: true })));
});

describe("frontend gateway basic auth", () => {
  it("protects static pages, api proxy, and health endpoints", async () => {
    const distDir = await createDistDir();
    let apiRequestCount = 0;
    let lastAuthorizationHeader = null;
    const upstream = await startServer(
      http.createServer((request, response) => {
        apiRequestCount += 1;
        lastAuthorizationHeader = request.headers.authorization ?? null;
        if (request.url === "/healthz") {
          response.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
          response.end(JSON.stringify({ status: "ok", service: "upstream-api" }));
          return;
        }
        response.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
        response.end(JSON.stringify({ path: request.url, authorization: lastAuthorizationHeader }));
      }),
    );
    const gateway = await startServer(
      buildServer({
        distDir,
        apiBase: serverOrigin(upstream),
        dashboardPassword: "secret-pass",
      }),
    );
    const gatewayOrigin = serverOrigin(gateway);

    const unauthenticatedHome = await httpRequest(`${gatewayOrigin}/`);
    expect(unauthenticatedHome.statusCode).toBe(401);
    expect(unauthenticatedHome.headers["www-authenticate"]).toBe(
      `Basic realm="${BASIC_AUTH_REALM}"`,
    );

    const unauthenticatedApi = await httpRequest(`${gatewayOrigin}/api/example`);
    expect(unauthenticatedApi.statusCode).toBe(401);
    expect(apiRequestCount).toBe(0);

    const wrongPassword = await httpRequest(`${gatewayOrigin}/`, {
      headers: {
        Authorization: basicAuthHeader("wrong-pass"),
      },
    });
    expect(wrongPassword.statusCode).toBe(401);

    const authenticatedHome = await httpRequest(`${gatewayOrigin}/`, {
      headers: {
        Authorization: basicAuthHeader("secret-pass"),
      },
    });
    expect(authenticatedHome.statusCode).toBe(200);
    expect(authenticatedHome.body).toContain("gateway test page");

    const gatewayHealth = await httpRequest(`${gatewayOrigin}/_gateway/healthz`, {
      headers: {
        Authorization: basicAuthHeader("secret-pass"),
      },
    });
    expect(gatewayHealth.statusCode).toBe(200);
    expect(JSON.parse(gatewayHealth.body)).toMatchObject({
      service: "neotrade3-frontend-gateway",
      status: "ok",
    });

    const apiHealth = await httpRequest(`${gatewayOrigin}/healthz`, {
      headers: {
        Authorization: basicAuthHeader("secret-pass"),
      },
    });
    expect(apiHealth.statusCode).toBe(200);
    expect(JSON.parse(apiHealth.body)).toMatchObject({
      service: "upstream-api",
      status: "ok",
    });

    const authenticatedApi = await httpRequest(`${gatewayOrigin}/api/example`, {
      headers: {
        Authorization: basicAuthHeader("secret-pass"),
      },
    });
    expect(authenticatedApi.statusCode).toBe(200);
    expect(JSON.parse(authenticatedApi.body)).toEqual({
      path: "/api/example",
      authorization: null,
    });
    expect(lastAuthorizationHeader).toBeNull();
  });

  it("fails to build the gateway when DASHBOARD_PASSWORD is missing", async () => {
    const distDir = await createDistDir();

    expect(() =>
      buildServer({
        distDir,
        apiBase: "http://127.0.0.1:18030",
        dashboardPassword: "",
      }),
    ).toThrow(/DASHBOARD_PASSWORD/);
  });

  it("logs proxied api request timing", async () => {
    const distDir = await createDistDir();
    const logSpy = vi.spyOn(console, "log").mockImplementation(() => {});
    const upstream = await startServer(
      http.createServer((request, response) => {
        response.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
        response.end(JSON.stringify({ path: request.url }));
      }),
    );
    const gateway = await startServer(
      buildServer({
        distDir,
        apiBase: serverOrigin(upstream),
        dashboardPassword: "secret-pass",
      }),
    );
    const gatewayOrigin = serverOrigin(gateway);

    const response = await httpRequest(`${gatewayOrigin}/api/example`, {
      headers: {
        Authorization: basicAuthHeader("secret-pass"),
      },
    });

    expect(response.statusCode).toBe(200);
    expect(logSpy).toHaveBeenCalledWith(
      expect.stringContaining("[gateway-proxy] GET /api/example status=200 elapsed_ms="),
    );
    logSpy.mockRestore();
  });

  it("rejects malformed encoded static paths without crashing", async () => {
    const distDir = await createDistDir();
    const upstream = await startServer(
      http.createServer((request, response) => {
        response.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
        response.end(JSON.stringify({ path: request.url }));
      }),
    );
    const gateway = await startServer(
      buildServer({
        distDir,
        apiBase: serverOrigin(upstream),
        dashboardPassword: "secret-pass",
      }),
    );
    const gatewayOrigin = serverOrigin(gateway);

    const response = await httpRequest(`${gatewayOrigin}/bad%ZZpath`, {
      headers: {
        Authorization: basicAuthHeader("secret-pass"),
      },
    });

    expect(response.statusCode).toBe(400);
  });
});
