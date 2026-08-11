"""
Job-ID tabanli uzun is takibi.

Onceki tasarimda ilerleme uc ayri global sozlukte tutuluyordu
(AGENT_PROGRESS / VIDEO_PROGRESS / CAROUSEL_PROGRESS). Job kimligi olmadigi
icin ayni anda iki is baslatildiginda ikincisi birincinin durumunun ustune
yaziyor, cancel bayragi yanlis ise uygulaniyor ve log listesi karisiyordu.
Sorun UI tarafinda navigasyon kilitlenerek gizlenmisti; yani semptom
bastirilmis, neden durmustu.

Bu modul her isi kendi kimligiyle izler ve "ayni anda tek GPU isi" kuralini
backend'de zorlar. UI kilidine guvenilmez.
"""

import itertools
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Any

# Olusturma sirasi. time.time() cozunurlugu (Windows'ta ~15ms) iki isin ayni
# damgayi almasina izin veriyor; o durumda "en son is" belirsiz kaliyordu.
_SEQUENCE = itertools.count()

# Bir iste tutulacak en fazla log satiri. Uzun kosularda sinirsiz buyumeyi
# engeller (onceki tasarimda liste hic kirpilmiyordu).
MAX_LOG_LINES = 500

# Bitmis isler bu sure sonunda kayittan dusurulur.
FINISHED_JOB_TTL_SECONDS = 3600

# Devam ediyor sayilan durumlar.
ACTIVE_STATUSES = {"running", "cancelling"}

JOB_DISPLAY_NAMES = {
    "agent": "Otonom Ajan",
    "carousel": "Carousel",
    "video": "Video",
}


class JobConflict(RuntimeError):
    """Baska bir GPU isi devam ederken yeni is baslatilmak istendi."""

    def __init__(self, active_kind: str, active_job_id: str):
        self.active_kind = active_kind
        self.active_job_id = active_job_id
        super().__init__(f"{display_name(active_kind)} calisiyor. Bitmesini bekle.")


def display_name(kind: str) -> str:
    return JOB_DISPLAY_NAMES.get(kind, kind)


@dataclass
class Job:
    kind: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    status: str = "running"
    stage: str = "starting"
    percent: int = 0
    current_task: str = ""
    result: Any = None
    error: str | None = None
    cancel_requested: bool = False
    seq: int = field(default_factory=lambda: next(_SEQUENCE))
    created_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    _logs: deque = field(default_factory=lambda: deque(maxlen=MAX_LOG_LINES))

    @property
    def is_active(self) -> bool:
        return self.status in ACTIVE_STATUSES

    def log(self, message: str) -> None:
        timestamp = time.strftime("%H:%M:%S")
        self._logs.append(f"[{timestamp}] {message}")

    @property
    def logs(self) -> list[str]:
        return list(self._logs)

    def set_stage(self, stage: str, percent: int, task: str) -> None:
        self.stage = stage
        self.percent = max(0, min(100, int(percent)))
        self.current_task = task

    def finish(self, status: str, *, task: str = "", error: str | None = None, result: Any = None) -> None:
        self.status = status
        self.stage = status
        self.finished_at = time.time()
        if status == "done":
            self.percent = 100
        if task:
            self.current_task = task
        if error is not None:
            self.error = error
        if result is not None:
            self.result = result

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.id,
            "kind": self.kind,
            "status": self.status,
            "stage": self.stage,
            "percent": self.percent,
            "current_task": self.current_task,
            "result": self.result,
            "error": self.error,
            "cancel_requested": self.cancel_requested,
            "logs": self.logs,
        }


# Bos kayit icin dondurulen sabit cevap. UI ilk aciliste bunu gorur.
IDLE_SNAPSHOT: dict[str, Any] = {
    "job_id": None,
    "kind": None,
    "status": "idle",
    "stage": "idle",
    "percent": 0,
    "current_task": "",
    "result": None,
    "error": None,
    "cancel_requested": False,
    "logs": [],
}


class JobRegistry:
    """
    Is kayitlarini tutar ve "ayni anda tek GPU isi" kuralini zorlar.

    Thread-safe: FastAPI BackgroundTasks isleri ayri thread'lerde calistirir.
    """

    def __init__(self, *, ttl_seconds: int = FINISHED_JOB_TTL_SECONDS):
        self._jobs: dict[str, Job] = {}
        self._lock = threading.RLock()
        self._ttl = ttl_seconds

    def create(self, kind: str) -> Job:
        """
        Yeni is olusturur.

        Baska bir is devam ediyorsa JobConflict firlatir; bu kural UI'da degil
        burada zorlanir, cunku tek GPU'yu iki is paylasamaz.
        """
        with self._lock:
            self._prune_locked()
            active = self._active_locked()
            if active is not None:
                raise JobConflict(active.kind, active.id)

            job = Job(kind=kind)
            self._jobs[job.id] = job
            return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def active(self) -> Job | None:
        with self._lock:
            return self._active_locked()

    def latest(self, kind: str | None = None) -> Job | None:
        """En son olusturulan isi dondurur (kind verilirse o turden)."""
        with self._lock:
            candidates = [j for j in self._jobs.values() if kind is None or j.kind == kind]
            if not candidates:
                return None
            # created_at degil seq: ayni tikta olusan isler icin deterministik.
            return max(candidates, key=lambda j: j.seq)

    def snapshot(self, job_id: str | None = None, *, kind: str | None = None) -> dict[str, Any]:
        """
        UI icin durum sozlugu.

        job_id verilirse o is, verilmezse ilgili turun en son isi dondurulur.
        Hicbiri yoksa idle cevabi doner (UI'nin cokmemesi icin).
        """
        job = self.get(job_id) if job_id else self.latest(kind)
        if job is None:
            return dict(IDLE_SNAPSHOT)
        return job.to_dict()

    def request_cancel(self, job_id: str | None = None, *, kind: str | None = None) -> Job | None:
        """
        Isbirlikci iptal ister. Iptal edilecek is bulunamazsa None doner.
        """
        with self._lock:
            job = self.get(job_id) if job_id else self.latest(kind)
            if job is None or not job.is_active:
                return None
            job.cancel_requested = True
            job.status = "cancelling"
            job.stage = "cancelling"
            job.current_task = "Iptal istendi. Guvenli durma bekleniyor..."
            return job

    def prune(self) -> int:
        with self._lock:
            return self._prune_locked()

    def clear(self) -> None:
        """Yalnizca testler icin."""
        with self._lock:
            self._jobs.clear()

    # -- lock icinde cagrilan yardimcilar --

    def _active_locked(self) -> Job | None:
        for job in self._jobs.values():
            if job.is_active:
                return job
        return None

    def _prune_locked(self) -> int:
        cutoff = time.time() - self._ttl
        expired = [
            job_id
            for job_id, job in self._jobs.items()
            if not job.is_active and (job.finished_at or job.created_at) < cutoff
        ]
        for job_id in expired:
            del self._jobs[job_id]
        return len(expired)


# Uygulama genelinde tek kayit defteri.
registry = JobRegistry()
