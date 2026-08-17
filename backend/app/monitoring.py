import os
import shutil
import time
from dataclasses import dataclass

from prometheus_client import CollectorRegistry, Gauge, generate_latest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models import GenerationJob
from backend.app.schemas import GenerationStatus


STARTED_AT = time.time()


@dataclass(frozen=True)
class SystemSnapshot:
    uptime_seconds: int
    load_1m: float
    load_5m: float
    load_15m: float
    cpu_count: int
    memory_total_bytes: int
    memory_available_bytes: int
    memory_used_percent: float
    disk_total_bytes: int
    disk_free_bytes: int
    disk_used_percent: float
    jobs_queued: int
    jobs_generating: int
    jobs_completed: int
    jobs_failed: int
    jobs_cancelled: int
    worker: dict[str, object] | None = None


def collect_system_snapshot(db: Session, worker_health: dict[str, object] | None = None) -> SystemSnapshot:
    load_1m, load_5m, load_15m = os.getloadavg()
    memory = _memory_info()
    disk = shutil.disk_usage("/")
    job_counts = _job_counts(db)
    return SystemSnapshot(
        uptime_seconds=int(time.time() - STARTED_AT),
        load_1m=round(load_1m, 3),
        load_5m=round(load_5m, 3),
        load_15m=round(load_15m, 3),
        cpu_count=os.cpu_count() or 1,
        memory_total_bytes=memory["MemTotal"],
        memory_available_bytes=memory["MemAvailable"],
        memory_used_percent=round((1 - memory["MemAvailable"] / memory["MemTotal"]) * 100, 2),
        disk_total_bytes=disk.total,
        disk_free_bytes=disk.free,
        disk_used_percent=round((1 - disk.free / disk.total) * 100, 2),
        jobs_queued=job_counts.get(GenerationStatus.queued.value, 0),
        jobs_generating=job_counts.get(GenerationStatus.generating.value, 0),
        jobs_completed=job_counts.get(GenerationStatus.completed.value, 0),
        jobs_failed=job_counts.get(GenerationStatus.failed.value, 0),
        jobs_cancelled=job_counts.get(GenerationStatus.cancelled.value, 0),
        worker=worker_health,
    )


def prometheus_metrics(snapshot: SystemSnapshot) -> bytes:
    registry = CollectorRegistry()
    gauges = {
        "flux_api_uptime_seconds": Gauge("flux_api_uptime_seconds", "API process uptime", registry=registry),
        "flux_system_load_1m": Gauge("flux_system_load_1m", "System load average over 1 minute", registry=registry),
        "flux_system_load_5m": Gauge("flux_system_load_5m", "System load average over 5 minutes", registry=registry),
        "flux_system_load_15m": Gauge("flux_system_load_15m", "System load average over 15 minutes", registry=registry),
        "flux_system_cpu_count": Gauge("flux_system_cpu_count", "CPU count", registry=registry),
        "flux_system_memory_used_percent": Gauge("flux_system_memory_used_percent", "Memory used percent", registry=registry),
        "flux_system_disk_used_percent": Gauge("flux_system_disk_used_percent", "Root disk used percent", registry=registry),
        "flux_jobs_queued": Gauge("flux_jobs_queued", "Queued generation jobs", registry=registry),
        "flux_jobs_generating": Gauge("flux_jobs_generating", "Generating jobs", registry=registry),
        "flux_jobs_completed": Gauge("flux_jobs_completed", "Completed jobs", registry=registry),
        "flux_jobs_failed": Gauge("flux_jobs_failed", "Failed jobs", registry=registry),
        "flux_jobs_cancelled": Gauge("flux_jobs_cancelled", "Cancelled jobs", registry=registry),
        "flux_worker_online": Gauge("flux_worker_online", "GPU worker health task reachable", registry=registry),
    }
    gauges["flux_api_uptime_seconds"].set(snapshot.uptime_seconds)
    gauges["flux_system_load_1m"].set(snapshot.load_1m)
    gauges["flux_system_load_5m"].set(snapshot.load_5m)
    gauges["flux_system_load_15m"].set(snapshot.load_15m)
    gauges["flux_system_cpu_count"].set(snapshot.cpu_count)
    gauges["flux_system_memory_used_percent"].set(snapshot.memory_used_percent)
    gauges["flux_system_disk_used_percent"].set(snapshot.disk_used_percent)
    gauges["flux_jobs_queued"].set(snapshot.jobs_queued)
    gauges["flux_jobs_generating"].set(snapshot.jobs_generating)
    gauges["flux_jobs_completed"].set(snapshot.jobs_completed)
    gauges["flux_jobs_failed"].set(snapshot.jobs_failed)
    gauges["flux_jobs_cancelled"].set(snapshot.jobs_cancelled)
    gauges["flux_worker_online"].set(1 if snapshot.worker else 0)
    _add_gpu_metrics(registry, snapshot.worker)
    return generate_latest(registry)


def _add_gpu_metrics(registry: CollectorRegistry, worker: dict[str, object] | None) -> None:
    gpu_util = Gauge("flux_gpu_utilization_percent", "GPU utilization percent", ["index", "name"], registry=registry)
    gpu_mem_used = Gauge("flux_gpu_memory_used_mib", "GPU memory used MiB", ["index", "name"], registry=registry)
    gpu_mem_total = Gauge("flux_gpu_memory_total_mib", "GPU memory total MiB", ["index", "name"], registry=registry)
    gpu_temp = Gauge("flux_gpu_temperature_c", "GPU temperature Celsius", ["index", "name"], registry=registry)
    gpu_power = Gauge("flux_gpu_power_draw_w", "GPU power draw watts", ["index", "name"], registry=registry)
    if not worker:
        return
    gpus = worker.get("gpus")
    if not isinstance(gpus, list):
        return
    for gpu in gpus:
        if not isinstance(gpu, dict):
            continue
        index = str(gpu.get("index", "unknown"))
        name = str(gpu.get("name", "unknown"))
        gpu_util.labels(index=index, name=name).set(float(gpu.get("utilization_gpu_percent") or 0))
        gpu_mem_used.labels(index=index, name=name).set(float(gpu.get("memory_used_mib") or 0))
        gpu_mem_total.labels(index=index, name=name).set(float(gpu.get("memory_total_mib") or 0))
        gpu_temp.labels(index=index, name=name).set(float(gpu.get("temperature_c") or 0))
        power = gpu.get("power_draw_w")
        if power is not None:
            gpu_power.labels(index=index, name=name).set(float(power))


def _memory_info() -> dict[str, int]:
    values: dict[str, int] = {}
    with open("/proc/meminfo", encoding="utf-8") as meminfo:
        for line in meminfo:
            key, raw_value = line.split(":", 1)
            if key in {"MemTotal", "MemAvailable"}:
                values[key] = int(raw_value.strip().split()[0]) * 1024
    if "MemAvailable" not in values:
        values["MemAvailable"] = values["MemTotal"]
    return values


def _job_counts(db: Session) -> dict[str, int]:
    rows = db.execute(select(GenerationJob.status, func.count()).group_by(GenerationJob.status)).all()
    return {status: count for status, count in rows}
