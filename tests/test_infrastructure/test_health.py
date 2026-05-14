import time
from src.infrastructure.health import HealthCheck


def test_health_check_initial_state():
    hc = HealthCheck()
    assert hc.get_unhealthy_agents() == []
    assert hc.get_timed_out_tasks() == []
    assert hc.heartbeat_timeout == 60.0
    assert hc.task_timeout == 600.0


def test_heartbeat_makes_agent_healthy():
    hc = HealthCheck()
    hc.heartbeat("agent_1")
    assert "agent_1" in hc.agent_heartbeats
    assert hc.get_unhealthy_agents() == []


def test_missing_heartbeat_is_unhealthy():
    hc = HealthCheck(heartbeat_timeout=0)  # immediate timeout
    hc.heartbeat("agent_1")
    time.sleep(0.01)
    assert "agent_1" in hc.get_unhealthy_agents()


def test_multiple_agents_health():
    hc = HealthCheck(heartbeat_timeout=60)
    hc.heartbeat("agent_1")
    hc.heartbeat("agent_2")
    hc.heartbeat("agent_3")
    assert len(hc.agent_heartbeats) == 3
    assert hc.get_unhealthy_agents() == []


def test_task_timeout_detection():
    hc = HealthCheck(task_timeout=0)  # immediate timeout
    hc.mark_task_start("task_1")
    time.sleep(0.01)
    assert "task_1" in hc.get_timed_out_tasks()


def test_task_not_timed_out():
    hc = HealthCheck(task_timeout=3600)
    hc.mark_task_start("task_1")
    assert hc.get_timed_out_tasks() == []


def test_combined_health_status():
    hc = HealthCheck(heartbeat_timeout=60, task_timeout=3600)
    hc.heartbeat("agent_1")
    hc.mark_task_start("task_1")
    assert hc.get_unhealthy_agents() == []
    assert hc.get_timed_out_tasks() == []
