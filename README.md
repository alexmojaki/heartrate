# heartrate

This library offers a simple real time visualisation of the execution of a Python program:

![demo](https://media.giphy.com/media/H7wUw65MLvHLoX4sMW/giphy.gif)

The numbers on the left are how many times each line has been hit. The bars show the lines that have been hit recently - longer bars mean more hits, lighter colours mean more recent.

Calls that are currently being executed are highlighted thanks to the [`executing`](https://github.com/alexmojaki/executing) library.

It also shows a live stacktrace:

![stacktrace](https://media.giphy.com/media/VIQqY8yyjYkhNfwF29/giphy.gif)

## Installation

`pip install --user heartrate`

Supports Python 3.5+.

## Usage

```python
from heartrate import trace
trace()
```

This will start tracing your program and start a server in a thread so you can view the visualisation in your browser. Open http://localhost:9999/ then click on a file. In the file view, the stacktrace is at the bottom.

In the stacktrace, you can click on stack entries for files that are being traced to open the visualisation for that file at that line. 

### Options

**`files`** determines which files get traced *in addition to the one where `trace` was called*. It must be a callable which accepts one argument: the path to a file, and returns True if the file should be traced. For convenience, a few functions are supplied for use, e.g.:

 ```python
from heartrate import trace, files
trace(files=files.path_contains('my_app', 'my_library'))
```

The supplied functions are:

- `files.all`: trace all files.
- `files.path_contains(*substrings)` trace all files where the path contains any of the given substrings.
- `files.contains_regex(pattern)` trace all files which contain the given regex in the file itself, so you can mark files to be traced in the source code, e.g. with a comment.

The default is to trace files containing the comment "`# heartrate`" (spaces optional).

**`host`**: HTTP host for the server. To run a remote server accessible from anywhere, use `'0.0.0.0'`. Default `'127.0.0.1'`.

**`port`**: HTTP port for the server. Default `9999`.

**`browser`**: if True, automatically opens a browser tab displaying the visualisation for the file where `trace` is called.

### Caveats

`trace` only traces the thread where it is called. To trace multiple threads, you must call it in each thread, with a different port each time.
