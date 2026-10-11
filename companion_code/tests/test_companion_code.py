import asyncio
import base64
import hashlib
import hmac
import logging
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import anomaly_detector
import correlation_engine
import decision_tree
import failure_observer
import rate_limiter
import signature_validator
from secret_scrubber import SecretScrubber


class AnomalyDetectorTests(unittest.TestCase):
    def test_spike_is_flagged_and_calm_baseline_is_not(self):
        flags = anomaly_detector.detect_anomalies_ema([10, 11, 10, 12, 11, 10, 95, 11, 10])
        self.assertTrue(flags[6])
        self.assertFalse(any(flags[:6]))

    def test_short_series_returns_no_anomalies(self):
        self.assertEqual(anomaly_detector.detect_anomalies_ema([1, 2]), [False, False])


class DecisionTreeTests(unittest.TestCase):
    def test_routes_known_signatures(self):
        c = decision_tree.choose_remediation
        self.assertEqual(c("5xx_spike_post_deploy", 90, has_flag=True), "rollback_feature_flag")
        self.assertEqual(c("5xx_spike_post_deploy", 90), "rollback_git")
        self.assertEqual(c("connection_timeout", 90), "retry_with_backoff")
        self.assertEqual(c("process_unresponsive", 90), "restart")
        self.assertEqual(c("oom_killed", 90), "restart_with_heap_dump")

    def test_low_confidence_unknown_and_invalid_escalate(self):
        c = decision_tree.choose_remediation
        self.assertEqual(c("oom_killed", 39), "escalate_to_human")
        self.assertEqual(c("never_seen", 90), "escalate_to_human")
        self.assertEqual(c("oom_killed", 101), "escalate_to_human")


class SecretScrubberTests(unittest.TestCase):
    def test_scrubs_github_and_aws_secrets(self):
        record = logging.LogRecord(
            "t", logging.INFO, __file__, 1,
            "token ghp_" + "a" * 36 + " key aws_access_key_id=" + "A" * 20, None, None,
        )
        self.assertTrue(SecretScrubber().filter(record))
        self.assertNotIn("ghp_", record.msg)
        self.assertNotIn("aws_access_key_id=AAAA", record.msg)
        self.assertEqual(record.msg.count("[SCRUBBED_SECRET]"), 2)


class SignatureValidatorTests(unittest.TestCase):
    secret = b"s3cret"
    body = '{"action":"opened"}'

    def sign(self, body=None, secret=None):
        digest = hmac.new(secret or self.secret, (body or self.body).encode(), hashlib.sha256).hexdigest()
        return "sha256=" + digest

    def test_valid_signature(self):
        r = signature_validator.validate_signature({"body": self.body}, self.secret, self.sign())
        self.assertEqual(r["statusCode"], 200)

    def test_valid_signature_base64_body(self):
        event = {"body": base64.b64encode(self.body.encode()).decode(), "isBase64Encoded": True}
        r = signature_validator.validate_signature(event, self.secret, self.sign())
        self.assertEqual(r["statusCode"], 200)

    def test_bad_signature_and_missing_prefix_rejected(self):
        bad = signature_validator.validate_signature({"body": self.body}, self.secret, self.sign(secret=b"x"))
        self.assertEqual(bad["statusCode"], 401)
        noprefix = signature_validator.validate_signature({"body": self.body}, self.secret, "abc")
        self.assertEqual(noprefix["statusCode"], 401)

    def test_malformed_and_oversized_payloads(self):
        self.assertEqual(signature_validator.validate_signature({}, self.secret, "x")["statusCode"], 400)
        big = {"body": "a" * (signature_validator.MAX_PAYLOAD_SIZE + 1)}
        self.assertEqual(signature_validator.validate_signature(big, self.secret, "x")["statusCode"], 413)


class RateLimiterTests(unittest.TestCase):
    def test_allows_until_condition_fails(self):
        from botocore.exceptions import ClientError
        client = mock.Mock()
        client.update_item.side_effect = [
            {}, ClientError({"Error": {"Code": "ConditionalCheckFailedException"}}, "UpdateItem")
        ]
        with mock.patch.object(rate_limiter, "get_dynamodb_client", return_value=client):
            self.assertTrue(rate_limiter.check_rate_limit("checkout-service"))
            self.assertFalse(rate_limiter.check_rate_limit("checkout-service"))

    def test_rejects_invalid_service_name_and_fails_closed(self):
        self.assertFalse(rate_limiter.check_rate_limit("bad name!"))
        from botocore.exceptions import ClientError
        client = mock.Mock()
        client.update_item.side_effect = ClientError({"Error": {"Code": "InternalServerError"}}, "UpdateItem")
        with mock.patch.object(rate_limiter, "get_dynamodb_client", return_value=client):
            self.assertFalse(rate_limiter.check_rate_limit("checkout-service"))


class CorrelationEngineTests(unittest.TestCase):
    def test_short_or_constant_series_return_empty(self):
        self.assertEqual(correlation_engine.find_delayed_correlations([1], [1.0] * 5), [])
        self.assertEqual(correlation_engine.find_delayed_correlations([1], [2.0] * 30), [])

    def test_finds_lagged_correlation(self):
        series = [0.0] * 40
        for i in (10, 20, 30):
            series[i + 5] = 10.0
        result = correlation_engine.find_delayed_correlations([10, 20, 30], series, max_lag_minutes=15)
        self.assertTrue(any(lag == 5 and corr > 0.3 for lag, corr, _ in result))


class FailureObserverTests(unittest.TestCase):
    def test_webhook_validation_and_observe(self):
        with self.assertRaises(ValueError):
            failure_observer.FailureObserver("http://example.com/hook")
        obs = failure_observer.FailureObserver("https://hooks.slack.com/services/T/B/X")
        asyncio.run(obs.observe_build(failure_observer.BuildEvent("b1", "failed")))
        asyncio.run(obs.observe_build("not-a-build"))


if __name__ == "__main__":
    unittest.main()
