import inspect
import logging
import sys
import threading
import webbrowser
from collections import defaultdict, deque, Counter
from functools import lru_cache
from itertools import islice

import stack_data
from executing import Source
from flask import Flask, render_template, jsonify, url_for, request
# noinspection PyUnresolvedReferences
from pygments.formatters import HtmlFormatter
from stack_data.utils import _pygmented_with_ranges, iter_stack

from heartrate import files as files_filters

logging.getLogger('werkzeug').setLevel(logging.ERROR)

levels = 10

lightnesses = [
    int((i + 1) * 100 / (levels + 1))
    for i in range(levels + 1)
]


style = stack_data.style_with_executing_node("monokai", "bg:#acf9ff")
formatter = HtmlFormatter(nowrap=True, style=style)


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

    host_is_local = host in ["127.0.0.1", "localhost"]
    if host_is_local:
        app.config["SERVER_NAME"] = "{host}:{port}".format(host=host, port=port)

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

        highlighted_lines = list(enumerate(_pygmented_with_ranges(
            formatter,
            source.text,
            executing_ranges(filename),
        )))
        
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
        )

    @app.route('/table/')
    def file_table_view():
        return render_template('file_table.html', **file_table_context())

    def current_frame():
        return sys._current_frames()[thread_ident]

    def executing_ranges(filename):
        for frame in iter_stack(current_frame()):
            if frame.f_code.co_filename == filename:
                executing = Source.executing(frame)
                if executing.node:
                    yield executing.text_range()

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
    
    if browser and host_is_local:
        with app.app_context():
            url = url_for(
                'file_view',
                filename=calling_file,
            )
        webbrowser.open_new_tab(url)


def queue_counter(queue, n):
    while True:
        try:
            return Counter(islice(queue, max(0, len(queue) - n), len(queue)))
        except RuntimeError:
            pass
