(function () {
  "use strict";

  function hide(notification) {
    if (!notification || notification.classList.contains("is-hiding")) return;

    notification.classList.add("is-hiding");
    window.setTimeout(function () {
      notification.remove();
    }, 220);
  }

  function syncTop(holder) {
    var header = document.querySelector(".site-header");
    var top = 18;

    if (header) {
      var style = window.getComputedStyle(header);
      var rect = header.getBoundingClientRect();

      if (style.position === "fixed" || style.position === "sticky") {
        top = Math.max(top, Math.ceil(rect.bottom + 14));
      }
    }

    holder.style.setProperty("--system-notification-top", top + "px");
  }

  function init() {
    document.querySelectorAll(".system-notifications").forEach(function (holder) {
      syncTop(holder);

      holder.querySelectorAll(".system-notification").forEach(function (notification) {
        if (notification.dataset.notificationReady === "1") return;
        notification.dataset.notificationReady = "1";

        var close = notification.querySelector(".system-notification__close");
        var timeout = notification.classList.contains("error") || notification.classList.contains("danger")
          ? 10000
          : 7000;
        var timer = window.setTimeout(function () {
          hide(notification);
        }, timeout);

        if (close) {
          close.addEventListener("click", function () {
            window.clearTimeout(timer);
            hide(notification);
          });
        }
      });
    });
  }

  document.addEventListener("DOMContentLoaded", init);
  window.addEventListener("resize", function () {
    document.querySelectorAll(".system-notifications").forEach(syncTop);
  });
})();
