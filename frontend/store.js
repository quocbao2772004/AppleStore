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

  function bindLoop(rail) {
    if (!rail || rail.getAttribute("data-loop-ready")) return null;
    var slides = Array.prototype.filter.call(rail.children, function (node) {
      return node.nodeType === 1;
    });
    if (slides.length < 2) return null;
    rail.setAttribute("data-loop-ready", "1");
    var count = slides.length;
    var before = document.createDocumentFragment();
    var after = document.createDocumentFragment();
    slides.forEach(function (slide) {
      var lead = slide.cloneNode(true);
      var tail = slide.cloneNode(true);
      lead.classList.add("is-clone");
      tail.classList.add("is-clone");
      lead.setAttribute("aria-hidden", "true");
      tail.setAttribute("aria-hidden", "true");
      before.appendChild(lead);
      after.appendChild(tail);
    });
    rail.insertBefore(before, rail.firstChild);
    rail.appendChild(after);
    function step() {
      var first = rail.children[0];
      var second = rail.children[1];
      if (!first || !second) return 0;
      return second.offsetLeft - first.offsetLeft;
    }
    function jump(index) {
      var width = step();
      if (!width) return;
      var behavior = rail.style.scrollBehavior;
      rail.style.scrollBehavior = "auto";
      rail.scrollLeft = index * width;
      rail.style.scrollBehavior = behavior;
    }
    var animating = false;
    var settling = false;
    var quiet = 0;
    var fallback = 0;
    function settle() {
      if (settling) return;
      window.clearTimeout(fallback);
      var width = step();
      if (!width) return;
      var index = Math.round(rail.scrollLeft / width);
      var next = index;
      if (index < count) next = index + count;
      else if (index >= count * 2) next = index - count;
      animating = false;
      if (next === index) return;
      settling = true;
      jump(next);
      settling = false;
    }
    rail.addEventListener("scroll", function () {
      if (animating || settling) return;
      window.clearTimeout(quiet);
      quiet = window.setTimeout(settle, 90);
    }, { passive: true });
    rail.addEventListener("scrollend", settle);
    jump(count);
    var AUTO_MS = 5000;
    var auto = 0;
    var hover = false;
    var focus = false;
    function stopAuto() {
      window.clearTimeout(auto);
      auto = 0;
    }
    function by(dir) {
      if (animating) return false;
      var width = step();
      if (!width) return false;
      var index = Math.round(rail.scrollLeft / width) + dir;
      animating = true;
      window.clearTimeout(fallback);
      fallback = window.setTimeout(settle, 800);
      rail.scrollTo({ left: index * width, behavior: reduced ? "auto" : "smooth" });
      arm();
      return true;
    }
    function arm() {
      stopAuto();
      if (reduced || document.hidden || hover || focus || !rail.hasAttribute("data-auto")) return;
      auto = window.setTimeout(function () {
        if (!by(1)) arm();
      }, AUTO_MS);
    }
    if (rail.hasAttribute("data-auto")) {
      var zone = rail.parentElement || rail;
      zone.addEventListener("pointerenter", function (event) {
        if (event.pointerType === "touch") return;
        hover = true;
        stopAuto();
      });
      zone.addEventListener("pointerleave", function (event) {
        if (event.pointerType === "touch") return;
        hover = false;
        arm();
      });
      zone.addEventListener("pointerdown", stopAuto);
      zone.addEventListener("pointerup", arm);
      zone.addEventListener("pointercancel", arm);
      zone.addEventListener("focusin", function () {
        window.setTimeout(function () {
          focus = !!zone.querySelector(":focus-visible");
          if (focus) stopAuto();
        }, 0);
      });
      zone.addEventListener("focusout", function () {
        window.setTimeout(function () {
          focus = !!zone.querySelector(":focus-visible");
          if (!focus) arm();
        }, 0);
      });
      document.addEventListener("visibilitychange", function () {
        if (document.hidden) stopAuto();
        else arm();
      });
      arm();
    }
    return { by: by };
  }
  var loops = {};
  document.querySelectorAll("[data-loop]").forEach(function (rail) {
    if (rail.id) loops[rail.id] = bindLoop(rail);
  });
  document.querySelectorAll("[data-loop-for]").forEach(function (button) {
    button.addEventListener("click", function () {
      var loop = loops[button.getAttribute("data-loop-for")];
      if (loop) loop.by(Number(button.getAttribute("data-loop-dir")) || 1);
    });
  });

  document.querySelectorAll("[data-reason-rail]").forEach(function (rail) {
    var band = rail.closest(".reason-band");
    if (!band) return;
    function by(dir) {
      var card = rail.querySelector(".reason-card");
      if (!card) return;
      var width = card.getBoundingClientRect().width + 16;
      var max = rail.scrollWidth - rail.clientWidth;
      var next = rail.scrollLeft + dir * width;
      if (next > max + 4) next = 0;
      if (next < -4) next = Math.max(0, max);
      rail.scrollTo({ left: next, behavior: reduced ? "auto" : "smooth" });
    }
    band.querySelectorAll("[data-reason-dir]").forEach(function (button) {
      button.addEventListener("click", function () {
        by(Number(button.getAttribute("data-reason-dir")) || 1);
      });
    });
  });
  var reasonDialog = document.getElementById("reason-dialog");
  var reasonLink = document.getElementById("reason-link");
  function openReason(card) {
    if (!reasonDialog || !card) return;
    var kicker = document.getElementById("reason-kicker");
    var title = document.getElementById("reason-title");
    var copy = document.getElementById("reason-copy");
    if (kicker) kicker.textContent = card.getAttribute("data-kicker") || "";
    if (title) title.textContent = card.getAttribute("data-title") || "";
    if (copy) copy.textContent = card.getAttribute("data-detail") || "";
    if (reasonLink) {
      var action = card.getAttribute("data-action") || "";
      var href = card.getAttribute("data-href") || "";
      reasonLink.textContent = card.getAttribute("data-link") || "Tìm hiểu thêm ›";
      if (action === "assistant") {
        reasonLink.hidden = false;
        reasonLink.setAttribute("href", "#assistant");
        reasonLink.setAttribute("data-open-assistant", "1");
      } else if (href) {
        reasonLink.hidden = false;
        reasonLink.setAttribute("href", href);
        reasonLink.removeAttribute("data-open-assistant");
      } else {
        reasonLink.hidden = true;
      }
    }
    if (reasonDialog.showModal) reasonDialog.showModal();
    else reasonDialog.setAttribute("open", "");
  }
  document.addEventListener("click", function (event) {
    var card = event.target.closest("[data-reason-open]");
    if (card) {
      openReason(card);
      return;
    }
    if (!reasonDialog) return;
    if (event.target.closest("[data-reason-close]") || event.target === reasonDialog) {
      if (reasonDialog.close) reasonDialog.close();
      else reasonDialog.removeAttribute("open");
      return;
    }
    var link = event.target.closest("#reason-link");
    if (link && link.getAttribute("data-open-assistant") === "1") {
      event.preventDefault();
      if (reasonDialog.close) reasonDialog.close();
      var opener = document.getElementById("open-assistant");
      if (opener) opener.click();
    }
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
  var clearDialog = document.getElementById("assistant-clear-dialog");
  var clearCancel = document.getElementById("assistant-clear-cancel");
  var clearConfirm = document.getElementById("assistant-clear-confirm");
  var clearError = document.getElementById("assistant-clear-error");
  function setClearOpen(open) {
    if (!clearDialog) return;
    if (clearError) clearError.hidden = true;
    if (clearConfirm) {
      clearConfirm.disabled = false;
      clearConfirm.textContent = "Xóa";
    }
    if (open) {
      if (clearDialog.showModal) clearDialog.showModal();
      if (clearCancel) clearCancel.focus();
    } else if (clearDialog.open && clearDialog.close) {
      clearDialog.close();
    }
    if (clear) clear.setAttribute("aria-expanded", open ? "true" : "false");
  }
  if (clear && log && clearDialog) {
    clear.setAttribute("aria-haspopup", "dialog");
    clear.setAttribute("aria-controls", "assistant-clear-dialog");
    clear.setAttribute("aria-expanded", "false");
    clear.addEventListener("click", function () { setClearOpen(true); });
    if (clearCancel) clearCancel.addEventListener("click", function () { setClearOpen(false); });
    clearDialog.addEventListener("click", function (event) {
      if (event.target === clearDialog) setClearOpen(false);
    });
    clearDialog.addEventListener("cancel", function (event) {
      event.preventDefault();
      setClearOpen(false);
    });
    if (clearConfirm) clearConfirm.addEventListener("click", function () {
      clearConfirm.disabled = true;
      clearConfirm.textContent = "Đang xóa…";
      if (clearError) clearError.hidden = true;
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
        if (!response.ok) throw new Error("clear");
        var rows = log.querySelectorAll(".msg");
        for (var i = 1; i < rows.length; i++) rows[i].remove();
        setClearOpen(false);
        refreshTracing();
      }).catch(function () {
        clearConfirm.disabled = false;
        clearConfirm.textContent = "Xóa";
        if (clearError) clearError.hidden = false;
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
  if (log && form) {
    log.addEventListener("click", function (event) {
      var chip = event.target.closest ? event.target.closest(".brand-chip") : null;
      if (!chip) return;
      var field = document.getElementById("assistant-q");
      if (!field) return;
      field.value = chip.getAttribute("data-q") || chip.textContent;
      form.requestSubmit();
    });
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

  function poseRobot(avatar, state) {
    if (!avatar) return;
    avatar.setAttribute("data-state", state);
    if (state === "busy" && typeof avatar.startWaiting === "function") {
      avatar.startWaiting();
      return;
    }
    if (state !== "busy" && typeof avatar.stopWaiting === "function") avatar.stopWaiting();
  }

  function setMascot(state) {
    poseRobot(document.getElementById("octopus-mascot"), state);
    var status = document.getElementById("assistant-status");
    if (status) status.textContent = state === "busy" ? "Đang nghĩ…" : "Trợ lý AI";
  }

  function ask(data) {
    var params = new URLSearchParams();
    data.forEach(function (value, key) {
      if (typeof value === "string") params.append(key, value);
    });
    var pending = addBubble("bot", "<p class=\"think\" role=\"status\"><span class=\"think-dots\" aria-hidden=\"true\"><span></span><span></span><span></span></span>Đang nghĩ</p>");
    var thinkingRow = pending && pending.closest ? pending.closest(".msg") : null;
    if (thinkingRow) {
      thinkingRow.classList.add("is-thinking");
      poseRobot(thinkingRow.querySelector("agent-robot-avatar"), "busy");
    }
    setMascot("busy");
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
      var rich = markup.indexOf("advice-card") !== -1 || markup.indexOf("chat-compare") !== -1 || markup.indexOf("chat-invoice") !== -1 || markup.indexOf("citation") !== -1 || markup.indexOf("<form") !== -1;
      pending.className = rich ? "bubble bot cards" : "bubble bot";
      pending.innerHTML = markup;
      log.scrollTop = log.scrollHeight;
      refreshTracing();
    }).catch(function () {
      if (pending) pending.innerHTML = "<p class=\"note\">Mạng lỗi, thử lại.</p>";
    }).then(function () {
      if (thinkingRow) {
        thinkingRow.classList.remove("is-thinking");
        poseRobot(thinkingRow.querySelector("agent-robot-avatar"), "idle");
      }
      setMascot("idle");
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

  var productEdit = document.getElementById("product-edit");
  var productForm = document.getElementById("product-edit-form");
  if (productEdit && productForm) {
    function closeProductEdit() {
      if (productEdit.close) productEdit.close();
      else productEdit.removeAttribute("open");
    }
    document.addEventListener("click", function (event) {
      var button = event.target.closest ? event.target.closest(".admin-edit") : null;
      if (!button) return;
      productForm.action = "/admin/" + (button.getAttribute("data-id") || "");
      productForm.elements.name.value = button.getAttribute("data-name") || "";
      productForm.elements.brand.value = button.getAttribute("data-brand") || "";
      productForm.elements.category.value = button.getAttribute("data-category") || "phone";
      productForm.elements.price.value = button.getAttribute("data-price") || "";
      productForm.elements.stock.value = button.getAttribute("data-stock") || "0";
      productForm.elements.description.value = button.getAttribute("data-description") || "";
      var photo = document.getElementById("product-edit-photo");
      var image = button.getAttribute("data-image") || "";
      if (photo) {
        if (image) {
          photo.src = image;
          photo.hidden = false;
        } else {
          photo.removeAttribute("src");
          photo.hidden = true;
        }
      }
      if (productEdit.showModal) productEdit.showModal();
      else productEdit.setAttribute("open", "");
      productForm.elements.name.focus();
    });
    var cancelEdit = document.getElementById("product-edit-cancel");
    if (cancelEdit) cancelEdit.addEventListener("click", closeProductEdit);
    productEdit.addEventListener("click", function (event) {
      if (event.target === productEdit) closeProductEdit();
    });
  }
})();

(function () {
  var toggle = document.querySelector(".qc-toggle");
  var menu = document.getElementById("quick-menu");
  var contact = document.querySelector(".quick-contact");
  function setContact(open) {
    if (!toggle || !menu) return;
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
    toggle.setAttribute("aria-label", open ? "Đóng liên hệ nhanh" : "Mở liên hệ nhanh");
    menu.hidden = !open;
  }
  if (toggle) {
    toggle.addEventListener("click", function () {
      setContact(toggle.getAttribute("aria-expanded") !== "true");
    });
    document.addEventListener("click", function (event) {
      if (!contact || contact.contains(event.target)) return;
      setContact(false);
    });
  }

  var storageKey = "octopus-compare";
  function esc(value) {
    return String(value == null ? "" : value).replace(/[&<>"]/g, function (char) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[char];
    });
  }
  function readCompare() {
    try {
      var parsed = JSON.parse(localStorage.getItem(storageKey) || "");
      if (!parsed || !Array.isArray(parsed.items)) return { category: "", label: "", items: [] };
      parsed.items = parsed.items.slice(0, 4);
      return parsed;
    } catch (error) {
      return { category: "", label: "", items: [] };
    }
  }
  function writeCompare(state) {
    if (!state.items.length) localStorage.removeItem(storageKey);
    else localStorage.setItem(storageKey, JSON.stringify(state));
  }
  function showNote(text) {
    var note = document.getElementById("compare-note");
    if (!note) return;
    note.textContent = text || "";
    note.hidden = !text;
  }
  function renderCompare() {
    var dock = document.getElementById("compare-dock");
    if (!dock) return;
    if (document.querySelector(".compare-page")) {
      dock.hidden = true;
      return;
    }
    var state = readCompare();
    var slots = document.getElementById("compare-slots");
    var go = document.getElementById("compare-go");
    dock.hidden = state.items.length === 0;
    if (slots) {
      slots.innerHTML = state.items.map(function (item) {
        var image = item.image ? '<img src="' + esc(item.image) + '" alt="">' : "";
        return '<div class="compare-slot">' + image + '<span>' + esc(item.title) + '</span><button type="button" data-compare-remove="' + esc(item.id) + '" aria-label="Bỏ ' + esc(item.title) + '">×</button></div>';
      }).join("");
    }
    if (go) {
      go.href = "/so-sanh" + (state.items.length ? "?" + state.items.map(function (item) {
        return "id=" + encodeURIComponent(item.id);
      }).join("&") : "");
    }
    var add = document.getElementById("compare-add");
    if (add) {
      var chosen = state.items.some(function (item) { return String(item.id) === add.getAttribute("data-id"); });
      add.classList.toggle("is-in", chosen);
      add.textContent = chosen ? "Đang so sánh" : "So sánh";
    }
  }
  var comparePage = document.querySelector(".compare-page");
  if (comparePage) {
    var cards = comparePage.querySelectorAll("[data-compare-id]");
    var items = [];
    cards.forEach(function (card) {
      items.push({
        id: card.getAttribute("data-compare-id"),
        title: card.getAttribute("data-compare-title") || "",
        price: card.getAttribute("data-compare-price") || "",
        image: card.getAttribute("data-compare-image") || ""
      });
    });
    if (items.length) {
      writeCompare({
        category: comparePage.getAttribute("data-compare-category") || "",
        label: comparePage.getAttribute("data-compare-label") || "",
        items: items.slice(0, 4)
      });
    } else {
      localStorage.removeItem(storageKey);
    }
  }
  var add = document.getElementById("compare-add");
  if (add) {
    add.addEventListener("click", function () {
      var state = readCompare();
      var id = add.getAttribute("data-id");
      var category = add.getAttribute("data-category") || "";
      if (state.category && state.items.length && state.category !== category) {
        showNote("Chỉ so sánh được máy cùng nhóm. Đang chọn " + (state.label || "nhóm này") + ".");
        document.getElementById("compare-dock").hidden = false;
        return;
      }
      if (!state.items.some(function (item) { return String(item.id) === id; })) {
        if (state.items.length >= 4) {
          showNote("Chỉ so sánh tối đa 4 máy.");
        } else {
          state.category = category;
          state.label = add.getAttribute("data-label") || "";
          state.items.push({
            id: id,
            title: add.getAttribute("data-title") || "",
            price: add.getAttribute("data-price") || "",
            image: add.getAttribute("data-image") || ""
          });
          showNote("");
          writeCompare(state);
        }
      }
      renderCompare();
    });
  }
  var dock = document.getElementById("compare-dock");
  if (dock) {
    dock.addEventListener("click", function (event) {
      var button = event.target.closest ? event.target.closest("[data-compare-remove]") : null;
      if (!button) return;
      var state = readCompare();
      state.items = state.items.filter(function (item) {
        return String(item.id) !== button.getAttribute("data-compare-remove");
      });
      if (!state.items.length) state.category = "";
      writeCompare(state);
      showNote("");
      renderCompare();
    });
  }
  var clear = document.getElementById("compare-clear");
  if (clear) {
    clear.addEventListener("click", function () {
      localStorage.removeItem(storageKey);
      showNote("");
      renderCompare();
    });
  }
  renderCompare();
})();

(function () {
  function reviveRobots(root) {
    (root || document).querySelectorAll("agent-robot-avatar").forEach(function (avatar) {
      var painted = avatar.shadowRoot && avatar.shadowRoot.querySelector("svg");
      if (!painted && avatar.parentNode) {
        var next = avatar.cloneNode(true);
        avatar.parentNode.replaceChild(next, avatar);
        avatar = next;
      }
      if (typeof avatar._syncSizeAttribute === "function") avatar._syncSizeAttribute();
      var rect = avatar.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0) avatar._runtimeVisible = true;
      if (typeof avatar._resumeFrames === "function") avatar._resumeFrames();
    });
  }
  function revive() {
    reviveRobots(document);
  }
  window.addEventListener("pageshow", revive);
  var opener = document.getElementById("open-assistant");
  if (opener) opener.addEventListener("click", function () { window.setTimeout(revive, 0); });
  if (window.customElements && customElements.whenDefined) {
    customElements.whenDefined("agent-robot-avatar").then(revive);
  } else {
    revive();
  }
})();
