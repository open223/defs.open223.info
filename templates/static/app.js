/* Search, permalinks and lazy syntax highlighting for the 223P definitions page.
 *
 * The page ships ~900 definition cards, so the work here is deliberately spread
 * out: Turtle blocks are highlighted only as they approach the viewport, the
 * search index is built once off the critical path, and filtering toggles a
 * single class per card and touches nothing else.
 *
 * Two URL forms address a definition:
 *   #<id>       scroll to it and mark it, leaving the rest of the page in place
 *   ?only=<id>  show that definition on its own
 * Either one warns at the top of the page when the id no longer exists. */

(function () {
  "use strict";

  var FILTER_DEBOUNCE_MS = 120;
  // Safari rate-limits replaceState, so the URL lags behind the filter.
  var URL_DEBOUNCE_MS = 400;
  // Start highlighting a card's Turtle well before it is scrolled into view.
  var HIGHLIGHT_MARGIN = "800px 0px";
  // Per-frame budget for highlighting, to keep scrolling smooth.
  var FRAME_BUDGET_MS = 8;

  var search = document.getElementById("search");
  var status = document.getElementById("status");
  var showAll = document.getElementById("show-all");
  var warning = document.getElementById("warning");
  var warningText = document.getElementById("warning-text");
  var warningSearch = document.getElementById("warning-search");
  var warningDismiss = document.getElementById("warning-dismiss");
  var definitions = document.getElementById("definitions");

  var cards = Array.prototype.slice.call(definitions.getElementsByClassName("card"));
  var cardById = new Map(
    cards.map(function (card) {
      return [card.id, card];
    })
  );

  // Searching and isolating are mutually exclusive views of the list.
  var query = "";
  var only = null;
  var target = null;
  var missingId = null;

  /* ------------------------------------------------------------ search index */

  // Two lowercased haystacks per card, kept apart so a match can be ranked by
  // where it was found: nameIndex is the heading, id and URI; bodyIndex is the
  // Turtle. Built from named parts rather than card.textContent so the card's
  // own injected chrome ("Show only this") is never searchable text.
  var nameIndex = null;
  var bodyIndex = null;
  var ready = false;

  function text(card, selector) {
    var el = card.querySelector(selector);
    return el ? el.textContent : "";
  }

  // Building it is what the search box waits on, so this also lifts the
  // disabled state. Cheap enough to run inline when a ?q= URL needs it now.
  function ensureIndex() {
    if (nameIndex === null) {
      nameIndex = new Array(cards.length);
      bodyIndex = new Array(cards.length);
      for (var i = 0; i < cards.length; i++) {
        var card = cards[i];
        nameIndex[i] = (
          card.id + " " + text(card, ".permalink") + " " + text(card, ".uri a")
        ).toLowerCase();
        bodyIndex[i] = text(card, "pre").toLowerCase();
      }
      ready = true;
      search.disabled = false;
    }
  }

  function terms(text) {
    return text.toLowerCase().split(/\s+/).filter(Boolean);
  }

  /* ---------------------------------------------------------------- rendering */

  function render() {
    var words = terms(query);
    var visible = 0;
    var named = 0;
    var i;

    if (only !== null) {
      for (i = 0; i < cards.length; i++) {
        cards[i].classList.toggle("filtered-out", cards[i].id !== only);
        cards[i].classList.remove("rank-body");
      }
      visible = cardById.has(only) ? 1 : 0;
    } else if (words.length === 0) {
      for (i = 0; i < cards.length; i++) {
        cards[i].classList.remove("filtered-out");
        cards[i].classList.remove("rank-body");
      }
      visible = cards.length;
    } else {
      ensureIndex();
      for (i = 0; i < cards.length; i++) {
        var name = nameIndex[i];
        var body = bodyIndex[i];
        // A name match needs every term in the heading/id/URI. Anything else
        // that matches only does so with help from the Turtle body.
        var inName = true;
        var matched = true;
        for (var w = 0; w < words.length; w++) {
          var hitName = name.indexOf(words[w]) !== -1;
          if (!hitName) inName = false;
          if (!hitName && body.indexOf(words[w]) === -1) {
            matched = false;
            break;
          }
        }
        cards[i].classList.toggle("filtered-out", !matched);
        // CSS `order` groups the two tiers without moving any DOM nodes;
        // document order is preserved within each tier.
        cards[i].classList.toggle("rank-body", matched && !inName);
        if (matched) {
          visible++;
          if (inName) named++;
        }
      }
    }

    showAll.hidden = only === null && words.length === 0;

    if (only !== null) {
      var card = cardById.get(only);
      status.textContent = card
        ? "Showing only “" + cardLabel(card) + "”"
        : "Showing no definitions";
    } else if (!ready) {
      status.textContent = "Building search index…";
    } else if (words.length === 0) {
      status.textContent = cards.length + " definitions";
    } else if (visible === 0) {
      status.textContent = "No definitions match “" + query + "”";
    } else {
      status.textContent =
        "Showing " + visible + " of " + cards.length + " definitions" +
        (named && named < visible ? " · " + named + " name matches first" : "");
    }
  }

  function cardLabel(card) {
    var heading = card.querySelector(".permalink");
    return heading ? heading.textContent.trim() : card.id;
  }

  /* --------------------------------------------------------------- URL state */

  function syncUrl(replace) {
    var url = new URL(window.location.href);
    if (query) {
      url.searchParams.set("q", query);
    } else {
      url.searchParams.delete("q");
    }
    if (only !== null) {
      url.searchParams.set("only", only);
    } else {
      url.searchParams.delete("only");
    }
    if (replace === false) {
      window.history.pushState(null, "", url);
    } else {
      window.history.replaceState(null, "", url);
    }
  }

  function readUrl() {
    var params = new URL(window.location.href).searchParams;
    only = params.get("only");
    query = params.get("q") || "";

    // Firefox restores form values across a reload, so prefer a restored value
    // over an empty URL rather than silently clearing the box.
    if (!query && search.value) query = search.value;
    search.value = query;
  }

  /* ------------------------------------------------------------------ search */

  var filterTimer, urlTimer;

  search.addEventListener("input", function () {
    clearTimeout(filterTimer);
    clearTimeout(urlTimer);
    filterTimer = setTimeout(function () {
      query = search.value;
      only = null; // typing leaves the isolated view
      render();
    }, FILTER_DEBOUNCE_MS);
    urlTimer = setTimeout(syncUrl, URL_DEBOUNCE_MS);
  });

  search.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && search.value) {
      event.preventDefault();
      reset();
    }
  });

  function reset() {
    clearTimeout(filterTimer);
    clearTimeout(urlTimer);
    query = "";
    only = null;
    search.value = "";
    render();
    syncUrl();
  }

  showAll.addEventListener("click", function () {
    reset();
    search.focus();
  });

  function searchFor(text) {
    clearTimeout(filterTimer);
    clearTimeout(urlTimer);
    query = text;
    only = null;
    search.value = text;
    render();
    syncUrl();
    search.focus();
  }

  /* ----------------------------------------------------------------- warnings */

  function showWarning(id) {
    missingId = id;
    warningText.textContent =
      "No definition found for “" + id + "”. It may have been renamed or " +
      "removed since that link was published.";
    warning.hidden = false;
  }

  function hideWarning() {
    missingId = null;
    warning.hidden = true;
  }

  warningDismiss.addEventListener("click", hideWarning);

  warningSearch.addEventListener("click", function () {
    // A stale id often still appears inside another definition's Turtle, so a
    // full-text search is a useful fallback for a broken link.
    var id = missingId;
    hideWarning();
    if (id) searchFor(id);
  });

  /* --------------------------------------------------------------- isolating */

  function isolate(id, replace) {
    query = "";
    only = id;
    search.value = "";
    render();
    syncUrl(replace);
    if (cardById.has(id)) {
      hideWarning();
      window.scrollTo(0, 0);
    } else {
      showWarning(id);
    }
  }

  definitions.addEventListener("click", function (event) {
    var link = event.target.closest(".isolate-link");
    if (!link || event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0) {
      return; // let the browser handle modified clicks normally
    }
    var card = link.closest(".card");
    if (!card) return;
    event.preventDefault();
    isolate(card.id, false);
  });

  window.addEventListener("popstate", function () {
    readUrl();
    render();
    if (only !== null && !cardById.has(only)) {
      showWarning(only);
    } else {
      hideWarning();
    }
  });

  /* -------------------------------------------------------------- permalinks */

  function scrollToCard(card) {
    // Cards use content-visibility, so off-screen heights are only estimated
    // and the first scroll can land short. Re-run it once the real geometry is
    // known, but stop as soon as the reader takes over.
    var cancelled = false;
    var events = ["wheel", "touchstart", "keydown", "mousedown"];

    function cancel() {
      cancelled = true;
    }
    function settle() {
      if (!cancelled) card.scrollIntoView({ block: "start" });
    }

    events.forEach(function (name) {
      window.addEventListener(name, cancel, { once: true, passive: true });
    });

    card.scrollIntoView({ block: "start" });
    requestAnimationFrame(function () {
      requestAnimationFrame(settle);
    });
    setTimeout(function () {
      settle();
      events.forEach(function (name) {
        window.removeEventListener(name, cancel);
      });
    }, 250);
  }

  function focusTarget(id) {
    if (!id) return;

    var card = cardById.get(id);
    if (!card) {
      showWarning(id);
      return;
    }
    hideWarning();

    // A permalink should always land on its definition, even if the current
    // search or isolated view would otherwise hide it.
    if (card.classList.contains("filtered-out")) {
      query = "";
      only = null;
      search.value = "";
      render();
      syncUrl();
    }

    if (target) target.classList.remove("is-target");
    card.classList.add("is-target");
    target = card;

    scrollToCard(card);
  }

  function currentHash() {
    var hash = window.location.hash.slice(1);
    if (!hash) return "";
    try {
      return decodeURIComponent(hash);
    } catch (err) {
      return hash;
    }
  }

  window.addEventListener("hashchange", function () {
    focusTarget(currentHash());
  });

  /* ------------------------------------------ work kept off the critical path */

  var idle = window.requestIdleCallback || function (fn) { return setTimeout(fn, 1); };

  // Spread work across idle periods in short slices, so none of it becomes a
  // long task that blocks the search box.
  function runChunked(items, work) {
    var i = 0;
    function pump() {
      var end = performance.now() + FRAME_BUDGET_MS;
      while (i < items.length && performance.now() < end) work(items[i++]);
      if (i < items.length) idle(pump);
    }
    idle(pump);
  }

  // Injected rather than shipped in the HTML: 905 of these cost ~123 KB and
  // 1,810 elements to parse, for a link that only matters on the few cards
  // actually on screen. Injection happens a full viewport early (see
  // HIGHLIGHT_MARGIN), so the card's height is settled before it is seen.
  function addIsolateLink(card) {
    if (card.querySelector(".card-actions")) return;
    var link = document.createElement("a");
    link.className = "isolate-link";
    link.href = "?only=" + encodeURIComponent(card.id);
    link.textContent = "Show only this";
    var row = document.createElement("p");
    row.className = "card-actions";
    row.appendChild(link);
    var uri = card.querySelector(".uri");
    if (uri) uri.insertAdjacentElement("afterend", row);
    else card.appendChild(row);
  }

  function setupCardActivation() {
    var canHighlight = !!(window.Prism && window.Prism.highlightElement);

    if (typeof IntersectionObserver === "undefined") {
      // No observer: add the links at idle and leave the Turtle unhighlighted.
      // Plain Turtle reads fine, and highlighting ~900 blocks up front is
      // exactly the freeze this page exists to avoid.
      runChunked(cards, addIsolateLink);
      return;
    }

    var queue = [];
    var flushing = false;

    function flush() {
      var end = performance.now() + FRAME_BUDGET_MS;
      while (queue.length && performance.now() < end) {
        window.Prism.highlightElement(queue.shift());
      }
      if (queue.length) {
        requestAnimationFrame(flush);
      } else {
        flushing = false;
      }
    }

    var observer = new IntersectionObserver(
      function (entries) {
        for (var i = 0; i < entries.length; i++) {
          if (!entries[i].isIntersecting) continue;
          var card = entries[i].target;
          observer.unobserve(card);
          addIsolateLink(card);
          if (!canHighlight) continue;
          var code = card.querySelector("code.language-turtle");
          if (!code) continue;
          queue.push(code);
          if (!flushing) {
            flushing = true;
            requestAnimationFrame(flush);
          }
        }
      },
      { rootMargin: HIGHLIGHT_MARGIN }
    );

    // Observe the card, not the <code>: a card skipped by content-visibility
    // still has a layout box, its contents do not. Registration is chunked so
    // 905 observations do not land in one burst while the reader is typing.
    runChunked(cards, function (card) {
      observer.observe(card);
    });
  }

  /* -------------------------------------------------------------------- init */

  readUrl();

  // A ?q= URL needs answers immediately, so pay for the index up front;
  // otherwise leave the box disabled and build it once the page is idle.
  if (query) ensureIndex();
  render();

  if (only !== null && !cardById.has(only)) showWarning(only);

  if (!ready) {
    idle(function () {
      ensureIndex();
      render();
    });
  }

  idle(setupCardActivation);
  focusTarget(currentHash());
})();
