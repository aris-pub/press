// Connects a Press page to the paper in #paper-frame through the bridge script Press
// adds to every paper (static/js/paper-bridge.js). The paper may be sandboxed, so
// this never touches the frame's document, only exchanges messages with it.
//
// Settings the paper saves (RSM's typeface, theme, collapsed sections) are kept here,
// in Press's storage under one key per paper, and handed back through the frame's name
// on the next load, before any paper script runs.
(function () {
  "use strict";
  var placeholder = document.getElementById("paper-frame");
  if (!placeholder) return;

  // The name is set before the frame goes into the page. In Chromium and WebKit, a name
  // set on a frame already in the page did not reach the paper after a reload.
  var iframe = placeholder.cloneNode(false);

  var overlay = document.getElementById("iframe-loading");
  var topButton = document.getElementById("top-fab");
  var storageKey = "press-paper-settings:" + iframe.getAttribute("data-settings-key");
  var MAX_SETTINGS_LENGTH = 100000;
  var SCROLL_THRESHOLD = 400;

  function readSettings() {
    try {
      var raw = localStorage.getItem(storageKey);
      if (raw) return JSON.parse(raw) || {};
    } catch (e) {}
    // Before papers had their own store they shared Press's storage, so RSM settings
    // saved back then sit under rsm- keys. Start from those.
    var seeded = {};
    try {
      for (var i = 0; i < localStorage.length; i++) {
        var key = localStorage.key(i);
        if (key && key.indexOf("rsm-") === 0) seeded[key] = localStorage.getItem(key);
      }
    } catch (e) {}
    return seeded;
  }

  function saveSettings(settings) {
    if (!settings || typeof settings !== "object") return;
    var clean = {};
    Object.keys(settings).forEach(function (key) {
      if (typeof settings[key] === "string") clean[key] = settings[key];
    });
    var json = JSON.stringify(clean);
    if (json.length > MAX_SETTINGS_LENGTH) return;
    try {
      localStorage.setItem(storageKey, json);
    } catch (e) {}
  }

  window.addEventListener("message", function (event) {
    if (event.source !== iframe.contentWindow) return;
    var message = event.data;
    if (!message || typeof message !== "object") return;
    if (message.type === "press:settings") {
      saveSettings(message.settings);
    } else if (message.type === "press:scroll" && topButton) {
      topButton.classList.toggle("visible", Number(message.y) > SCROLL_THRESHOLD);
    }
  });

  if (topButton) {
    topButton.addEventListener("click", function () {
      iframe.contentWindow.postMessage({ type: "press:top" }, "*");
    });
  }

  iframe.addEventListener("load", function () {
    if (overlay) overlay.style.display = "none";
    iframe.style.opacity = "1";
  });

  // Listeners first, then the address, so a fast load cannot be missed.
  iframe.name = "press-settings:" + JSON.stringify(readSettings());
  iframe.src = iframe.getAttribute("data-src");
  placeholder.replaceWith(iframe);
})();
