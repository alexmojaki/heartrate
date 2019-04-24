import inspect
import logging
import sys
import threading
import webbrowser
from collections import defaultdict, deque, Counter
from functools import lru_cache
from itertools import islice, takewhile
from traceback import extract_stack

import pygments
from flask import Flask, render_template, jsonify
# noinspection PyUnresolvedReferences
from pygments.formatters import HtmlFormatter
# noinspection PyUnresolvedReferences
from pygments.lexers import PythonLexer
from werkzeug.routing import PathConverter

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


@lru_cache()
def highlighted_lines(path):
    with open(path) as f:
        code = f.read()

    return list(enumerate(highlight_python(code).splitlines()))


def trace(
        files=files_filters.contains_regex(r'#\s*heartrate'),
        port=9999,
        host='127.0.0.1',
        browser=False,
):
    calling_file = inspect.currentframe().f_back.f_code.co_filename

    @lru_cache(maxsize=None)
    def include_file(path):
        return path == calling_file or files(path)

    thread_ident = threading.get_ident()
    queues = defaultdict(lambda: deque(maxlen=2 ** levels))
    totals = defaultdict(Counter)

    app = Flask(__name__)

    class FileConverter(PathConverter):
        regex = '.*?'

    app.url_map.converters['file'] = FileConverter

    @app.route('/')
    def index():
        return render_template('index.html', files=sorted(queues.keys()))

    @app.route('/file/<file:path>')
    def file_view(path):
        return render_template("file.html", path=path, **file_table_context(path))

    def file_table_context(path):
        queue = queues[path]
        total = len(queue)
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
            for i, _ in highlighted_lines(path)
        ]

        max_ratio = max(map(max, ratios)) or 1

        rows = [
            (
                i + 1,
                totals[path][i + 1] or '',
                reversed([

                    int(round(ratio / max_ratio * 100))
                    for ratio in ratios[i]
                ]),
                line,
            )
            for i, line in highlighted_lines(path)
        ]

        return dict(rows=rows, zip=zip, lightnesses=lightnesses)

    @app.route('/table/<file:path>')
    def file_table_view(path):
        return render_template('file_table.html', **file_table_context(path))

    @app.route('/stacktrace/')
    def stacktrace():
        frame = sys._current_frames()[thread_ident]
        return jsonify([
            (path, *rest, highlight_python(code), include_file(path))
            for path, *rest, code in
            takewhile(
                lambda entry: not (
                        'heartrate' in entry[0]
                        and entry[2] == trace_func.__name__),
                extract_stack(frame)
            )
        ])

    threading.Thread(
        target=lambda: app.run(
            debug=True,
            use_reloader=False,
            host=host,
            port=port,
        ),
    ).start()

    def trace_func(frame, event, _arg):
        filename = frame.f_code.co_filename
        if event == "call":
            if include_file(filename):
                return trace_func

        elif event == "line":
            lineno = frame.f_lineno
            queues[filename].append(lineno)
            totals[filename][lineno] += 1

    sys.settrace(trace_func)
    
    if browser:
        webbrowser.open_new_tab("http://localhost:{port}/file/{calling_file}".format(
            port=port, calling_file=calling_file,
        ))
