import inspect
import logging
import sys
import threading
import webbrowser
from collections import defaultdict, deque, Counter
from functools import lru_cache
from itertools import islice

import pygments
import stack_data
from executing import Source
from flask import Flask, render_template, jsonify, url_for, request
# noinspection PyUnresolvedReferences
from pygments.formatters import HtmlFormatter
# noinspection PyUnresolvedReferences
from pygments.lexers import Python3Lexer

from heartrate import files as files_filters

logging.getLogger('werkzeug').setLevel(logging.ERROR)

levels = 10

lightnesses = [
    int((i + 1) * 100 / (levels + 1))
    for i in range(levels + 1)
]


lexer = Python3Lexer()
style = stack_data.style_with_executing_node("monokai", "bg:#acf9ff")
formatter = HtmlFormatter(nowrap=True, style=style)


def highlight_python(code):
    return pygments.highlight(
        code,
        lexer,
        formatter,
    )


def highlight_python_and_ranges(code):
    return (highlight_python(code)
            .replace(highlight_python(open_sentinel).rstrip('\n'), "<b>")
            .replace(highlight_python(close_sentinel).rstrip('\n'), "</b>")
            )


def trace(
        files=files_filters.contains_regex(r'#\s*heartrate'),
        port=9999,
        host='127.0.0.1',
        browser=False,
        daemon=False,
):
    calling_frame = inspect.currentframe().f_back
    calling_file = calling_frame.f_code.co_filename

    @lru_cache(maxsize=None)
    def include_file(path):
        try:
            return path == calling_file or files(path)
        except Exception:
            return False

    thread_ident = threading.get_ident()
    queues = defaultdict(lambda: deque(maxlen=2 ** levels))
    totals = defaultdict(Counter)

    app = Flask(__name__)
    app.config["SERVER_NAME"] = "localhost:{port}".format(port=port)

    @app.route('/')
    def index():
        return render_template('index.html', files=sorted(queues.keys()))

    @app.route('/file/')
    def file_view():
        return render_template("file.html", **file_table_context())

    def file_table_context():
        filename = request.args['filename']
        source = Source.for_filename(filename)
        queue = queues[filename]

        highlighted = highlight_ranges(source, frames_matching(filename))
        highlighted = highlight_python_and_ranges(highlighted)
        highlighted_lines = list(enumerate(highlighted.splitlines()))
        
        counters = [
            queue_counter(queue, 2 ** i)
            for i in range(levels + 1)
        ]

        ratios = [
            [
                counter[i + 1] / min(2 ** c, len(queue) or 1)
                * (c + 1) / levels
                for c, counter in enumerate(counters)
            ]
            for i, _ in highlighted_lines
        ]

        max_ratio = max(map(max, ratios)) or 1

        rows = [
            (
                i + 1,
                totals[filename][i + 1] or '',
                reversed([

                    int(round(ratio / max_ratio * 100))
                    for ratio in ratios[i]
                ]),
                line,
            )
            for i, line in highlighted_lines
        ]

        return dict(
            rows=rows,
            zip=zip,
            lightnesses=lightnesses,
            filename=filename,
            highlighted=highlighted,
        )

    @app.route('/table/')
    def file_table_view():
        return render_template('file_table.html', **file_table_context())

    def current_frame():
        return sys._current_frames()[thread_ident]

    def frames_matching(filename):
        frame = current_frame()
        while frame:
            if frame.f_code.co_filename == filename:
                yield frame
            frame = frame.f_back

    @app.route('/stacktrace/')
    def stacktrace():
        def gen():
            options = stack_data.Options(before=0, after=0, pygments_formatter=formatter)
            frame_infos = stack_data.FrameInfo.stack_data(
                current_frame(),
                options,
                collapse_repeated_frames=False,
            )
            for frame_info in frame_infos:
                filename = frame_info.filename
                name = frame_info.executing.code_qualname()
                if "heartrate" in filename and name.endswith(trace_func.__name__):
                    continue
                yield (
                    filename,
                    frame_info.lineno,
                    name,
                    "\n".join(
                        line.render(pygmented=True)
                        for line in frame_info.lines
                    ),
                    include_file(filename)
                )

        return jsonify(list(gen()))

    threading.Thread(
        target=lambda: app.run(
            debug=False,
            host=host,
            port=port,
        ),
        daemon=daemon,
    ).start()

    with app.app_context():
        url = url_for(
            'file_view',
            filename=calling_file,
        )

    def trace_func(frame, event, _arg):
        filename = frame.f_code.co_filename
        if event == "call":
            if include_file(filename):
                return trace_func

        elif event == "line":
            lineno = frame.f_lineno
            queues[filename].append(lineno)
            totals[filename][lineno] += 1
            Source.lazycache(frame)

    calling_frame.f_trace = trace_func
    sys.settrace(trace_func)
    
    if browser:
        webbrowser.open_new_tab(url)


open_sentinel = " $$heartrate_open$$ "
close_sentinel = " $$heartrate_close$$ "


def highlight_ranges(source, frames):
    text = source.text
    ranges = set()
    for frame in frames:
        executing = Source.executing(frame)
        if executing.node:
            text_range = executing.text_range()
            ranges.add(text_range)
    
    positions = []

    for start, end in ranges:
        positions.append((start, open_sentinel))
        positions.append((end, close_sentinel))
        while True:
            start = text.find('\n', start + 1, end)
            if start == -1:
                break
            positions.append((start, close_sentinel))
            positions.append((start + 1, open_sentinel))

    # This just makes the loop below simpler
    positions.append((len(text), ''))

    positions.sort()

    parts = []
    start = 0
    for position, part in positions:
        parts.append(text[start:position])
        parts.append(part)
        start = position
    return ''.join(parts)


def queue_counter(queue, n):
    while True:
        try:
            return Counter(islice(queue, max(0, len(queue) - n), len(queue)))
        except RuntimeError:
            pass
