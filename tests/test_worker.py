import time
from app.core.worker import Worker


def _wait(w, cond, timeout=2):
    end = time.time() + timeout
    while time.time() < end and not cond():
        w.drain()
        time.sleep(0.01)


def test_result_and_progress():
    w, got = Worker(), {"p": [], "r": None}

    def job(task):
        task.progress(1); task.progress(2)
        return "ok"
    w.submit(job, on_result=lambda r: got.update(r=r), on_progress=got["p"].append)
    _wait(w, lambda: got["r"])
    assert got == {"p": [1, 2], "r": "ok"}


def test_error_delivered():
    w, err = Worker(), []
    w.submit(lambda t: 1 / 0, on_error=err.append)
    _wait(w, lambda: err)
    assert isinstance(err[0], ZeroDivisionError)


def test_cancel_flag():
    w, res = Worker(), []

    def job(task):
        while not task.cancelled.is_set():
            time.sleep(0.01)
        return "cancelled"
    t = w.submit(job, on_result=res.append)
    t.cancel()
    _wait(w, lambda: res)
    assert res == ["cancelled"]
