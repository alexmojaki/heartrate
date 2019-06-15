function getLoop(url, done) {
  function get() {
    $.get(url)
      .done(done)
      .always(setTimeout(get, 500));
  }

  $(get);
}

function getHTML(url, id) {
  getLoop(url, function (data) {
    let elem = document.getElementById(id);
    elem.innerHTML = data;
  });
}

let stacktrace = [];

getLoop("/stacktrace/", function (data) {
  let toKeep = 0;
  while (stacktrace[toKeep] !== undefined && JSON.stringify(stacktrace[toKeep]) === JSON.stringify(data[toKeep])) {
    toKeep += 1;
  }
  const $stacktrace = $("#stacktrace");
  $("#stacktrace > div").slice(toKeep).remove();
  data.slice(toKeep).forEach(function (arr) {
    $stacktrace
      .append($("<div/>")
        .append($("<pre/>")
          .append($(arr[4] ? "<a/>" : "<span/>")
            .text(arr.slice(0, 3).join(" : "))
            .attr("href", "/file/?" + $.param({filename:arr[0]}) + "#line-" + arr[1])
          )
        )
        .append($("<pre/>")
          .html(arr[3])
        )
      );
  });
  stacktrace = data;

  $stacktrace[0].style.minHeight = $stacktrace[0].clientHeight + "px";
});
