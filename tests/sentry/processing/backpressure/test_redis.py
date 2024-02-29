from django.test.utils import override_settings

from sentry.processing.backpressure.memory import iter_cluster_memory_usage
from sentry.processing.backpressure.monitor import Redis, load_service_definitions
from sentry.testutils.helpers import override_options
from sentry.testutils.helpers.redis import get_redis_cluster_default_options


@override_settings(SENTRY_PROCESSING_SERVICES={"redis": {"redis": "default"}})
def test_rb_cluster_returns_some_usage() -> None:
    services = load_service_definitions()
    redis_service = services["redis"]
    assert isinstance(redis_service, Redis)

    usage = [usage for usage in iter_cluster_memory_usage(redis_service.cluster)]
    assert len(usage) > 0
    memory = usage[0]
    assert memory.used > 0
    assert memory.available > 0
    assert 0.0 < memory.percentage < 1.0


@override_settings(SENTRY_PROCESSING_SERVICES={"redis": {"redis": "cluster"}})
@override_options(get_redis_cluster_default_options(id="cluster"))
def test_redis_cluster_cluster_returns_some_usage() -> None:
    services = load_service_definitions()
    redis_service = services["redis"]
    assert isinstance(redis_service, Redis)

    usage = [usage for usage in iter_cluster_memory_usage(redis_service.cluster)]
    assert len(usage) > 0
    memory = usage[0]
    assert memory.used > 0
    assert memory.available > 0
    assert 0.0 < memory.percentage < 1.0
