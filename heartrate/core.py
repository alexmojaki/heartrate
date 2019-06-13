import inspect
import logging
import sys
import threading
import webbrowser
from collections import defaultdict, deque, Counter
from functools import lru_cache
from itertools import islice, takewhile
from traceback import extract_stack

from executing_node import Source
import pygments
from flask import Flask, render_template, jsonify, url_for, request
# noinspection PyUnresolvedReferences
from pygments.formatters import HtmlFormatter
# noinspection PyUnresolvedReferences
from pygments.lexers import PythonLexer

from heartrate import files as files_filters

logging.getLogger('werkzeug').setLevel(logging.ERROR)

levels = 10

lightnesses = [
    int((i + 1) * 100 / (levels + 1))
    for i in range(levels + 1)
]


def highlight_python(code):
    return pygments.highlight(
        code,
        PythonLexer(),
        HtmlFormatter(nowrap=True),
    )


def trace(
        files=files_filters.contains_regex(r'#\s*heartrate'),
        port=9999,
        host='127.0.0.1',
        browser=False,
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
        total = len(queue)
        
        tokens = source.asttokens()
        ranges = set()
        for frame in frames_matching(filename):
            try:
                node = Source.executing_node(frame)
            except Exception:
                pass
            else:
                ranges.add(tokens.get_text_range(node))
        highlighted = highlight_ranges(ranges, source.text)
        highlighted = highlight_python(highlighted)
        highlighted = (highlighted
                       .replace(highlight_python(open_sentinel).strip(), "<b>")
                       .replace(highlight_python(close_sentinel).strip(), "</b>")
                       )
        highlighted_lines = list(enumerate(highlighted.splitlines()))
        
        counters = [
            Counter(islice(queue, max(0, total - 2 ** i), total))
            for i in range(levels + 1)
        ]

        ratios = [
            [
                counter[i + 1] / min(2 ** c, total or 1)
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
        return jsonify([
            (path, *rest, code, include_file(path))
            for path, *rest, code in
            takewhile(
                lambda entry: not (
                        'heartrate' in entry[0]
                        and entry[2] == trace_func.__name__),
                extract_stack(current_frame())
            )
        ])

    threading.Thread(
        target=lambda: app.run(
            debug=False,
            host=host,
            port=port,
        ),
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


open_sentinel = "$$heartrate_open$$"
close_sentinel = "$$heartrate_close$$"


def highlight_ranges(ranges, text):
    positions = []

    for start, end in ranges:
        positions.append((start, open_sentinel))
        positions.append((end, close_sentinel))

    # This just makes the loop below simpler
    positions.append((len(text), ''))

    positions.sort()

    parts = []
    start = 0
    for position, part in positions:
        parts.append(text[start:position])
        parts.append(part)
        start = position
    html_body = ''.join(parts)
    return html_body
