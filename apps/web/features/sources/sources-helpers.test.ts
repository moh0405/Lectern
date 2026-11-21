import { beforeEach, describe, expect, it } from "vitest";
import { describeStep, explainFailure } from "./job-card";
import { forgetJob, loadActiveJobs, rememberJob } from "./job-store";
import { checkUrls, isWebLink } from "./url-card";

describe("checkUrls", () => {
  it("accepts one http(s) link per line and drops duplicates", () => {
    expect(checkUrls("https://a.example/x\n\n  http://b.example \nhttps://a.example/x")).toEqual({
      urls: ["https://a.example/x", "http://b.example"],
      invalid: [],
    });
  });
  it("marks free text and other schemes as invalid lines instead of splitting them into links", () => {
    const check = checkUrls("not a url\nhttps://ok.example\nftp://files.example\nexample.com");
    expect(check.urls).toEqual(["https://ok.example"]);
    expect(check.invalid).toEqual([
      { line: 1, text: "not a url" },
      { line: 3, text: "ftp://files.example" },
      { line: 4, text: "example.com" },
    ]);
  });
  it("requires a real host", () => {
    expect(isWebLink("https://")).toBe(false);
    expect(isWebLink("https://github.com/owner/repo")).toBe(true);
  });
});

describe("job wording", () => {
  it("turns backend progress into plain steps that talk about passages", () => {
    expect(describeStep({ status: "queued", progress: [] })).toBe("Waiting to start…");
    expect(describeStep({ status: "running", progress: ["extracting heaps.pdf"] })).toBe("Step 1 of 2: reading heaps.pdf…");
    expect(describeStep({ status: "running", progress: ["extracting heaps.pdf", "embedding 1 chunks from heaps.pdf"] }))
      .toBe("Step 2 of 2: indexing 1 passage from heaps.pdf…");
  });
  it("explains failures without the raw server message", () => {
    const text = explainFailure("beautifulsoup4 not installed. Add it to requirements.");
    expect(text).toMatch(/cannot read this kind of source/);
    expect(text).not.toMatch(/beautifulsoup/);
    expect(explainFailure("HTTP 404 Not Found")).toMatch(/Nothing was found/);
    expect(explainFailure("something odd")).toMatch(/could not be read/);
  });
});

describe("active job store", () => {
  beforeEach(() => sessionStorage.clear());
  it("remembers running jobs newest first and forgets finished ones", () => {
    rememberJob({ id: "a", label: "a.pdf" });
    rememberJob({ id: "b", label: "b.pdf" });
    expect(loadActiveJobs().map((j) => j.id)).toEqual(["b", "a"]);
    forgetJob("b");
    expect(loadActiveJobs()).toEqual([{ id: "a", label: "a.pdf" }]);
  });
  it("ignores corrupt storage", () => {
    sessionStorage.setItem("lectern-active-jobs", "{nope");
    expect(loadActiveJobs()).toEqual([]);
  });
});
