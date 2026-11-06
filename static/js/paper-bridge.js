// Press adds this script to every paper it serves, before any of the author's markup.
// Once papers are sandboxed they cannot touch the browser's storage or be reached
// directly by the scroll page, so this script:
// - gives the paper an in-memory localStorage, seeded by the scroll page through
//   the frame's name and saved back to it by message, so reading settings survive a reload
//   on the scroll page (on the bare paper URL they last until the page is reloaded),
// - reports the paper's scroll position to the scroll page for its back-to-top button,
// - scrolls to the top when the scroll page asks.
(function () {
  "use strict";
  var PREFIX = "press-settings:";
  var framed = window.parent !== window;
  var saved = {};

  if (typeof window.name === "string" && window.name.indexOf(PREFIX) === 0) {
    try {
      var parsed = JSON.parse(window.name.slice(PREFIX.length));
      if (parsed && typeof parsed === "object") {
        Object.keys(parsed).forEach(function (key) {
          if (typeof parsed[key] === "string") saved[key] = parsed[key];
        });
      }
    } catch (e) {}
  }

  function send(message) {
    if (framed) window.parent.postMessage(message, "*");
  }

  function makeStorage(data, onChange) {
    var has = Object.prototype.hasOwnProperty;
    var storage = {
      getItem: function (key) {
        key = String(key);
        return has.call(data, key) ? data[key] : null;
      },
      setItem: function (key, value) {
        data[String(key)] = String(value);
        onChange();
      },
      removeItem: function (key) {
        delete data[String(key)];
        onChange();
      },
      clear: function () {
        Object.keys(data).forEach(function (key) {
          delete data[key];
        });
        onChange();
      },
      key: function (index) {
        var keys = Object.keys(data);
        return index >= 0 && index < keys.length ? keys[index] : null;
      },
    };
    Object.defineProperty(storage, "length", {
      get: function () {
        return Object.keys(data).length;
      },
    });
    return storage;
  }

  function install(name, storage) {
    try {
      Object.defineProperty(window, name, {
        configurable: true,
        get: function () {
          return storage;
        },
      });
    } catch (e) {}
  }

  // The frame's name also carries the settings to the paper's next page when the
  // paper links to another of its own HTML files inside the frame.
  install(
    "localStorage",
    makeStorage(saved, function () {
      if (!framed) return;
      window.name = PREFIX + JSON.stringify(saved);
      send({ type: "press:settings", settings: saved });
    })
  );
  install("sessionStorage", makeStorage({}, function () {}));

  if (!framed) return;

  var pending = false;
  function reportScroll() {
    pending = false;
    send({ type: "press:scroll", y: Math.max(0, window.scrollY || 0) });
  }
  window.addEventListener(
    "scroll",
    function () {
      if (!pending) {
        pending = true;
        window.requestAnimationFrame(reportScroll);
      }
    },
    { passive: true }
  );

  window.addEventListener("message", function (event) {
    if (event.source !== window.parent) return;
    var message = event.data;
    if (message && message.type === "press:top") {
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  });
})();
