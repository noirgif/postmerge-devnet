from typing import Callable, TypeVar
from time import sleep
import subprocess

T = TypeVar('T')

def retry(func: Callable[..., T | None], *args, **kwargs) -> T | None:
    for delay in [1, 2, 4]:
        try:
            result = func(*args, **kwargs)
            if result:
                return result
        except Exception as e:
            print(e)
        sleep(delay)
    return func(*args, **kwargs)


def check_error(*procs: list[subprocess.Popen | None]) -> int:
    error_value = 0
    for ind, proc_group in enumerate(procs):
        for proc in proc_group:
            if proc is None:
                continue
            name = f'Node {ind} {proc.args[0]}'
            if proc.returncode != 0:
                if proc.poll() is None:
                    print(f"{name} running...")
                else:
                    print(f"{name} ended with error")
                    error_value = proc.returncode
            else:
                print(f"{name} ended successfully")
    return error_value