import { describe, expect, it } from "vitest";
import {
  ApiError,
  BUSY_MESSAGE,
  DAILY_LIMIT_MESSAGE,
  LLM_UNAVAILABLE_MESSAGE,
  OFFLINE_MESSAGE,
  SERVER_ERROR_MESSAGE,
  describeError,
  errorMessage,
  parseRetryAfter,
  unwrap,
} from "./api";

describe("capacity error guidance", () => {
  it("explains a bare429 from a platform before the API can handle it", () => {
    try { unwrap({ error: {}, response: new Response("", { status:429 }) }); }
    catch(error) { expect(error).toBeInstanceOf(ApiError); expect(errorMessage(error)).toBe(BUSY_MESSAGE); return; }
    throw Error("Expected a capacity error");
  });
  it.each(["429", "429 Too Many Requests", "Rate limit exceeded", "Too Many Requests", ""])("explains generic capacity text: %s", message => {
    expect(errorMessage(new ApiError(429,"rate_limited",message))).toBe(BUSY_MESSAGE);
  });
  it("keeps specific provider quota guidance instead of inventing a short wait", () => {
    const text="The model provider daily quota is used up. Try again tomorrow.";
    expect(errorMessage(new ApiError(429,"quota",text))).toBe(text);
  });
  it("keeps other API failures and successful responses intact", () => {
    expect(errorMessage(new ApiError(403,"disabled_in_demo","Private feature"))).toBe("Private feature");
    expect(unwrap({data:{ok:true},response:new Response()})).toEqual({ok:true});
  });
});

describe("student-facing error wording", () => {
  it("explains an unreachable API without naming the server address", () => {
    const info = describeError(new TypeError("Failed to fetch"));
    expect(info.kind).toBe("offline");
    expect(info.message).toBe(OFFLINE_MESSAGE);
    expect(info.message).not.toMatch(/http|127\.0\.0\.1|backend/);
    expect(info.detail).toContain("Failed to fetch");
  });
  it("says how long to wait when the server sends Retry-After", () => {
    try { unwrap({ error: {}, response: new Response("", { status: 429, headers: { "retry-after": "30" } }) }); }
    catch (error) {
      expect(errorMessage(error)).toBe("The study service is busy right now. Try again in 30 seconds.");
      expect(describeError(error).retryAfter).toBe(30);
      return;
    }
    throw Error("Expected a capacity error");
  });
  it("reads Retry-After as seconds or a date", () => {
    expect(parseRetryAfter("12")).toBe(12);
    expect(parseRetryAfter(new Date(10_000 + 5_000).toUTCString(), 10_000)).toBe(5);
    expect(parseRetryAfter("soon")).toBeUndefined();
    expect(parseRetryAfter(null)).toBeUndefined();
  });
  it("gives the daily limit's reset time", () => {
    const info = describeError(new ApiError(429, "daily_limit", "Daily limit of 200 model calls reached."));
    expect(info).toMatchObject({ kind: "daily_limit", message: DAILY_LIMIT_MESSAGE });
    expect(info.message).toMatch(/resets at midnight UTC/);
  });
  it("never tells a visitor to edit env files when the model is off", () => {
    const info = describeError(new ApiError(503, "llm_unavailable", "GEMINI_API_KEY is not set. Set it in .env"));
    expect(info.message).toBe(LLM_UNAVAILABLE_MESSAGE);
    expect(info.message).not.toMatch(/GEMINI|\.env/);
    expect(info.detail).toContain("GEMINI_API_KEY");
  });
  it("replaces status lines and internal errors with plain words", () => {
    expect(errorMessage(new ApiError(500, "http_error", "500 Internal Server Error"))).toBe(SERVER_ERROR_MESSAGE);
    expect(errorMessage(new ApiError(500, "internal_error", "Internal server error"))).toBe(SERVER_ERROR_MESSAGE);
    expect(errorMessage(new ApiError(503, "agent_unavailable", "The agent needs the 'agent' extra (langgraph) on the server"))).toBe("This feature isn't available on this server right now.");
    expect(errorMessage(new ApiError(404, "http_error", "404 Not Found"))).toMatch(/could not be found/);
  });
  it("shows the field message for validation errors", () => {
    const err = new ApiError(422, "validation_error", "Request validation failed", [{ field: "question", message: "String should have at least 3 characters" }]);
    expect(errorMessage(err)).toBe("Check what you entered in “question”: String should have at least 3 characters.");
  });
  it("keeps specific server messages written for people", () => {
    expect(errorMessage(new ApiError(409, "no_material", "Index some material first"))).toBe("Index some material first");
    expect(errorMessage(new ApiError(422, "invalid_url", "Not a valid http(s) URL: x"))).toBe("Not a valid http(s) URL: x");
  });
});
