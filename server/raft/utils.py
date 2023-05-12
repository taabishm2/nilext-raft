from datetime import datetime
from random import randrange


def debug(func):
    def wrapper(*args, **kwargs):
        print(f"[LOG] >>> Calling {func.__name__} with args={args} kwargs={kwargs}")
        result = func(*args, **kwargs)
        print(f"[LOG] <<< {func.__name__} returned {result}")
        return result

    return wrapper


def random_timeout(low, high):
    return randrange(low, high) / 1000


def log_me(log: str):
    # # Add a print lock?
    # # return
    # pass
    #print(f"[LOG]: {datetime.now()} {log}")
    pass
