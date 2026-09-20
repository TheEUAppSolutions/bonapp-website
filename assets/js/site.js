/* European Apps Solutions — progressive enhancement only.
   Every page works with JavaScript disabled: the theme falls back to the OS
   preference, the app grid renders unfiltered, and reveals are CSS-gated on
   prefers-reduced-motion. Nothing here is required to read the site. */
(function () {
  "use strict";

  var root = document.documentElement;

  /* --- theme toggle: system -> light -> dark -> system --------------------- */

  var ORDER = ["system", "light", "dark"];
  var LABEL = {
    system: "Theme: follows your system. Click for light.",
    light: "Theme: light. Click for dark.",
    dark: "Theme: dark. Click to follow your system."
  };

  function apply(mode) {
    if (mode === "system") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", mode);
    var btn = document.querySelector(".theme-toggle");
    if (btn) {
      btn.setAttribute("aria-label", LABEL[mode]);
      btn.setAttribute("title", LABEL[mode]);
    }
  }

  var stored;
  try { stored = localStorage.getItem("theme"); } catch (e) { stored = null; }
  apply(ORDER.indexOf(stored) > -1 ? stored : "system");

  var toggle = document.querySelector(".theme-toggle");
  if (toggle) {
    toggle.addEventListener("click", function () {
      var current = root.getAttribute("data-theme") || "system";
      var next = ORDER[(ORDER.indexOf(current) + 1) % ORDER.length];
      apply(next);
      try {
        if (next === "system") localStorage.removeItem("theme");
        else localStorage.setItem("theme", next);
      } catch (e) { /* private mode — the choice just won't persist */ }
    });
  }

  /* --- masthead hairline appears once the page has scrolled --------------- */

  var masthead = document.querySelector(".masthead");
  if (masthead) {
    var onScroll = function () {
      masthead.setAttribute("data-stuck", window.scrollY > 8 ? "true" : "false");
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
  }

  /* --- app grid filters --------------------------------------------------- */

  var filterBar = document.querySelector("[data-filters]");
  var grid = document.querySelector("[data-app-grid]");
  if (filterBar && grid) {
    var cards = Array.prototype.slice.call(grid.querySelectorAll("[data-group]"));
    var empty = document.querySelector("[data-empty]");

    filterBar.addEventListener("click", function (event) {
      var btn = event.target.closest(".filter");
      if (!btn) return;

      var group = btn.dataset.group;
      filterBar.querySelectorAll(".filter").forEach(function (b) {
        b.setAttribute("aria-pressed", String(b === btn));
      });

      var shown = 0;
      cards.forEach(function (card) {
        var match = group === "all" || card.dataset.group === group;
        card.hidden = !match;
        if (match) shown++;
      });
      if (empty) empty.hidden = shown > 0;

      // keep the chosen filter in the URL so a filtered shelf can be linked
      var url = new URL(window.location.href);
      if (group === "all") url.searchParams.delete("filter");
      else url.searchParams.set("filter", group);
      history.replaceState(null, "", url);
    });

    var preset = new URL(window.location.href).searchParams.get("filter");
    if (preset) {
      var target = filterBar.querySelector('.filter[data-group="' + CSS.escape(preset) + '"]');
      if (target) target.click();
    }
  }

  /* --- reveal on scroll --------------------------------------------------- */

  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var targets = document.querySelectorAll(".reveal");
  if (reduced || !("IntersectionObserver" in window)) {
    targets.forEach(function (el) { el.classList.add("is-in"); });
  } else {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("is-in");
        io.unobserve(entry.target);
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: .08 });
    targets.forEach(function (el) { io.observe(el); });
  }
})();
