import re


# noinspection PyShadowingBuiltins
def all(_path):
    return True


def path_contains(*subs):
    def func(path):
        return any(map(path.__contains__, subs))

    return func


def contains_regex(pattern):
    def func(path):
        with open(path) as f:
            code = f.read()
        return bool(re.search(pattern, code))

    return func
