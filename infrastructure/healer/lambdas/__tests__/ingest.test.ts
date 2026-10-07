import { handler } from "../ingest/index";
import { APIGatewayProxyEvent } from "aws-lambda";
import { createHmac } from "crypto";
import * as snsClient from "../shared/sns-client";
import * as dynamoClient from "../shared/dynamodb-client";
import { SentryWebhookPayload } from "../shared/types";

jest.mock("../shared/sns-client");
jest.mock("../shared/dynamodb-client");

const mockPublish = jest.spyOn(snsClient, "publishHealerEvent").mockResolvedValue();
const mockRateLimit = jest.spyOn(dynamoClient, "checkAndRecordRateLimit").mockResolvedValue({
  allowed: true,
  count: 1,
});

const makeSentryPayload = (): SentryWebhookPayload => ({
  action: "triggered",
  data: {
    issue: {
      id: "issue-123",
      title: 'TypeError: Cannot read properties of undefined (reading "id")',
      culprit: "src/endpoints/auth/index.ts in registerAuthEndpoints",
      permalink: "https://sentry.io/organizations/your-org/issues/123/",
      level: "error",
      metadata: { value: "Cannot read properties of undefined" },
      project: { slug: "your-api" },
    },
  },
});

const makeEvent = (body: object, headers: Record<string, string> = {}): APIGatewayProxyEvent =>
  ({ body: JSON.stringify(body), headers }) as unknown as APIGatewayProxyEvent;

const computeSignature = (body: string, secret: string): string =>
  createHmac("sha256", secret).update(body, "utf8").digest("hex");

describe("Sentry ingest handler", () => {
  const TEST_SECRET = "test-webhook-secret";

  beforeEach(() => {
    jest.clearAllMocks();
    // Set secret for all non-security-specific tests so signature check passes.
    // Tests in the nested describe override this as needed.
    process.env.SENTRY_WEBHOOK_SECRET = TEST_SECRET;
  });
  afterEach(() => { delete process.env.SENTRY_WEBHOOK_SECRET; });

  const signedEvent = (payload: object) => {
    const body = JSON.stringify(payload);
    const sig = computeSignature(body, TEST_SECRET);
    return { body, headers: { "sentry-hook-signature": sig } } as unknown as APIGatewayProxyEvent;
  };

  it("normalises Sentry payload and publishes to SNS", async () => {
    const result = await handler(signedEvent(makeSentryPayload()));
    expect(result.statusCode).toBe(200);
    expect(mockPublish).toHaveBeenCalledWith(
      expect.objectContaining({
        source: "sentry",
        type: "integration",
        affectedService: "your-api",
      }),
    );
  });

  it("returns 429 when rate limit exceeded", async () => {
    mockRateLimit.mockResolvedValueOnce({ allowed: false, count: 3 });
    const result = await handler(signedEvent(makeSentryPayload()));
    expect(result.statusCode).toBe(429);
    expect(mockPublish).not.toHaveBeenCalled();
  });

  it("returns 400 for invalid body", async () => {
    const body = "not-json";
    const sig = computeSignature(body, TEST_SECRET);
    const result = await handler({
      body,
      headers: { "sentry-hook-signature": sig },
    } as unknown as APIGatewayProxyEvent);
    expect(result.statusCode).toBe(400);
  });

  describe("Sentry webhook signature validation", () => {
    it("accepts request with valid HMAC signature when secret is configured", async () => {
      const payload = makeSentryPayload();
      const body = JSON.stringify(payload);
      const sig = computeSignature(body, TEST_SECRET);
      const result = await handler({
        body,
        headers: { "sentry-hook-signature": sig },
      } as unknown as APIGatewayProxyEvent);
      expect(result.statusCode).toBe(200);
      expect(mockPublish).toHaveBeenCalled();
    });

    it("returns 401 when signature is invalid", async () => {
      const result = await handler({
        body: JSON.stringify(makeSentryPayload()),
        headers: { "sentry-hook-signature": "badc0ffee" },
      } as unknown as APIGatewayProxyEvent);
      expect(result.statusCode).toBe(401);
      expect(mockPublish).not.toHaveBeenCalled();
    });

    it("rejects (401) when SENTRY_WEBHOOK_SECRET is not set — no longer silently accepts", async () => {
      delete process.env.SENTRY_WEBHOOK_SECRET; // override the beforeEach default
      const result = await handler(makeEvent(makeSentryPayload()));
      // Security fix (P2-1): missing secret now rejects rather than passing through
      expect(result.statusCode).toBe(401);
    });
  });
});
