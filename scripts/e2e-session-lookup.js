/**
 * 按 fusion sessionId 列出该用户一手牌，可视化展示视觉 / 规则，并可复制原始 JSON。
 */
(function (global) {
  "use strict";

  var DEFAULT_API = "http://192.168.110.81:8080";
  var STREET_LAB = { preflop: "翻前", flop: "翻牌", turn: "转牌", river: "河牌" };
  var SUIT_SYM = { s: "♠", h: "♥", d: "♦", c: "♣" };

  function $(id) {
    return document.getElementById(id);
  }

  function fusionBase() {
    return (($("q-api") && $("q-api").value) || DEFAULT_API).replace(/\/+$/, "");
  }

  function setStatus(msg) {
    var el = $("q-status");
    if (el) el.textContent = msg || "";
  }

  function pretty(obj) {
    if (obj == null) return "";
    try {
      return JSON.stringify(obj, null, 2);
    } catch (e) {
      return String(obj);
    }
  }

  function escHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function visualOf(body) {
    if (!body || typeof body !== "object") return null;
    return body.rawJson != null ? body.rawJson : null;
  }

  function ruleOf(body) {
    if (!body || typeof body !== "object") return null;
    return body.ruleResult != null ? body.ruleResult : null;
  }

  function userHint(body) {
    var rr = body && body.ruleResult;
    var vis = body && body.rawJson && body.rawJson.llm_extraction;
    var oid = (rr && (rr.open_id || rr.openId)) || (vis && vis.open_id) || "";
    var nick = vis && vis.hero_nickname;
    var parts = [];
    if (oid) parts.push("open_id " + shortId(oid));
    if (nick) parts.push(/hero/i.test(String(nick)) ? String(nick) : "Hero " + nick);
    return parts.join(" · ");
  }

  function parseCard(code) {
    var raw = String(code == null ? "" : code).trim();
    if (!raw) return { cls: "unk", text: "—" };
    var compact = raw.replace(/\s/g, "");
    if (/^x+$/i.test(compact) || /^x.x$/i.test(compact)) return { cls: "unk", text: "?" };
    var suitCh = compact.slice(-1).toLowerCase();
    var rank = compact.slice(0, -1).toUpperCase();
    if (rank === "10") rank = "T";
    var suit = SUIT_SYM[suitCh] ? suitCh : "";
    if (!suit) return { cls: "unk", text: compact };
    return { cls: suit, text: rank + SUIT_SYM[suit] };
  }

  function cardsHtml(list) {
    if (!list || !list.length) return "<span class='hv-miss'>无</span>";
    return list
      .map(function (c) {
        var p = parseCard(c);
        return "<span class='pcard " + p.cls + "'>" + escHtml(p.text) + "</span>";
      })
      .join("");
  }

  function streetLab(s) {
    var k = String(s || "").toLowerCase();
    return STREET_LAB[k] || s || "";
  }

  function parseBlindLevel(s) {
    var m = String(s || "").match(/(\d+(?:\.\d+)?)\s*\/\s*(\d+(?:\.\d+)?)(?:\s*\((\d+(?:\.\d+)?)\))?/);
    if (!m) return {};
    return { sb: m[1], bb: m[2], ante: m[3] || 0 };
  }

  function visModel(raw) {
    var ext = raw && raw.llm_extraction;
    if (!ext || typeof ext !== "object") return null;
    var hand = (ext.hands || [])[0];
    if (!hand || typeof hand !== "object") return null;
    var blinds = parseBlindLevel(ext.blind_level);
    var cfg = ext.blinds_config || {};
    if (blinds.sb == null && cfg.small_blind != null) {
      blinds = {
        sb: cfg.small_blind,
        bb: cfg.big_blind,
        ante: cfg.ante_per_player != null ? cfg.ante_per_player : cfg.ante,
      };
    }
    var board = hand.community_cards || [];
    if (!board.length) {
      var by = hand.community_cards_by_street || {};
      board = [].concat(by.flop || [], by.turn || [], by.river || []);
    }
    var pots = hand.pots_structure || hand.pots_info || {};
    var settle = hand.settlement || {};
    var players = (hand.players || []).map(function (p) {
      var hole = p.shown_cards || [];
      if (p.is_hero && (!hole || !hole.length)) hole = hand.hero_cards || [];
      return {
        pos: p.position || p.player_seat || "",
        name: p.nickname || "",
        hero: !!p.is_hero,
        dealer: !!p.is_dealer,
        hole: hole,
        init: p.initial_chips,
        final: p.final_chips,
        fold: String(p.status || "").toLowerCase() === "fold" || String(p.status || "").toLowerCase() === "folded",
      };
    });
    var actions = (hand.actions || []).map(function (a) {
      return {
        street: a.street,
        pos: a.player_position || "",
        name: a.player || "",
        action: a.action || "",
        amount: a.amount,
      };
    });
    var winners = settle.winner_nickname || settle.winners || hand.winner;
    return {
      blinds: blinds,
      n: players.length || ext.table_size,
      pot: (global.E2EMatch && E2EMatch.pickVisPot)
        ? E2EMatch.pickVisPot(hand)
        : (pots.total_pot != null ? pots.total_pot : hand.final_pot),
      showdown: !!(settle.showdown || hand.outcome === "showdown"),
      board: board,
      players: players,
      actions: actions,
      winners: winners,
    };
  }

  function ruleModel(rr) {
    if (!rr || typeof rr !== "object") return null;
    var byId = {};
    var players = (rr.players || []).map(function (row) {
      var cells = Array.isArray(row) ? row : [];
      var shown = cells[6];
      var hole = Array.isArray(shown) && shown.length ? shown : cells[3];
      if (!Array.isArray(hole)) hole = hole ? [hole] : [];
      var rec = {
        id: cells[0],
        pos: cells[1] || "",
        name: cells[2] || "",
        hero: /hero/i.test(String(cells[2] || "")),
        dealer: String(cells[1] || "").toUpperCase() === "BTN",
        hole: hole,
        init: cells[4],
        final: cells[5],
        fold: false,
      };
      byId[String(cells[0])] = rec;
      return rec;
    });
    var actions = (rr.actions || []).map(function (row) {
      var cells = Array.isArray(row) ? row : [];
      var who = byId[String(cells[0])] || {};
      var act = String(cells[2] || "").toLowerCase();
      if (act === "fold" && who) who.fold = true;
      return {
        street: cells[1],
        pos: who.pos || cells[0] || "",
        name: who.name || "",
        action: cells[2] || "",
        amount: cells[3],
      };
    });
    var board = [];
    if (Array.isArray(rr.board)) {
      rr.board.forEach(function (x) {
        if (typeof x === "string" && x) board.push(x);
        else if (Array.isArray(x)) x.forEach(function (c) { if (c) board.push(c); });
      });
    }
    var result = rr.result || {};
    var blinds = rr.blinds || {};
    var winners = result.winners;
    if (Array.isArray(winners)) {
      winners = winners.map(function (id) {
        var p = byId[String(id)];
        return p ? p.name || p.pos || id : id;
      });
    }
    return {
      blinds: blinds,
      n: players.length,
      pot: result.total_pot,
      showdown: !!result.showdown,
      board: board,
      players: players,
      actions: actions,
      winners: winners,
    };
  }

  var POS_ORDER = ["UTG", "UTG+1", "UTG+2", "LJ", "HJ", "CO", "BTN", "SB", "BB"];
  var POST_RE = /post_|cost_|^(ante|sb|bb|straddle|small_blind|big_blind)$/i;

  function shortId(id) {
    var s = String(id || "");
    if (s.length <= 18) return s;
    return "…" + s.slice(-14);
  }

  function statusClass(s) {
    var k = String(s || "").toLowerCase();
    if (k === "success" || k === "ok") return "ok";
    if (/fail|error|timeout/.test(k)) return "bad";
    return "";
  }

  function numOf(v) {
    if (v == null || v === "") return null;
    var m = String(v).replace(/,/g, "").match(/-?\d+(?:\.\d+)?/);
    return m ? Number(m[0]) : null;
  }

  function sameAmt(a, b) {
    var na = numOf(a);
    var nb = numOf(b);
    if (na != null && nb != null) return na === nb;
    return String(a == null ? "" : a) === String(b == null ? "" : b);
  }

  function sameText(a, b) {
    return String(a == null ? "" : a).trim() === String(b == null ? "" : b).trim();
  }

  function cardsKey(list) {
    return (list || [])
      .map(function (c) { return parseCard(c).text; })
      .join(" ");
  }

  function sameCards(a, b) {
    return cardsKey(a) === cardsKey(b);
  }

  function fmtBlind(b) {
    b = b || {};
    var core = [b.sb, b.bb].filter(function (x) { return x != null && x !== ""; }).join("/");
    if (!core) return "";
    if (b.ante != null && b.ante !== "" && Number(b.ante) !== 0) core += " · ante " + b.ante;
    return core;
  }

  function fmtWin(v) {
    if (v == null || v === "") return "";
    if (!Array.isArray(v)) return String(v);
    if (v.length <= 2) return v.join("、");
    return v.length + " 人（" + v.slice(0, 2).join("、") + "…）";
  }

  function dash(v) {
    return v == null || v === "" ? "—" : String(v);
  }

  function pairCell(left, right, equal, html) {
    var lRaw = left == null || left === "" ? "" : left;
    var rRaw = right == null || right === "" ? "" : right;
    if (!lRaw && !rRaw) return "<span class='cell-one'>—</span>";
    if (equal) {
      var one = lRaw || rRaw;
      return "<span class='cell-one'>" + (html ? one : escHtml(dash(one))) + "</span>";
    }
    var l = html ? (lRaw || "—") : escHtml(dash(lRaw));
    var r = html ? (rRaw || "—") : escHtml(dash(rRaw));
    return (
      "<div class='cell-pair is-bad'>" +
      "<div class='row'><span class='tag'>视觉</span><span>" + l + "</span></div>" +
      "<div class='row'><span class='tag'>规则</span><span>" + r + "</span></div>" +
      "</div>"
    );
  }

  function kpiCard(lab, left, right, equal) {
    var cls = equal ? "" : " is-diff";
    var body;
    if (equal) body = "<div class='one'>" + escHtml(dash(left || right)) + "</div>";
    else {
      body =
        "<div class='pair'>" +
        "<div class='col'><span class='tag'>视觉</span><span class='num'>" + escHtml(dash(left)) + "</span></div>" +
        "<span class='vs'>/</span>" +
        "<div class='col'><span class='tag'>规则</span><span class='num'>" + escHtml(dash(right)) + "</span></div>" +
        "</div>";
    }
    return "<div class='cmp-kpi" + cls + "'><div class='lab'>" + escHtml(lab) + "</div>" + body + "</div>";
  }

  function isPost(a) {
    if (global.E2EMatch && typeof E2EMatch.isPost === "function") {
      return E2EMatch.isPost(a && a.action);
    }
    return POST_RE.test(String((a && a.action) || ""));
  }

  function actHtml(a) {
    if (!a) return "<span class='hv-miss'>—</span>";
    var amt = a.amount == null || a.amount === "" ? "" : String(a.amount);
    var name = a.name && a.pos && a.name !== a.pos ? a.name : "";
    return (
      "<div class='act'>" +
      "<span class='pos'>" + escHtml(a.pos || "") + "</span>" +
      (name ? "<span class='who'>" + escHtml(name) + "</span>" : "") +
      "<span class='verb'>" + escHtml(a.action || "") + "</span>" +
      (amt ? "<span class='amt'>" + escHtml(amt) + "</span>" : "") +
      "</div>"
    );
  }

  function actKey(a) {
    if (!a) return "";
    return [a.pos || "", a.action || "", a.amount == null ? "" : String(numOf(a.amount) != null ? numOf(a.amount) : a.amount)].join("|");
  }

  function matchPlayer(list, p, used) {
    if (!p || !list) return -1;
    var pos = String(p.pos || "").toUpperCase();
    var name = String(p.name || "");
    var i;
    for (i = 0; i < list.length; i++) {
      if (used[i]) continue;
      if (pos && String(list[i].pos || "").toUpperCase() === pos) return i;
    }
    for (i = 0; i < list.length; i++) {
      if (used[i]) continue;
      if (name && String(list[i].name || "") === name) return i;
    }
    return -1;
  }

  function mergePlayers(vis, rule) {
    var a = (vis && vis.players) || [];
    var b = (rule && rule.players) || [];
    var used = {};
    var rows = [];
    a.forEach(function (p) {
      var j = matchPlayer(b, p, used);
      if (j >= 0) used[j] = true;
      rows.push({ vis: p, rule: j >= 0 ? b[j] : null });
    });
    b.forEach(function (p, i) {
      if (!used[i]) rows.push({ vis: null, rule: p });
    });
    rows.sort(function (x, y) {
      var px = String((x.vis || x.rule || {}).pos || "").toUpperCase();
      var py = String((y.vis || y.rule || {}).pos || "").toUpperCase();
      var ix = POS_ORDER.indexOf(px);
      var iy = POS_ORDER.indexOf(py);
      return (ix < 0 ? 99 : ix) - (iy < 0 ? 99 : iy);
    });
    return rows;
  }

  function streetsOf(vis, rule) {
    var order = [];
    var seen = {};
    function add(list) {
      (list || []).forEach(function (a) {
        var st = a.street || "";
        if (!seen[st]) {
          seen[st] = true;
          order.push(st);
        }
      });
    }
    add(vis && vis.actions);
    add(rule && rule.actions);
    return order;
  }

  function actsOn(model, street, hidePost) {
    return ((model && model.actions) || []).filter(function (a) {
      if ((a.street || "") !== street) return false;
      if (hidePost && isPost(a)) return false;
      return true;
    });
  }

  function renderCompare(vis, rule, hidePost) {
    if (!vis && !rule) return "<p class='hv-miss'>这一手没有可展示的视觉 / 规则结果。</p>";
    var diffs = [];
    var blindL = vis ? fmtBlind(vis.blinds) : "";
    var blindR = rule ? fmtBlind(rule.blinds) : "";
    var nL = vis && vis.n != null ? vis.n + " 人" : "";
    var nR = rule && rule.n != null ? rule.n + " 人" : "";
    var potL = vis && vis.pot != null ? vis.pot : "";
    var potR = rule && rule.pot != null ? rule.pot : "";
    var sdL = vis ? (vis.showdown ? "摊牌" : "未摊牌") : "";
    var sdR = rule ? (rule.showdown ? "摊牌" : "未摊牌") : "";
    if (vis && rule && !sameText(blindL, blindR)) diffs.push("盲注");
    if (vis && rule && !sameAmt(vis.n, rule.n)) diffs.push("人数");
    if (vis && rule && !sameAmt(potL, potR)) diffs.push("底池");
    if (vis && rule && !!vis.showdown !== !!rule.showdown) diffs.push("摊牌");
    var boardEq = sameCards(vis && vis.board, rule && rule.board);
    if (vis && rule && !boardEq) diffs.push("公牌");

    var kpis =
      "<div class='cmp-kpis'>" +
      kpiCard("盲注", blindL, blindR, !vis || !rule || sameText(blindL, blindR)) +
      kpiCard("人数", nL, nR, !vis || !rule || sameAmt(vis.n, rule.n)) +
      kpiCard("底池", potL, potR, !vis || !rule || sameAmt(potL, potR)) +
      kpiCard("摊牌", sdL, sdR, !vis || !rule || !!vis.showdown === !!rule.showdown) +
      "</div>";

    var boardCls = vis && rule && !boardEq ? " is-diff" : "";
    var boardHtml;
    if (boardEq) {
      boardHtml =
        "<div class='cmp-board'><span class='lab'>公牌</span>" +
        cardsHtml((vis && vis.board) || (rule && rule.board)) +
        "</div>";
    } else {
      boardHtml =
        "<div class='cmp-board" + boardCls + "'>" +
        "<span class='lab'>公牌</span>" +
        "<div class='side'><span class='tag'>视觉</span>" + cardsHtml(vis && vis.board) + "</div>" +
        "<div class='side'><span class='tag'>规则</span>" + cardsHtml(rule && rule.board) + "</div>" +
        "</div>";
    }

    var playerRows = mergePlayers(vis, rule);
    var pDiff = 0;
    var pBody = playerRows
      .map(function (row) {
        var pv = row.vis;
        var pr = row.rule;
        var pos = (pv && pv.pos) || (pr && pr.pos) || "";
        var both = !!(pv && pr);
        var nameEq = both && sameText(pv.name, pr.name);
        var cardEq = both && sameCards(pv.hole, pr.hole);
        var initEq = both && sameAmt(pv.init, pr.init);
        var endEq = both && sameAmt(pv.final, pr.final);
        var rowDiff = !both || !nameEq || !cardEq || !initEq || !endEq;
        if (rowDiff) pDiff += 1;
        var fold = (pv && pv.fold) || (pr && pr.fold);
        var hero = (pv && pv.hero) || (pr && pr.hero);
        var nameL = (pv && pv.name) || "";
        var nameR = (pr && pr.name) || "";
        if (hero && nameEq) nameL = escHtml(dash(nameL || nameR)) + "<span class='hero-mark'>Hero</span>";
        else if (hero) {
          nameL = escHtml(dash(pv && pv.name)) + (pv && pv.hero ? "<span class='hero-mark'>Hero</span>" : "");
          nameR = escHtml(dash(pr && pr.name)) + (pr && pr.hero ? "<span class='hero-mark'>Hero</span>" : "");
        }
        return (
          "<tr class='" +
          (fold ? "is-fold" : "") +
          "'><td class='pos'>" +
          escHtml(pos) +
          "</td><td" +
          (both && !nameEq ? " class='is-diff'" : "") +
          ">" +
          (hero && nameEq
            ? "<span class='cell-one'>" + nameL + "</span>"
            : pairCell(nameL, nameR, nameEq, hero && !nameEq)) +
          "</td><td" +
          (both && !cardEq ? " class='is-diff'" : "") +
          ">" +
          pairCell(cardsHtml(pv && pv.hole), cardsHtml(pr && pr.hole), cardEq, true) +
          "</td><td" +
          (both && !initEq ? " class='is-diff'" : "") +
          ">" +
          pairCell(pv && pv.init, pr && pr.init, initEq, false) +
          "</td><td" +
          (both && !endEq ? " class='is-diff'" : "") +
          ">" +
          pairCell(pv && pv.final, pr && pr.final, endEq, false) +
          "</td></tr>"
        );
      })
      .join("");
    if (pDiff) diffs.push("玩家 " + pDiff + " 人");

    var playersHtml =
      "<div class='cmp-sec'>玩家</div>" +
      "<div class='table-scroll'><table class='cmp'><thead><tr>" +
      "<th>位置</th><th>昵称</th><th>手牌</th><th>起始筹码</th><th>结束筹码</th>" +
      "</tr></thead><tbody>" +
      (pBody || "<tr><td colspan='5'>没有玩家</td></tr>") +
      "</tbody></table></div>";

    var actDiff = 0;
    var streetsHtml = streetsOf(vis, rule)
      .map(function (st) {
        var av = actsOn(vis, st, hidePost);
        var ar = actsOn(rule, st, hidePost);
        var n = Math.max(av.length, ar.length);
        var rows = [];
        var i;
        for (i = 0; i < n; i++) {
          var eq = actKey(av[i]) === actKey(ar[i]);
          if (!eq) actDiff += 1;
          rows.push(
            "<tr class='" +
              (eq ? "" : "is-diff") +
              "'><td class='n'>" +
              (i + 1) +
              "</td><td>" +
              actHtml(av[i]) +
              "</td><td>" +
              actHtml(ar[i]) +
              "</td></tr>"
          );
        }
        return (
          "<div class='cmp-street'><h4>" +
          escHtml(streetLab(st) || "行动") +
          "<span class='n'>视觉 " +
          av.length +
          " · 规则 " +
          ar.length +
          "</span></h4>" +
          "<div class='table-scroll'><table class='cmp cmp-act'><thead><tr><th class='n'>#</th><th>视觉</th><th>规则</th></tr></thead><tbody>" +
          (rows.join("") || "<tr><td colspan='3'>没有行动</td></tr>") +
          "</tbody></table></div></div>"
        );
      })
      .join("");
    if (actDiff) diffs.push("行动 " + actDiff + " 步");

    var winL = vis ? fmtWin(vis.winners) : "";
    var winR = rule ? fmtWin(rule.winners) : "";
    var winEq = !vis || !rule || sameText(winL, winR);
    if (vis && rule && !winEq) diffs.push("赢家");
    var winHtml = "";
    if (winL || winR) {
      winHtml = winEq
        ? "<div class='cmp-win'>赢家 " + escHtml(dash(winL || winR)) + "</div>"
        : "<div class='cmp-win is-diff'>赢家　视觉 " + escHtml(dash(winL)) + "　·　规则 " + escHtml(dash(winR)) + "</div>";
    }

    var bannerCls = diffs.length ? " is-diff" : "";
    var pills = diffs
      .map(function (d) {
        return "<span class='cmp-pill'>" + escHtml(d) + "</span>";
      })
      .join("");
    var bannerHead = diffs.length
      ? "<strong>不一致 " + diffs.length + " 项</strong><span class='cmp-pills'>" + pills + "</span>"
      : "<strong>视觉与规则一致</strong>";
    var winBlock = winHtml ? "<div class='cmp-sec'>结算</div>" + winHtml : "";
    return (
      "<div class='cmp-banner" +
      bannerCls +
      "'>" +
      bannerHead +
      "<label class='cmp-opt'><input type='checkbox' id='cmp-hide-post'" +
      (hidePost ? " checked" : "") +
      "/> 隐藏前注 / 盲注 / Straddle</label></div>" +
      kpis +
      boardHtml +
      playersHtml +
      (streetsHtml ? "<div class='cmp-sec'>行动</div>" + streetsHtml : "") +
      winBlock
    );
  }

  function copyText(text, btn, okMsg) {
    if (!text) {
      alert("还没有可复制的内容。");
      return;
    }
    var label = btn ? btn.textContent : "";
    function done() {
      setStatus(okMsg);
      if (btn) {
        btn.textContent = "已复制";
        setTimeout(function () {
          btn.textContent = label;
        }, 1200);
      }
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done, function () {
        alert("复制失败");
      });
    } else {
      alert("当前浏览器不能复制，请手动全选 JSON。");
    }
  }

  function lookupPage() {
    var hands = [];
    var bodies = {};
    var currentId = "";
    var hidePosts = true;

    function renderList() {
      var box = $("hand-list");
      var q = (($("q-hand") && $("q-hand").value) || "").trim().toLowerCase();
      var n = 0;
      box.innerHTML = hands
        .map(function (h, i) {
          var hid = String(h.handId || "");
          var blob = (hid + " " + (h.status || "") + " " + (h.source || "")).toLowerCase();
          if (q && blob.indexOf(q) < 0) return "";
          n += 1;
          var active = hid === currentId ? " active" : "";
          var st = h.status || "";
          return (
            "<button type='button' class='" +
            active.trim() +
            "' data-i='" +
            i +
            "' title='" +
            escHtml(hid) +
            "'>" +
            "<div class='hid-row'><span class='idx'>#" +
            (i + 1) +
            "</span><span class='hid'>" +
            escHtml(shortId(hid)) +
            "</span></div>" +
            "<div class='meta'><span class='st " +
            statusClass(st) +
            "'>" +
            escHtml(st || "—") +
            "</span></div></button>"
          );
        })
        .join("");
      $("hand-count").textContent = n + " / " + hands.length;
      box.querySelectorAll("button[data-i]").forEach(function (btn) {
        btn.addEventListener("click", function () {
          openHand(hands[Number(btn.dataset.i)]);
        });
      });
    }

    function fillPane(pre, data, missing) {
      if (data == null) {
        pre.textContent = missing;
        return;
      }
      pre.textContent = pretty(data);
    }

    function paintJson() {
      var body = currentId ? bodies[currentId] : null;
      var hint = $("user-hint");
      var empty = $("json-empty");
      var wrap = $("stage-wrap");
      var copyId = $("q-copy-id");
      hint.textContent = body ? userHint(body) : "";
      if (copyId) copyId.hidden = !currentId;
      if (!currentId) {
        wrap.hidden = true;
        empty.hidden = false;
        empty.textContent = "先查 session，再点左侧一手。";
        return;
      }
      wrap.hidden = false;
      empty.hidden = true;
      if (body === undefined) {
        $("viz-compare").innerHTML = "<p class='hv-miss'>正在拉取视觉 / 规则…</p>";
        $("json-vis").textContent = "正在拉取…";
        $("json-rule").textContent = "正在拉取…";
        return;
      }
      $("viz-compare").innerHTML = renderCompare(
        visModel(visualOf(body)),
        ruleModel(ruleOf(body)),
        hidePosts
      );
      var cb = $("cmp-hide-post");
      if (cb) {
        cb.addEventListener("change", function () {
          hidePosts = cb.checked;
          paintJson();
        });
      }
      fillPane($("json-vis"), visualOf(body), "这一手没有视觉结果。");
      fillPane($("json-rule"), ruleOf(body), "这一手没有规则返回。");
    }

    async function openHand(h) {
      if (!h || !h.handId) return;
      currentId = String(h.handId);
      renderList();
      var n = hands.indexOf(h);
      $("json-title").textContent = (n >= 0 ? "第 " + (n + 1) + " 手" : "对照");
      $("json-title").title = currentId;
      if (!(currentId in bodies)) {
        bodies[currentId] = undefined;
        paintJson();
        try {
          var body = await global.E2EMatch.fetchHandResult(
            fusionBase(),
            h.sessionId || $("q-session").value.trim(),
            h.handId
          );
          bodies[currentId] = body && typeof body === "object" ? body : null;
        } catch (e) {
          bodies[currentId] = null;
          setStatus((e && e.message) || e);
        }
      }
      paintJson();
    }

    async function runQuery() {
      if (!global.E2EMatch) {
        alert("缺少 e2e-match.js，请重新生成站点后刷新。");
        return;
      }
      var sid = $("q-session").value.trim();
      if (!sid) {
        alert("请填写 fusion sessionId");
        return;
      }
      var api = fusionBase();
      try {
        localStorage.setItem("e2e-last-session", sid);
        localStorage.setItem("e2e-last-api", api);
      } catch (e) {}
      $("q-go").disabled = true;
      setStatus("正在列 session 手牌…");
      hands = [];
      bodies = {};
      currentId = "";
      try {
        var ids = global.E2EMatch.parseSessionIds(sid);
        var listed = [];
        for (var i = 0; i < ids.length; i++) {
          listed = listed.concat(await global.E2EMatch.listSessionHands(api, ids[i]));
        }
        hands = listed;
        setStatus("共 " + hands.length + " 手。橙色表示视觉与规则不一致。");
        renderList();
        paintJson();
        if (hands.length === 1) openHand(hands[0]);
      } catch (e) {
        setStatus("");
        alert((e && e.message) || e);
        renderList();
      } finally {
        $("q-go").disabled = false;
      }
    }

    async function downloadAll() {
      if (!hands.length) {
        alert("先查询 session。");
        return;
      }
      $("q-dump").disabled = true;
      var out = [];
      try {
        for (var i = 0; i < hands.length; i++) {
          var h = hands[i];
          setStatus("正在拉视觉 / 规则 " + (i + 1) + "/" + hands.length);
          var body = bodies[h.handId];
          if (body === undefined) {
            try {
              body = await global.E2EMatch.fetchHandResult(fusionBase(), h.sessionId, h.handId);
            } catch (e) {
              body = { error: String((e && e.message) || e) };
            }
            bodies[h.handId] = body;
          }
          out.push({
            sessionId: h.sessionId,
            handId: h.handId,
            status: h.status,
            source: h.source,
            createTime: h.createTime,
            visual: visualOf(body),
            rule: ruleOf(body),
          });
        }
        var blob = new Blob([JSON.stringify(out, null, 2)], { type: "application/json" });
        var a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = "session-" + ($("q-session").value.trim() || "hands") + ".json";
        a.click();
        URL.revokeObjectURL(a.href);
        setStatus("已下载 " + out.length + " 手视觉 / 规则。");
      } finally {
        $("q-dump").disabled = false;
      }
    }

    function copyKind(kind) {
      var body = currentId ? bodies[currentId] : null;
      if (kind === "vis") {
        copyText(pretty(visualOf(body)), $("q-copy-vis"), "已复制视觉 JSON。");
      } else {
        copyText(pretty(ruleOf(body)), $("q-copy-rule"), "已复制规则 JSON。");
      }
    }

    try {
      $("q-session").value = localStorage.getItem("e2e-last-session") || "";
      $("q-api").value = localStorage.getItem("e2e-last-api") || DEFAULT_API;
    } catch (e) {
      $("q-api").value = DEFAULT_API;
    }

    $("q-go").addEventListener("click", runQuery);
    $("q-dump").addEventListener("click", downloadAll);
    $("q-copy-vis").addEventListener("click", function () {
      copyKind("vis");
    });
    $("q-copy-rule").addEventListener("click", function () {
      copyKind("rule");
    });
    $("q-copy-id").addEventListener("click", function () {
      copyText(currentId, $("q-copy-id"), "已复制 handId。");
    });
    $("q-hand").addEventListener("input", renderList);
    $("q-session").addEventListener("keydown", function (e) {
      if (e.key === "Enter") runQuery();
    });
    renderList();
    paintJson();
  }

  global.E2ESessionLookup = { start: lookupPage };
})(window);
