import fs from "node:fs";
import http from "node:http";
import https from "node:https";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const PROJECT_ROOT = path.resolve(__dirname, "..");
const DEFAULT_HOST = "127.0.0.1";
const DEFAULT_PORT = 5174;
const DEFAULT_API_BASE = "http://127.0.0.1:18030";
const DEFAULT_DIST_DIR = path.join(PROJECT_ROOT, "dist");
const PROXY_TIMEOUT_MS = 300_000;
export const BASIC_AUTH_REALM = "NeoTrade3 Dashboard";

const CONTENT_TYPES = new Map([
  [".css", "text/css; charset=utf-8"],
  [".gif", "image/gif"],
  [".html", "text/html; charset=utf-8"],
  [".ico", "image/x-icon"],
  [".jpeg", "image/jpeg"],
  [".jpg", "image/jpeg"],
  [".js", "application/javascript; charset=utf-8"],
  [".json", "application/json; charset=utf-8"],
  [".map", "application/json; charset=utf-8"],
  [".png", "image/png"],
  [".svg", "image/svg+xml"],
  [".txt", "text/plain; charset=utf-8"],
  [".webp", "image/webp"],
]);

export function parseArgs(argv) {
  const args = {
    host: process.env.NEOTRADE3_FRONTEND_GATEWAY_HOST || DEFAULT_HOST,
    port: Number(process.env.NEOTRADE3_FRONTEND_GATEWAY_PORT || DEFAULT_PORT),
    apiBase: process.env.NEOTRADE3_API_BASE_URL || DEFAULT_API_BASE,
    distDir: process.env.NEOTRADE3_DASHBOARD_DIST || DEFAULT_DIST_DIR,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const flag = argv[index];
    const value = argv[index + 1];
    if (flag === "--host" && value) {
      args.host = value;
      index += 1;
      continue;
    }
    if (flag === "--port" && value) {
      args.port = Number(value);
      index += 1;
      continue;
    }
    if (flag === "--api-base" && value) {
      args.apiBase = value;
      index += 1;
      continue;
    }
    if (flag === "--dist-dir" && value) {
      args.distDir = value;
      index += 1;
      continue;
    }
    throw new Error(`unknown or incomplete argument: ${flag}`);
  }

  if (!Number.isInteger(args.port) || args.port <= 0) {
    throw new Error(`invalid port: ${args.port}`);
  }

  return args;
}

function jsonResponse(response, statusCode, payload) {
  const body = Buffer.from(JSON.stringify(payload, null, 2));
  response.writeHead(statusCode, {
    "Content-Type": "application/json; charset=utf-8",
    "Content-Length": String(body.length),
    "Cache-Control": "no-store",
  });
  response.end(body);
}

export function requireDashboardPassword(password = process.env.DASHBOARD_PASSWORD) {
  if (typeof password !== "string" || password.length === 0) {
    throw new Error("missing required DASHBOARD_PASSWORD for frontend gateway");
  }
  return password;
}

function parseBasicAuthHeader(headerValue) {
  if (typeof headerValue !== "string" || !headerValue.startsWith("Basic ")) {
    return null;
  }

  const encoded = headerValue.slice("Basic ".length).trim();
  if (!encoded) {
    return null;
  }

  let decoded;
  try {
    decoded = Buffer.from(encoded, "base64").toString("utf-8");
  } catch {
    return null;
  }

  const separatorIndex = decoded.indexOf(":");
  if (separatorIndex < 0) {
    return null;
  }

  return {
    username: decoded.slice(0, separatorIndex),
    password: decoded.slice(separatorIndex + 1),
  };
}

function isAuthorizedRequest(request, dashboardPassword) {
  const credentials = parseBasicAuthHeader(request.headers.authorization);
  return credentials !== null && credentials.password === dashboardPassword;
}

function sendUnauthorized(response, method = "GET") {
  const payload = Buffer.from(
    JSON.stringify(
      {
        error: "unauthorized",
      },
      null,
      2,
    ),
  );
  response.writeHead(401, {
    "Content-Type": "application/json; charset=utf-8",
    "Content-Length": String(payload.length),
    "Cache-Control": "no-store",
    "WWW-Authenticate": `Basic realm="${BASIC_AUTH_REALM}"`,
  });
  if (method === "HEAD") {
    response.end();
    return;
  }
  response.end(payload);
}

function safeJoin(rootDir, requestPath) {
  let decodedPath;
  try {
    decodedPath = decodeURIComponent(requestPath.split("?")[0]);
  } catch {
    return null;
  }
  const normalized = path.posix.normalize(decodedPath);
  const withoutLeadingSlash = normalized.replace(/^\/+/, "");
  const target = path.resolve(rootDir, withoutLeadingSlash);
  const relative = path.relative(rootDir, target);
  if (relative.startsWith("..") || path.isAbsolute(relative)) {
    return null;
  }
  return target;
}

function shouldProxy(urlPathname) {
  return (
    urlPathname === "/api" ||
    urlPathname.startsWith("/api/") ||
    urlPathname === "/healthz"
  );
}

function sendFile(response, filePath) {
  fs.stat(filePath, (statError, stat) => {
    if (statError || !stat.isFile()) {
      jsonResponse(response, 404, { error: "static resource not found" });
      return;
    }

    const extension = path.extname(filePath).toLowerCase();
    const contentType =
      CONTENT_TYPES.get(extension) || "application/octet-stream";

    response.writeHead(200, {
      "Content-Type": contentType,
      "Content-Length": String(stat.size),
    });
    const stream = fs.createReadStream(filePath);
    stream.on("error", (error) => {
      jsonResponse(response, 500, { error: String(error) });
    });
    stream.pipe(response);
  });
}

function logProxyResult({ method, path, statusCode, startedAt, detail = null, level = "info" }) {
  const elapsedMs = Number((Date.now() - startedAt).toFixed(0));
  const line = [
    "[gateway-proxy]",
    method,
    path,
    `status=${statusCode}`,
    `elapsed_ms=${elapsedMs}`,
  ];
  if (detail) {
    line.push(`detail=${detail}`);
  }
  const writer = level === "error" ? console.error : console.log;
  writer(line.join(" "));
}

function proxyRequest(request, response, apiBase, upstreamPath) {
  const startedAt = Date.now();
  const method = request.method || "GET";
  const path = request.url || "/";
  const upstreamUrl = new URL(upstreamPath, apiBase);
  const transport = upstreamUrl.protocol === "https:" ? https : http;
  const headers = { ...request.headers };
  delete headers.authorization;
  delete headers.host;
  delete headers.connection;
  delete headers["content-length"];

  const proxyRequestOptions = {
    protocol: upstreamUrl.protocol,
    hostname: upstreamUrl.hostname,
    port: upstreamUrl.port || (upstreamUrl.protocol === "https:" ? 443 : 80),
    method: request.method,
    path: `${upstreamUrl.pathname}${upstreamUrl.search}`,
    headers,
    timeout: PROXY_TIMEOUT_MS,
  };

  const upstream = transport.request(proxyRequestOptions, (upstreamResponse) => {
    const responseHeaders = { ...upstreamResponse.headers };
    delete responseHeaders.connection;
    delete responseHeaders["transfer-encoding"];

    response.writeHead(upstreamResponse.statusCode || 502, responseHeaders);
    upstreamResponse.on("end", () => {
      logProxyResult({
        method,
        path,
        statusCode: upstreamResponse.statusCode || 502,
        startedAt,
      });
    });
    upstreamResponse.pipe(response);
  });

  upstream.on("timeout", () => {
    upstream.destroy(new Error("upstream timeout"));
  });

  upstream.on("error", (error) => {
    logProxyResult({
      method,
      path,
      statusCode: response.headersSent ? response.statusCode || 502 : 503,
      startedAt,
      detail: String(error.message || error),
      level: "error",
    });
    if (!response.headersSent) {
      jsonResponse(response, 503, {
        error: "gateway upstream request failed",
        detail: String(error.message || error),
      });
    } else {
      response.destroy(error);
    }
  });

  request.on("error", (error) => {
    upstream.destroy(error);
  });

  request.pipe(upstream);
}

export function buildServer({ distDir, apiBase, dashboardPassword }) {
  const absoluteDistDir = path.resolve(distDir);
  const requiredDashboardPassword = requireDashboardPassword(dashboardPassword);

  return http.createServer((request, response) => {
    const url = new URL(request.url || "/", "http://127.0.0.1");
    const pathname = url.pathname;

    if (!isAuthorizedRequest(request, requiredDashboardPassword)) {
      sendUnauthorized(response, request.method || "GET");
      return;
    }

    if (pathname === "/_gateway/healthz") {
      jsonResponse(response, 200, {
        service: "neotrade3-frontend-gateway",
        status: "ok",
        dist_dir: absoluteDistDir,
        api_base: apiBase,
      });
      return;
    }

    if (shouldProxy(pathname)) {
      proxyRequest(request, response, apiBase, `${pathname}${url.search}`);
      return;
    }

    if (!["GET", "HEAD"].includes(request.method || "GET")) {
      jsonResponse(response, 405, { error: "method not allowed" });
      return;
    }

    const requestTarget = pathname === "/" ? "/index.html" : pathname;
    let filePath = safeJoin(absoluteDistDir, requestTarget);
    if (!filePath) {
      jsonResponse(response, 400, { error: "invalid path" });
      return;
    }

    const extension = path.extname(filePath);
    if (!extension && pathname !== "/") {
      filePath = path.join(absoluteDistDir, "index.html");
    } else if (!fs.existsSync(filePath)) {
      const assetCandidate = safeJoin(absoluteDistDir, pathname);
      if (assetCandidate && fs.existsSync(assetCandidate)) {
        filePath = assetCandidate;
      } else if (!extension) {
        filePath = path.join(absoluteDistDir, "index.html");
      }
    }

    if (request.method === "HEAD") {
      fs.stat(filePath, (statError, stat) => {
        if (statError || !stat.isFile()) {
          jsonResponse(response, 404, { error: "static resource not found" });
          return;
        }
        const extensionName = path.extname(filePath).toLowerCase();
        const contentType =
          CONTENT_TYPES.get(extensionName) || "application/octet-stream";
        response.writeHead(200, {
          "Content-Type": contentType,
          "Content-Length": String(stat.size),
        });
        response.end();
      });
      return;
    }

    sendFile(response, filePath);
  });
}

export function main(argv = process.argv.slice(2)) {
  const options = parseArgs(argv);
  const server = buildServer(options);

  server.listen(options.port, options.host, () => {
    process.stdout.write(
      `${JSON.stringify(
        {
          service: "neotrade3-frontend-gateway",
          host: options.host,
          port: options.port,
          dist_dir: path.resolve(options.distDir),
          api_base: options.apiBase,
          gateway_healthz: `http://${options.host}:${options.port}/_gateway/healthz`,
          api_healthz_via_gateway: `http://${options.host}:${options.port}/healthz`,
        },
        null,
        2,
      )}\n`,
    );
  });

  const gracefulShutdown = () => {
    server.close(() => {
      process.exit(0);
    });
  };

  process.on("SIGINT", gracefulShutdown);
  process.on("SIGTERM", gracefulShutdown);
}

function isExecutedAsScript() {
  const entry = process.argv[1];
  if (!entry) {
    return false;
  }
  return pathToFileURL(path.resolve(entry)).href === import.meta.url;
}

if (isExecutedAsScript()) {
  try {
    main();
  } catch (error) {
    process.stderr.write(`${error instanceof Error ? error.stack : String(error)}\n`);
    process.exit(1);
  }
}
