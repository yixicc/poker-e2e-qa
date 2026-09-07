/**
 * 浏览器直连 fusion 查视觉/规则，并与源数据界面树比对。
 * 查询方式和 poker-hand-viewer 一样：fetch(API + /api/fusion/...)，不经过本地 Python。
 */
(function (global) {
  "use strict";

  var CATS = ["卡牌", "文字", "图像", "数字"];
  var POST_SKIP = { POST_BLIND: 1, POST_ANTE: 1, ANTE: 1 };
  var POS_ALIAS = {
    UTG1: "UTG+1",
    UTG2: "UTG+2",
    UTG3: "UTG+3",
    DEALER: "BTN",
    BUTTON: "BTN",
    SMALLBLIND: "SB",
    BIGBLIND: "BB",
  };
  var BLIND_LV = /^\s*(\d+(?:\.\d+)?)\s*\/\s*(\d+(?:\.\d+)?)(?:\s*\((\d+(?:\.\d+)?)\))?/;
  var VIDEO_NUM = /^(\d+)\.mp4$/i;
  var LEN_MARK = "__len__";

  function classify(path) {
    var p = String(path || "").toLowerCase();
    if (/(avatar|dealer|status|image|img)/.test(p)) return "图像";
    if (p.indexOf("card") >= 0) return "卡牌";
    if (/(bet_amount|chips|seat|pot|\.sb|\.bb|ante|player_count)/.test(p)) return "数字";
    return "文字";
  }

  function emitPath(path) {
    if (!path) return false;
    if (path.slice(-6) === ".value") return true;
    var last = path.split(".").pop().split("[")[0];
    return last === "players" || last === "table" || last === "cards" || last === "community_cards";
  }

  function flattenValues(obj, prefix, out) {
    prefix = prefix || "";
    out = out || {};
    if (obj && typeof obj === "object" && !Array.isArray(obj)) {
      var keys = Object.keys(obj);
      if (keys.length === 1 && keys[0] === "value") {
        if (prefix) out[prefix + ".value"] = obj.value;
        return out;
      }
      if (prefix && emitPath(prefix)) out[prefix] = [LEN_MARK, keys.length];
      for (var i = 0; i < keys.length; i++) {
        var k = keys[i];
        flattenValues(obj[k], prefix ? prefix + "." + k : String(k), out);
      }
      return out;
    }
    if (Array.isArray(obj)) {
      if (prefix && emitPath(prefix)) out[prefix] = [LEN_MARK, obj.length];
      for (var j = 0; j < obj.length; j++) flattenValues(obj[j], prefix + "[" + j + "]", out);
      return out;
    }
    if (prefix) out[prefix] = obj;
    return out;
  }

  function parseNum(v) {
    if (v == null || v === true || v === false) return null;
    if (typeof v === "number" && isFinite(v)) return v;
    var s = String(v).trim().replace(/,/g, "").replace(/\s*(bb|筹码)\s*$/i, "").trim();
    if (!s) return null;
    var n = Number(s);
    return isFinite(n) ? n : null;
  }

  function isLen(v) {
    return Array.isArray(v) && v.length === 2 && v[0] === LEN_MARK;
  }

  function valuesEqual(a, b) {
    if (a === b) return true;
    if (isLen(a) && isLen(b)) return a[1] === b[1];
    var na = parseNum(a);
    var nb = parseNum(b);
    if (na != null && nb != null) return Math.abs(na - nb) < 1e-9;
    if (typeof a === "boolean" || typeof b === "boolean") return Boolean(a) === Boolean(b);
    var sa = a == null ? "" : String(a).trim();
    var sb = b == null ? "" : String(b).trim();
    return sa.toLowerCase() === sb.toLowerCase();
  }

  function compareFlat(left, right) {
    var out = {};
    right = right || {};
    var paths = Object.keys(left);
    for (var i = 0; i < paths.length; i++) {
      var path = paths[i];
      var lv = left[path];
      if (!(path in right)) {
        out[path] = "missing";
        continue;
      }
      var rv = right[path];
      if (isLen(lv) || isLen(rv)) {
        out[path] = isLen(lv) && isLen(rv) && lv[1] === rv[1] ? "match" : "len_mismatch";
        continue;
      }
      if (path.slice(-11) === ".name.value") {
        var sa = lv == null ? "" : String(lv);
        var sb = rv == null ? "" : String(rv);
        out[path] = sa === sb ? "match" : "mismatch";
        continue;
      }
      out[path] = valuesEqual(lv, rv) ? "match" : "mismatch";
    }
    return out;
  }

  function normPos(p) {
    var s = String(p || "").trim().toUpperCase().replace(/\s+/g, "");
    if (POS_ALIAS[s]) return POS_ALIAS[s];
    if (s.indexOf("UTG") === 0 && s.length > 3 && /\d/.test(s.charAt(3)) && s.indexOf("+") < 0) {
      return "UTG+" + s.slice(3);
    }
    return s;
  }

  function isPost(act) {
    var u = String(act || "").toUpperCase().replace(/[- ]/g, "_");
    return POST_SKIP[u] || u.indexOf("POST_") === 0;
  }

  function normAction(act) {
    var u = String(act || "").trim().toUpperCase().replace(/[- ]/g, "_");
    if (u === "ALLIN" || u === "ALL_IN") return "ALL-IN";
    return u;
  }

  function compactAct(act) {
    return String(act || "").replace(/[_-]/g, "");
  }

  function posMapFromUi(ui) {
    var out = {};
    var players = (ui && ui.players) || {};
    Object.keys(players).forEach(function (key) {
      if (key.charAt(0) !== "P") return;
      var seat = parseInt(key.slice(1), 10);
      if (!isFinite(seat)) return;
      var pos = normPos((((players[key] || {}).position) || {}).value);
      if (pos) out[pos] = seat;
    });
    return out;
  }

  function resolveSeat(pos, posMap) {
    var p = normPos(pos);
    if (p in posMap) return posMap[p];
    if (p === "UTG+1" && "UTG" in posMap && !("UTG+1" in posMap)) return posMap.UTG;
    return null;
  }

  function parseBlindLevel(s) {
    var m = BLIND_LV.exec(String(s || ""));
    if (!m) return {};
    return { sb: Number(m[1]), bb: Number(m[2]), ante: Number(m[3] || 0) };
  }

  function extractVis(body) {
    if (!body || typeof body !== "object") return { hand: null, blinds: {} };
    var raw = body.rawJson || {};
    var ext = raw.llm_extraction || {};
    var hands = ext.hands || [];
    var hand = hands[0] && typeof hands[0] === "object" ? hands[0] : null;
    var blinds = parseBlindLevel(ext.blind_level);
    var cfg = ext.blinds_config || {};
    if (!blinds.sb && !blinds.bb) {
      blinds = {
        sb: cfg.small_blind,
        bb: cfg.big_blind,
        ante: cfg.ante_per_player != null ? cfg.ante_per_player : cfg.ante,
      };
    }
    return { hand: hand, blinds: blinds };
  }

  function visToUi(hand, blinds, posMap) {
    if (!hand || typeof hand !== "object" || !posMap || !Object.keys(posMap).length) return null;
    var byPos = {};
    (hand.players || []).forEach(function (p) {
      if (p && typeof p === "object" && p.position) byPos[normPos(p.position)] = p;
    });
    var lastAct = {};
    var lastBet = {};
    var folded = {};
    (hand.actions || []).forEach(function (a) {
      if (!a || typeof a !== "object" || isPost(a.action)) return;
      var seat = resolveSeat(a.player_position, posMap);
      if (seat == null) return;
      var act = normAction(a.action);
      lastAct[seat] = act;
      if (["BET", "RAISE", "CALL", "ALLIN"].indexOf(compactAct(act)) >= 0) {
        lastBet[seat] = parseNum(a.amount) || 0;
      }
      if (act === "FOLD") folded[seat] = 1;
    });
    var settle = hand.settlement || {};
    var showdown = Boolean(settle.showdown || hand.outcome === "showdown");
    var players = {};
    Object.keys(posMap).forEach(function (pos) {
      var seat = posMap[pos];
      var p = byPos[pos];
      if (!p) return;
      var cardsRaw = p.shown_cards || [];
      if (p.is_hero && (!cardsRaw || !cardsRaw.length)) cardsRaw = hand.hero_cards || [];
      var cardMap = {};
      (cardsRaw || []).forEach(function (card, ci) {
        if (card) cardMap["P" + ci] = { value: card };
      });
      var status = folded[seat] ? "fold" : showdown ? "show" : "in_hand";
      players["P" + seat] = {
        name: { value: p.nickname || "" },
        action: { value: lastAct[seat] || "" },
        comment: { value: "" },
        cards: cardMap,
        bet_amount: { value: lastBet[seat] != null ? lastBet[seat] : 0 },
        chips: { value: parseNum(p.final_chips) },
        seat: { value: seat },
        dealer: { value: Boolean(p.is_dealer) },
        status: { value: status },
        position: { value: pos },
      };
    });
    var board = [];
    (hand.community_cards || []).forEach(function (x) {
      if (x) board.push({ value: x });
    });
    var pots = hand.pots_structure || {};
    var pot = pots.total_pot;
    if (pot == null) {
      pot = parseNum((hand.pots_info || {}).total_pot);
      if (pot == null) pot = parseNum(hand.final_pot);
    }
    var n = (hand.players || []).length || Object.keys(posMap).length;
    return {
      players: players,
      table: {
        community_cards: board,
        pot: { value: pot },
        sb: { value: blinds.sb },
        bb: { value: blinds.bb },
        ante: { value: blinds.ante },
        player_count: { value: n },
        showdown: { value: showdown },
      },
    };
  }

  function rowCells(row) {
    return Array.isArray(row) ? row : [];
  }

  function ruleToUi(rr, posMap) {
    if (!rr || typeof rr !== "object" || !posMap || !Object.keys(posMap).length) return null;
    var byLabel = {};
    var byPos = {};
    (rr.players || []).forEach(function (row) {
      var cells = rowCells(row);
      if (cells.length < 3) return;
      byLabel[String(cells[0])] = cells;
      byPos[normPos(cells[1])] = cells;
    });
    var lastAct = {};
    var lastBet = {};
    var folded = {};
    (rr.actions || []).forEach(function (a) {
      var cells = rowCells(a);
      if (cells.length < 3 || isPost(cells[2])) return;
      var src = byLabel[String(cells[0])];
      var seat = resolveSeat(src ? src[1] : null, posMap);
      if (seat == null) return;
      var act = normAction(cells[2]);
      lastAct[seat] = act;
      var amt = cells.length > 3 ? cells[3] : 0;
      if (["BET", "RAISE", "CALL", "ALLIN"].indexOf(compactAct(act)) >= 0) {
        lastBet[seat] = parseNum(amt) || 0;
      }
      if (act === "FOLD") folded[seat] = 1;
    });
    var result = rr.result || {};
    var showdown = Boolean(result.showdown);
    var players = {};
    Object.keys(posMap).forEach(function (pos) {
      var seat = posMap[pos];
      var cells = byPos[pos];
      if (!cells) return;
      var hole = cells.length > 3 ? cells[3] : null;
      var shown = cells.length > 6 ? cells[6] : null;
      var cardsRaw = Array.isArray(shown) && shown.length ? shown : hole;
      if (!Array.isArray(cardsRaw)) cardsRaw = [];
      var cardMap = {};
      cardsRaw.forEach(function (card, ci) {
        if (card) cardMap["P" + ci] = { value: card };
      });
      var status = folded[seat] ? "fold" : showdown ? "show" : "in_hand";
      var finalChips = cells.length > 5 ? cells[5] : null;
      players["P" + seat] = {
        name: { value: cells.length > 2 ? cells[2] : "" },
        action: { value: lastAct[seat] || "" },
        comment: { value: "" },
        cards: cardMap,
        bet_amount: { value: lastBet[seat] != null ? lastBet[seat] : 0 },
        chips: { value: parseNum(finalChips) },
        seat: { value: seat },
        dealer: { value: normPos(cells[1]) === "BTN" },
        status: { value: status },
        position: { value: pos },
      };
    });
    var board = [];
    var rawBoard = rr.board;
    if (Array.isArray(rawBoard)) {
      rawBoard.forEach(function (x) {
        if (typeof x === "string" && x) board.push({ value: x });
        else if (Array.isArray(x)) x.forEach(function (c) { if (c) board.push({ value: c }); });
      });
    }
    var blinds = rr.blinds || {};
    var n = (rr.players || []).length || Object.keys(posMap).length;
    return {
      players: players,
      table: {
        community_cards: board,
        pot: { value: result.total_pot },
        sb: { value: blinds.sb },
        bb: { value: blinds.bb },
        ante: { value: blinds.ante },
        player_count: { value: n },
        showdown: { value: showdown },
      },
    };
  }

  function rate(match, total) {
    if (total <= 0) return null;
    return Math.round((1000 * match) / total) / 10;
  }

  function emptyBucket() {
    return { total: 0, match: 0, mismatch: 0, missing: 0, len_mismatch: 0, errors: [] };
  }

  function summarizePair(leftTrees, rightTrees, seqs) {
    var byPath = {};
    for (var i = 0; i < leftTrees.length; i++) {
      var left = leftTrees[i];
      var seq = seqs[i] != null ? seqs[i] : i + 1;
      if (left == null) continue;
      var flatL = flattenValues(left);
      var right = i < rightTrees.length ? rightTrees[i] : null;
      var flatR = right != null ? flattenValues(right) : null;
      var verdicts = compareFlat(flatL, flatR);
      var paths = Object.keys(verdicts);
      var bad = false;
      for (var j = 0; j < paths.length; j++) {
        var kind = verdicts[paths[j]];
        if (!byPath[paths[j]]) byPath[paths[j]] = emptyBucket();
        var b = byPath[paths[j]];
        b.total += 1;
        b[kind] = (b[kind] || 0) + 1;
        if (kind !== "match") bad = true;
      }
      if (bad) {
        for (var k = 0; k < paths.length; k++) {
          if (verdicts[paths[k]] === "match") continue;
          var errs = byPath[paths[k]].errors;
          if (errs.indexOf(seq) < 0) errs.push(seq);
        }
      }
    }
    var stats = {};
    var catTot = {};
    CATS.forEach(function (c) { catTot[c] = [0, 0]; });
    var allM = 0;
    var allT = 0;
    Object.keys(byPath).forEach(function (path) {
      var b = byPath[path];
      var total = b.total;
      var matchN = b.match;
      stats[path] = {
        total: total,
        match: matchN,
        mismatch: b.mismatch,
        missing: b.missing,
        len_mismatch: b.len_mismatch,
        rate: rate(matchN, total),
        n_error: b.errors.length,
        errors: b.errors.slice(0, 12),
      };
      var cat = classify(path);
      if (catTot[cat]) {
        catTot[cat][0] += matchN;
        catTot[cat][1] += total;
      }
      allM += matchN;
      allT += total;
    });
    var rates = { all: rate(allM, allT) };
    CATS.forEach(function (cat) {
      var m = catTot[cat][0];
      var t = catTot[cat][1];
      rates[cat] = t === 0 ? "—" : rate(m, t);
    });
    return { rates: rates, fields: stats };
  }

  function matchBatch(goldTrees, fusionAligned) {
    var visTrees = [];
    var ruleTrees = [];
    for (var i = 0; i < goldTrees.length; i++) {
      var gold = goldTrees[i];
      var posMap = posMapFromUi(gold);
      var item = i < fusionAligned.length ? fusionAligned[i] : null;
      var body = item && item.body;
      var extracted = extractVis(body);
      visTrees.push(extracted.hand ? visToUi(extracted.hand, extracted.blinds, posMap) : null);
      var rr = body && typeof body === "object" ? body.ruleResult : null;
      ruleTrees.push(rr ? ruleToUi(rr, posMap) : null);
    }
    var seqs = goldTrees.map(function (_, i) { return i + 1; });
    var gtVis = summarizePair(goldTrees, visTrees, seqs);
    var visRule = summarizePair(visTrees, ruleTrees, seqs);
    var gtRule = summarizePair(goldTrees, ruleTrees, seqs);
    var nVis = visTrees.filter(Boolean).length;
    var nRule = ruleTrees.filter(Boolean).length;
    return {
      pair_rates: { gt_vis: gtVis.rates, vis_rule: visRule.rates, gt_rule: gtRule.rates },
      field_stats: { gt_vis: gtVis.fields, vis_rule: visRule.fields, gt_rule: gtRule.fields },
      n_vis: nVis,
      n_rule: nRule,
      n_gold: goldTrees.length,
    };
  }

  function unwrap(data) {
    if (data && typeof data === "object" && data.result !== undefined) return data.result;
    return data;
  }

  function parseSessionIds(raw) {
    return String(raw || "")
      .trim()
      .split(/[\s,;，、]+/)
      .map(function (p) { return p.trim(); })
      .filter(function (p, i, arr) { return p && arr.indexOf(p) === i; });
  }

  function videoName(url) {
    var path = "";
    try {
      path = new URL(url, "http://local").pathname;
    } catch (e) {
      path = String(url || "");
    }
    return decodeURIComponent((path.split("/").pop() || "").split("?")[0]);
  }

  function videoStem(url) {
    return videoName(url).replace(/\.[^.]+$/, "");
  }

  function sortSessionHands(hands) {
    return hands.slice().sort(function (a, b) {
      var ma = VIDEO_NUM.exec(videoName(a.videoUrl || ""));
      var mb = VIDEO_NUM.exec(videoName(b.videoUrl || ""));
      if (ma || mb) {
        if (ma && !mb) return -1;
        if (!ma && mb) return 1;
        if (ma && mb) return parseInt(ma[1], 10) - parseInt(mb[1], 10);
      }
      var ta = parseInt(a.createTimeMs, 10) || 0;
      var tb = parseInt(b.createTimeMs, 10) || 0;
      return ta - tb;
    });
  }

  async function fusionGet(base, path) {
    var url = String(base || "").replace(/\/+$/, "") + path;
    var res;
    try {
      res = await fetch(url);
    } catch (e) {
      throw new Error("连不上 fusion：" + url);
    }
    if (!res.ok) throw new Error("fusion " + res.status + " " + path);
    return unwrap(await res.json());
  }

  async function listSessionRecords(base, sessionId) {
    var out = [];
    var page = 1;
    while (page <= 50) {
      var q = "page=" + page + "&size=100&sessionId=" + encodeURIComponent(sessionId);
      var res = await fusionGet(base, "/api/fusion/hand-records?" + q);
      if (!res || typeof res !== "object") break;
      var chunk = res.list || [];
      out = out.concat(chunk);
      var total = parseInt(res.total, 10) || 0;
      if (!chunk.length || (total && out.length >= total)) break;
      page += 1;
    }
    return out;
  }

  async function listSessionHands(base, sessionId) {
    var raw = await fusionGet(base, "/api/fusion/hands-by-session?sessionId=" + encodeURIComponent(sessionId));
    var lst = Array.isArray(raw) ? raw : (raw && raw.list) || [];
    var recs = await listSessionRecords(base, sessionId);
    var byId = {};
    recs.forEach(function (r) {
      if (r && r.handId) byId[String(r.handId)] = r;
    });
    var src = lst.length
      ? lst
      : recs.map(function (r) {
          return {
            handId: r.handId,
            sessionId: r.sessionId || sessionId,
            status: r.status,
            createTime: r.createTime,
            videoUrl: r.videoUrl,
          };
        });
    var hands = [];
    var seen = {};
    src.forEach(function (item) {
      var hid = String((item && item.handId) || "");
      if (!hid || seen[hid]) return;
      seen[hid] = 1;
      var rec = byId[hid] || {};
      hands.push({
        handId: hid,
        sessionId: String(item.sessionId || rec.sessionId || sessionId),
        status: item.status || rec.status,
        videoUrl: rec.videoUrl || item.videoUrl || "",
        createTimeMs: rec.createTime || item.createTime || 0,
      });
    });
    return sortSessionHands(hands);
  }

  async function mapPool(items, limit, fn) {
    var out = new Array(items.length);
    var i = 0;
    async function worker() {
      while (i < items.length) {
        var idx = i++;
        out[idx] = await fn(items[idx], idx);
      }
    }
    var n = Math.min(limit, items.length) || 1;
    var workers = [];
    for (var w = 0; w < n; w++) workers.push(worker());
    await Promise.all(workers);
    return out;
  }

  async function fetchSessionResults(base, sessionIds, onProgress) {
    var listed = [];
    for (var s = 0; s < sessionIds.length; s++) {
      listed = listed.concat(await listSessionHands(base, sessionIds[s]));
    }
    if (!listed.length) throw new Error("fusion 这个 sessionId 下没有手牌");
    var done = 0;
    return mapPool(listed, 6, async function (meta) {
      var body = null;
      try {
        var path =
          "/api/fusion/hand-result?sessionId=" +
          encodeURIComponent(meta.sessionId) +
          "&handId=" +
          encodeURIComponent(meta.handId);
        var res = await fusionGet(base, path);
        body = res && typeof res === "object" ? res : null;
      } catch (e) {
        body = null;
      }
      done += 1;
      if (onProgress) onProgress("正在拉 fusion 手牌 " + done + "/" + listed.length);
      return Object.assign({}, meta, { body: body });
    });
  }

  function alignToCases(cases, fusionHands) {
    var byStem = {};
    fusionHands.forEach(function (h) {
      var stem = videoStem(h.videoUrl || "");
      if (stem) byStem[stem] = h;
    });
    var nHit = 0;
    cases.forEach(function (c) {
      var id = String((c && c.hand_id) || "");
      if (id && byStem[id]) nHit += 1;
    });
    if (fusionHands.length && nHit && (nHit === fusionHands.length || nHit >= Math.max(1, Math.floor(0.8 * fusionHands.length)))) {
      return cases.map(function (c) { return byStem[String((c && c.hand_id) || "")] || null; });
    }
    return cases.map(function (_, i) { return i < fusionHands.length ? fusionHands[i] : null; });
  }

  async function lookup(opts) {
    var base = String((opts && opts.base) || "http://192.168.110.81:8080").replace(/\/+$/, "");
    var sessionIds = parseSessionIds(opts && opts.sessionId);
    var gold = opts && opts.gold;
    if (!sessionIds.length) throw new Error("请填写 fusion sessionId");
    if (!gold || !Array.isArray(gold.trees) || !gold.trees.length) {
      throw new Error("没有源数据界面树。请用完整的 e2e-quality 目录打开 index.html。");
    }
    var onProgress = opts && opts.onProgress;
    if (onProgress) onProgress("正在列 fusion 手牌…");
    var fusionHands = await fetchSessionResults(base, sessionIds, onProgress);
    var cases = gold.cases && gold.cases.length ? gold.cases : gold.trees.map(function (_, i) {
      return { hand_id: "", seq: i + 1 };
    });
    if (onProgress) onProgress("正在比对 " + gold.trees.length + " 手源数据…");
    var aligned = alignToCases(cases, fusionHands);
    var result = matchBatch(gold.trees, aligned);
    result.n_fusion = fusionHands.length;
    result.session_ids = sessionIds;
    return result;
  }

  global.E2EMatch = {
    lookup: lookup,
    parseSessionIds: parseSessionIds,
    matchBatch: matchBatch,
  };
})(window);
