/*
 * Two behaviours, and nothing else: the rule explorer on the flag page and the
 * print button on the counsel page. No network, no storage, no dependencies.
 *
 * `verdict` restates serenata/classify/single_bid_in_segment.py for a reader who
 * wants to move the numbers. It is not the rule; the rule is the Python module.
 * tests/test_site.py runs this function and the Python one over the same grid
 * and fails if they ever disagree, which is the only thing that keeps a page
 * describing a rule from describing a different one.
 */
(function () {
  "use strict";

  /* Whole-number percentage to one decimal place, rounded half up, computed in
     integers so it matches serenata/site/figures.py and never shows 0.30000004. */
  function percent(part, whole) {
    if (whole <= 0) return "0.0";
    var scaled = Math.floor((2000 * part + whole) / (2 * whole));
    return Math.floor(scaled / 10) + "." + (scaled % 10);
  }

  function verdict(bids, size, singles, floor, ratePercent) {
    if (bids !== 1) return "not-single";
    if (size < floor) return "below-floor";
    if (!(size >= floor && singles * 100 < ratePercent * size)) return "ordinary";
    return "flagged";
  }

  if (typeof module !== "undefined" && module.exports) {
    module.exports = { verdict: verdict, percent: percent };
    return;
  }

  function integer(input) {
    var value = parseInt(input.value, 10);
    return isNaN(value) || value < 0 ? 0 : value;
  }

  function explorer(root) {
    var floor = parseInt(root.getAttribute("data-floor"), 10);
    var rate = parseInt(root.getAttribute("data-rate"), 10);
    var bids = root.querySelector('[name="bids"]');
    var size = root.querySelector('[name="size"]');
    var singles = root.querySelector('[name="singles"]');
    var line = root.querySelector("[data-rate-line]");
    var result = root.querySelector("[data-verdict]");
    var why = root.querySelector("[data-why]");
    var note = root.querySelector("[data-note]");
    var record = root.querySelector("[data-record]");
    var none = root.querySelector("[data-none]");

    var reasons = {
      flagged:
        "This lot drew one bid, its market has at least " + floor +
        " comparable lot results, and fewer than " + rate + "% of them drew one bid.",
      "not-single": "The rule reads lots that drew exactly one bid. This lot drew a different number.",
      "below-floor":
        "Below " + floor + " lot results the rule stays silent. A rate from so few lots says too little to compare against.",
      ordinary:
        "In this market " + rate + "% or more of lots drew one bid, so one bid is ordinary here.",
    };
    var headline = {
      flagged: "Flagged",
      "not-single": "Not flagged",
      "below-floor": "Not flagged",
      ordinary: "Not flagged",
    };

    function update() {
      var b = integer(bids);
      var n = integer(size);
      var s = integer(singles);
      var notes = [];
      /* The boxes are never rewritten: someone typing "100" over "60" passes
         through "1", and snapping the field to a valid value would fight them.
         What is impossible is corrected in what is shown, and said so. */
      if (b === 1 && s < 1) {
        s = 1;
        notes.push("This lot drew one bid, so at least one lot result in its market did. Counted as 1 single-bid lot.");
      }
      if (s > n) {
        n = s;
        notes.push("A market cannot have fewer lot results than single-bid lots. Counted as " + n + " lot results.");
      }
      var code = verdict(b, n, s, floor, rate);
      line.textContent = s + " of " + n + " lot results in this market drew one bid: " + percent(s, n) + "%.";
      result.textContent = headline[code];
      result.setAttribute("data-code", code);
      why.textContent = reasons[code];
      note.textContent = notes.join(" ");
      note.hidden = notes.length === 0;
      record.hidden = code !== "flagged";
      none.hidden = code === "flagged";
      var fields = record.querySelectorAll("[data-field]");
      for (var i = 0; i < fields.length; i++) {
        var name = fields[i].getAttribute("data-field");
        if (name === "segment_size") fields[i].textContent = n;
        if (name === "segment_single_bids") fields[i].textContent = s;
        if (name === "bids") fields[i].textContent = b;
      }
    }

    root.addEventListener("input", update);
    root.querySelector("form").addEventListener("submit", function (event) {
      event.preventDefault();
    });
    update();
  }

  var roots = document.querySelectorAll("[data-explorer]");
  for (var i = 0; i < roots.length; i++) explorer(roots[i]);

  var printers = document.querySelectorAll("[data-print]");
  for (var j = 0; j < printers.length; j++) {
    printers[j].addEventListener("click", function () {
      window.print();
    });
  }
})();
