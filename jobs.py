"""Single-slot background job manager for generate/send actions.

Only one job runs at a time — both actions write to the same JSON files,
so serializing keeps state consistent. Events are buffered on the job and
also fanned out to live subscribers (SSE clients).
"""
import threading
import time
import uuid
from queue import Queue


class JobManager:
    def __init__(self):
        self._current = None
        self._lock = threading.Lock()

    def start(self, target_fn, label: str) -> str:
        """target_fn must accept (on_progress, should_stop) — on_progress(event)
        emits an event, should_stop() returns True once cancel was requested.
        """
        with self._lock:
            if self._current and self._current["status"] == "running":
                raise RuntimeError("A job is already running.")

            cancel_event = threading.Event()
            job = {
                "id": uuid.uuid4().hex[:8],
                "label": label,
                "status": "running",
                "started_at": time.time(),
                "ended_at": None,
                "events": [],
                "subscribers": [],
                "result": None,
                "error": None,
                "cancel_event": cancel_event,
            }
            self._current = job

        def runner():
            def on_progress(event):
                event = {**event, "ts": time.time()}
                job["events"].append(event)
                for q in list(job["subscribers"]):
                    try:
                        q.put_nowait(event)
                    except Exception:
                        pass

            def should_stop():
                return cancel_event.is_set()

            try:
                job["result"] = target_fn(on_progress, should_stop)
                job["status"] = "cancelled" if cancel_event.is_set() else "finished"
            except Exception as e:
                job["error"] = str(e)
                job["status"] = "failed"
                err = {"type": "error", "message": str(e), "ts": time.time()}
                job["events"].append(err)
                for q in list(job["subscribers"]):
                    try:
                        q.put_nowait(err)
                    except Exception:
                        pass
            finally:
                job["ended_at"] = time.time()
                # Sentinel None = stream end
                for q in list(job["subscribers"]):
                    try:
                        q.put_nowait(None)
                    except Exception:
                        pass

        threading.Thread(target=runner, daemon=True, name=f"job-{job['id']}").start()
        return job["id"]

    def current(self):
        return self._current

    def get(self, job_id: str):
        if self._current and self._current["id"] == job_id:
            return self._current
        return None

    def cancel(self, job_id: str) -> bool:
        """Signal the running job to stop at the next safe checkpoint.
        Returns True if the cancel was accepted."""
        job = self.get(job_id)
        if not job or job["status"] != "running":
            return False
        job["cancel_event"].set()
        # Nudge a cancel event into the stream so UI sees it immediately.
        evt = {"type": "info", "message": "Annulation demandée…", "ts": time.time()}
        job["events"].append(evt)
        for q in list(job["subscribers"]):
            try:
                q.put_nowait(evt)
            except Exception:
                pass
        return True

    def subscribe(self, job_id: str):
        """Return a Queue that receives events + a None sentinel at the end."""
        job = self.get(job_id)
        if not job:
            return None
        q = Queue()
        # Replay already-buffered events first so late subscribers don't miss anything.
        for event in list(job["events"]):
            q.put_nowait(event)
        if job["status"] != "running":
            q.put_nowait(None)
        else:
            job["subscribers"].append(q)
        return q


job_manager = JobManager()
