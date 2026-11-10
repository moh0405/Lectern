import { describe, expect, it } from "vitest";
import { ApiError, BUSY_MESSAGE, errorMessage, unwrap } from "./api";

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
