import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "../src/api/client";
import { overview } from "./fixtures";

afterEach(() => vi.unstubAllGlobals());

describe("API client", () => {
  it("validates and returns a typed overview", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(overview), { status: 200 })));
    await expect(api.overview()).resolves.toEqual(overview);
  });

  it("normalises API errors with request correlation", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "Demo unavailable" }), { status: 503, headers: { "x-request-id": "request-1" } })));
    await expect(api.overview()).rejects.toMatchObject({ name: "ApiError", message: "Demo unavailable", status: 503, requestId: "request-1" });
  });

  it("rejects contract drift", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ context }), { status: 200 })));
    await expect(api.overview()).rejects.toThrow();
  });
});

const context = { fictional_data: true, organisation: "Northstar Clinics", declaration: "Fictional", artefact_fingerprint: "x" };
