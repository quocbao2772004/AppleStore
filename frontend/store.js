(function () {
  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var header = document.querySelector(".top");
  var sentinel = document.getElementById("nav-sentinel");
  if (header && sentinel && "IntersectionObserver" in window) {
    new IntersectionObserver(function (entries) {
      header.classList.toggle("is-scrolled", !entries[0].isIntersecting);
    }, { threshold: 0 }).observe(sentinel);
  } else if (header) {
    header.classList.add("is-scrolled");
  }

  function escText(value) {
    return String(value).replace(/[&<>"]/g, function (char) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[char];
    });
  }

  var search = document.getElementById("nav-search");
  var suggest = document.getElementById("nav-suggest");
  var searchTimer = 0;
  if (search && suggest) {
    search.addEventListener("input", function () {
      var term = search.value.trim();
      window.clearTimeout(searchTimer);
      if (term.length < 1) {
        suggest.hidden = true;
        suggest.innerHTML = "";
        return;
      }
      searchTimer = window.setTimeout(function () {
        fetch("/api/suggest?q=" + encodeURIComponent(term))
          .then(function (response) { return response.json(); })
          .then(function (items) {
            suggest.innerHTML = items.map(function (item) {
              var image = item.image ? '<img src="' + escText(item.image) + '" alt="">' : "";
              return '<a href="/p/' + encodeURIComponent(item.id) + '">' + image + '<strong>' + escText(item.name) + '</strong><span>' + escText(item.price) + '</span></a>';
            }).join("") || '<p class="note" style="padding:12px">Không thấy sản phẩm.</p>';
            suggest.hidden = false;
          });
      }, 150);
    });
    document.addEventListener("click", function (event) {
      if (!search.contains(event.target) && !suggest.contains(event.target)) suggest.hidden = true;
    });
  }

  var familyRow = document.getElementById("family-row");
  document.querySelectorAll("[data-family-dir]").forEach(function (button) {
    button.addEventListener("click", function () {
      if (!familyRow) return;
      familyRow.scrollBy({ left: Number(button.dataset.familyDir) * 280, behavior: reduced ? "auto" : "smooth" });
    });
  });

  document.querySelectorAll(".swatch-btn, .swatches button.swatch").forEach(function (button) {
    button.addEventListener("click", function () {
      var name = button.dataset.colorName;
      var card = button.closest("[data-color-card]");
      if (card) {
        var photo = card.querySelector(".family-photo img");
        if (photo && button.dataset.cutout) {
          photo.src = button.dataset.cutout;
          photo.alt = name;
          photo.dataset.color = name;
        } else if (photo) {
          card.querySelectorAll("img[data-color]").forEach(function (image) {
            image.hidden = image.dataset.color !== name;
          });
        }
      }
      var gallery = document.getElementById("wide-gallery");
      if (!card && !gallery) return;
      if (gallery && !card) {
        gallery.querySelectorAll(".wide-slide").forEach(function (slide) {
          slide.hidden = slide.dataset.color !== name;
        });
      }
      var label = button.parentElement.querySelector(".color-label");
      if (label) label.textContent = name;
      button.parentElement.querySelectorAll("button.swatch").forEach(function (other) {
        other.classList.toggle("on", other === button);
      });
      if (gallery && !card) gallery.scrollTo({ left: 0, behavior: reduced ? "auto" : "smooth" });
    });
  });

  var wide = document.getElementById("wide-gallery");
  document.querySelectorAll("[data-wide-dir]").forEach(function (button) {
    button.addEventListener("click", function () {
      if (!wide) return;
      var slide = wide.querySelector(".wide-slide:not([hidden])");
      var amount = slide ? slide.getBoundingClientRect().width + 16 : 600;
      wide.scrollBy({ left: Number(button.dataset.wideDir) * amount, behavior: reduced ? "auto" : "smooth" });
    });
  });

  if (reduced || !document.body.dataset.home) return;

  var heroPhoto = document.querySelector(".hero-stage");
  var pin = document.querySelector(".pin");
  var current = 0;
  var target = 0;

  function tick() {
    target = window.scrollY || 0;
    current += (target - current) * 0.08;
    if (heroPhoto) {
      var progress = Math.min(Math.max(current / (window.innerHeight || 1), 0), 1);
      heroPhoto.style.transform = "translate3d(0," + (progress * 48).toFixed(2) + "px,0)";
    }
    if (pin) {
      var rect = pin.getBoundingClientRect();
      var span = pin.offsetHeight - window.innerHeight;
      var seen = Math.min(Math.max(-rect.top / (span || 1), 0), 1);
      pin.style.setProperty("--p", seen.toFixed(4));
    }
    requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
})();

(function () {
  var pop = document.getElementById("assistant");
  var opener = document.getElementById("open-assistant");
  var log = document.getElementById("assistant-log");
  var form = document.getElementById("assistant-compose");
  if (!pop || !opener) return;

  function setOpen(open) {
    pop.hidden = !open;
    opener.setAttribute("aria-expanded", open ? "true" : "false");
    if (open) {
      var field = document.getElementById("assistant-q");
      if (field) field.focus();
      if (log) log.scrollTop = log.scrollHeight;
    }
  }
  opener.addEventListener("click", function () { setOpen(pop.hidden); });
  var closer = document.getElementById("assistant-close");
  if (closer) closer.addEventListener("click", function () { setOpen(false); });
  var clear = document.getElementById("assistant-clear");
  if (clear && log) {
    clear.addEventListener("click", function () {
      if (!window.confirm("Xóa lịch sử chat của phiên này?")) return;
      var params = new URLSearchParams();
      params.set("action", "clear");
      fetch("/tro-ly", {
        method: "POST",
        body: params,
        headers: {
          "X-Assistant-Panel": "1",
          "Content-Type": "application/x-www-form-urlencoded"
        }
      }).then(function (response) {
        if (!response.ok) return;
        var rows = log.querySelectorAll(".msg");
        for (var i = 1; i < rows.length; i++) rows[i].remove();
        refreshTracing();
      });
    });
  }

  var userMark = (log && log.getAttribute("data-initial")) || "B";
  var botAvatar = document.getElementById("bot-avatar");
  function avatar(kind) {
    if (kind.indexOf("user") !== -1) {
      return '<span class="av av-user" aria-hidden="true">' + userMark + '</span>';
    }
    return botAvatar ? botAvatar.innerHTML : "";
  }
  function addBubble(kind, html) {
    if (!log) return null;
    var isUser = kind.indexOf("user") !== -1;
    var row = document.createElement("div");
    row.className = "msg " + (isUser ? "user" : "bot");
    var bubble = document.createElement("div");
    bubble.className = "bubble " + kind;
    bubble.innerHTML = html;
    if (isUser) {
      row.appendChild(bubble);
      row.insertAdjacentHTML("beforeend", avatar(kind));
    } else {
      row.insertAdjacentHTML("afterbegin", avatar(kind));
      row.appendChild(bubble);
    }
    log.appendChild(row);
    log.scrollTop = log.scrollHeight;
    return bubble;
  }

  function ask(data) {
    var params = new URLSearchParams();
    data.forEach(function (value, key) {
      if (typeof value === "string") params.append(key, value);
    });
    var pending = addBubble("bot", "<p class=\"note\">Đang tìm…</p>");
    fetch("/tro-ly", {
      method: "POST",
      body: params,
      headers: {
        "X-Assistant-Panel": "1",
        "Content-Type": "application/x-www-form-urlencoded"
      }
    }).then(function (response) {
      if (response.redirected && response.url.indexOf("/login") !== -1) {
        window.location = "/login";
        return "";
      }
      return response.text();
    }).then(function (html) {
      if (!pending) return;
      var markup = html || "<p class=\"note\">Không trả lời được.</p>";
      var rich = markup.indexOf("advice-card") !== -1 || markup.indexOf("<form") !== -1;
      pending.className = rich ? "bubble bot cards" : "bubble bot";
      pending.innerHTML = markup;
      log.scrollTop = log.scrollHeight;
      refreshTracing();
    }).catch(function () {
      if (pending) pending.innerHTML = "<p class=\"note\">Mạng lỗi, thử lại.</p>";
    });
  }

  var mic = document.getElementById("assistant-mic");
  var Speech = window.SpeechRecognition || window.webkitSpeechRecognition;
  var recognition = null;
  if (mic && Speech) {
    recognition = new Speech();
    recognition.lang = "vi-VN";
    recognition.interimResults = false;
    recognition.onresult = function (event) {
      var said = event.results[0][0].transcript;
      var field = document.getElementById("assistant-q");
      if (field) field.value = said;
      if (form) form.requestSubmit();
    };
    recognition.onend = function () { mic.classList.remove("recording"); };
    mic.addEventListener("click", function () {
      if (mic.classList.contains("recording")) {
        recognition.stop();
        return;
      }
      mic.classList.add("recording");
      recognition.start();
    });
  } else if (mic) {
    mic.addEventListener("click", function () {
      addBubble("bot", "Trình duyệt này chưa nghe được giọng nói. Gõ tin nhắn giúp mình.");
    });
  }

  if (form && log) {
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      var field = document.getElementById("assistant-q");
      var text = field ? field.value.trim() : "";
      if (!text) return;
      var mine = "<span>" + text.replace(/[&<>]/g, function (char) {
        return { "&": "&amp;", "<": "&lt;", ">": "&gt;" }[char];
      }) + "</span>";
      addBubble("user", mine);
      var data = new FormData();
      data.set("q", text);
      ask(data);
      if (field) field.value = "";
    });
    pop.addEventListener("submit", function (event) {
      var inner = event.target;
      if (!inner || inner === form) return;
      if ((inner.getAttribute("action") || "").indexOf("/tro-ly") === -1) return;
      event.preventDefault();
      ask(new FormData(inner));
    });
  }

  var tracePage = document.querySelector(".trace-page");
  function refreshTracing() {
    if (!tracePage) return;
    fetch("/tracing/rev", { credentials: "same-origin", cache: "no-store" }).then(function (response) {
      if (!response.ok) return "";
      return response.text();
    }).then(function (rev) {
      rev = (rev || "").trim();
      if (!rev || rev === tracePage.getAttribute("data-rev")) return;
      var url = new URL(window.location.href);
      var listed = tracePage.getAttribute("data-count") || "0";
      var selected = url.searchParams.get("t");
      var nextCount = rev.split(":")[0] || "0";
      if (!selected || selected === listed) {
        if (nextCount === "0") {
          url.searchParams.delete("t");
          url.searchParams.delete("o");
        } else {
          url.searchParams.set("t", nextCount);
          url.searchParams.set("o", "0");
        }
        window.location.assign(url.pathname + url.search);
        return;
      }
      window.location.reload();
    }).catch(function () {});
  }
  var traceReload = document.getElementById("trace-reload");
  if (traceReload) traceReload.addEventListener("click", function () { window.location.reload(); });
  if (tracePage) {
    window.setInterval(refreshTracing, 2000);
    document.addEventListener("visibilitychange", function () {
      if (document.visibilityState === "visible") refreshTracing();
    });
  }
})();
