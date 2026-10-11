"""Appendix F: restart only what is tagged healer-eligible=true."""

from unittest.mock import MagicMock

import pytest

from healer.remediate import NotEligible, restart_service


def ecs_with(tags, services=True):
    ecs = MagicMock()
    ecs.describe_services.return_value = {
        "services": [{"serviceArn": "arn:aws:ecs:us-east-1:1:service/c/api"}] if services else []
    }
    ecs.list_tags_for_resource.return_value = {"tags": tags}
    return ecs


def test_a_tagged_service_is_restarted():
    ecs = ecs_with([{"key": "healer-eligible", "value": "true"}])
    out = restart_service(ecs, "c", "api")
    ecs.update_service.assert_called_once_with(cluster="c", service="api", forceNewDeployment=True)
    assert out["applied"] and out["rollback"]() is None


@pytest.mark.parametrize(
    "tags",
    [
        [],
        [{"key": "healer-eligible", "value": "false"}],
        [{"key": "chaos-eligible", "value": "true"}],  # safe to break is not safe to remediate
    ],
)
def test_anything_else_is_refused_before_any_call(tags):
    ecs = ecs_with(tags)
    with pytest.raises(NotEligible):
        restart_service(ecs, "c", "api")
    ecs.update_service.assert_not_called()


def test_an_unknown_service_is_a_lookup_error():
    with pytest.raises(LookupError):
        restart_service(ecs_with([], services=False), "c", "ghost")
