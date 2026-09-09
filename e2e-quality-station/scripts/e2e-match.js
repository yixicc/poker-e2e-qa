/**
 * 浏览器直连 fusion 查视觉/规则，并与源数据界面树比对。
 * 查询方式和 poker-hand-viewer 一样：fetch(API + /api/fusion/...)，不经过本地 Python。
 */
(function (global) {
  "use strict";

  var CATS = ["卡牌", "行动", "文字", "图像", "数字"];
  var POST_SKIP = {
    POST_BLIND: 1, POST_ANTE: 1, ANTE: 1,
    STRADDLE: 1, POST_STRADDLE: 1,
    COST_ANTE: 1, COST_STRADDLE: 1, COST_SB: 1, COST_BB: 1, COST_BLIND: 1
  };
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
    if (p.indexOf("history.") === 0) return "行动";
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

  var STREET_FLAT = ["preflop", "flop", "turn", "river"];
  var SEQ_STREET_LAB = { preflop: "翻前", flop: "翻牌", turn: "转牌", river: "河牌" };

  function actionLabel(act) {
    var u = normAction(act);
    if (!u) return "";
    if (u === "POST_BLIND" || u === "COST_SB" || u === "COST_BB" || u === "COST_BLIND" ||
        (u.indexOf("BLIND") >= 0 && (u.indexOf("POST") >= 0 || u.indexOf("COST") >= 0))) {
      return "盲注";
    }
    if (u.indexOf("STRADDLE") >= 0) return "straddle";
    if (u === "POST_ANTE" || u === "COST_ANTE" || u === "ANTE" || u.indexOf("ANTE") >= 0) return "前注";
    if (u === "ALLIN" || u === "ALL_IN" || u === "ALL-IN") return "ALL-IN";
    return u;
  }

  function formatAct(a) {
    if (!a) return "";
    var pos = String(a.who || a.pos || (a.seat != null ? "P" + a.seat : "")).trim();
    var verb = actionLabel(a.action) || actVerb(a.action);
    if (showAmt(a.action) && a.amount != null && a.amount !== "") {
      return (pos + " " + verb + " " + fmtAmt(a.amount)).trim();
    }
    return (pos + " " + verb).trim();
  }

  function flattenHistory(hist) {
    if (!hist || typeof hist !== "object") return {};
    var posts = { preflop: [], flop: [], turn: [], river: [] };
    var vols = { preflop: [], flop: [], turn: [], river: [] };
    ((hist.actions) || []).forEach(function (a) {
      if (!a) return;
      var st = a.street || "preflop";
      if (!vols[st]) return;
      (a.post ? posts : vols)[st].push(a);
    });
    var out = {};
    STREET_FLAT.forEach(function (st) {
      [["post", posts], ["vol", vols]].forEach(function (pair) {
        var lst = pair[1][st];
        if (!lst.length) return;
        var prefix = "history." + pair[0] + "." + st;
        out[prefix] = [LEN_MARK, lst.length];
        lst.forEach(function (a, i) {
          var p = prefix + "[" + i + "]";
          out[p + ".who"] = a.pos || "";
          out[p + ".action"] = actionLabel(a.action);
          out[p + ".amount"] = a.amount;
        });
      });
    });
    return out;
  }

  function seqGroups(hist) {
    var posts = { preflop: [], flop: [], turn: [], river: [] };
    var vols = { preflop: [], flop: [], turn: [], river: [] };
    (((hist && hist.actions) || [])).forEach(function (a) {
      if (!a) return;
      var st = a.street || "preflop";
      if (!vols[st]) return;
      var step = {
        who: normPos(a.pos || a.who || ""),
        action: actionLabel(a.action),
        amount: a.amount
      };
      (a.post ? posts : vols)[st].push(step);
    });
    var groups = [];
    STREET_FLAT.forEach(function (st) {
      [["post", posts, "盲注"], ["vol", vols, ""]].forEach(function (row) {
        groups.push({
          key: row[0] + "." + st,
          lab: (SEQ_STREET_LAB[st] || st) + row[2],
          steps: row[1][st]
        });
      });
    });
    return groups;
  }

  function stepEqual(a, b) {
    return a.who === b.who && a.action === b.action && valuesEqual(a.amount, b.amount);
  }

  function stepPart(a, b) {
    if (a.who !== b.who) return "位置";
    if (a.action !== b.action) return "动作";
    return "额";
  }

  function compareSeq(leftHist, rightHist, rightMissing) {
    var leftG = seqGroups(leftHist);
    var leftN = 0;
    leftG.forEach(function (g) { leftN += g.steps.length; });
    if (rightMissing) {
      return {
        exact: leftN === 0,
        miss: leftN > 0,
        len_diff: leftN > 0,
        step_n: 0,
        step_t: leftN,
        left_n: leftN,
        right_n: 0,
        hint: leftN ? "缺记录" : ""
      };
    }
    var rightG = seqGroups(rightHist);
    var stepN = 0;
    var stepT = 0;
    var rightN = 0;
    var exact = true;
    var lenDiff = false;
    var hint = "";
    function setHint(h) {
      if (!hint) hint = h;
    }
    for (var i = 0; i < leftG.length; i++) {
      var ls = leftG[i].steps;
      var rs = rightG[i].steps;
      var lab = leftG[i].lab;
      rightN += rs.length;
      if (ls.length !== rs.length) {
        exact = false;
        lenDiff = true;
        if (rs.length < ls.length) setHint(lab + "漏" + (ls.length - rs.length) + "步");
        else setHint(lab + "多" + (rs.length - ls.length) + "步");
      }
      var n = Math.min(ls.length, rs.length);
      for (var j = 0; j < ls.length; j++) {
        stepT += 1;
        if (j < n && stepEqual(ls[j], rs[j])) {
          stepN += 1;
        } else {
          exact = false;
          if (j < n && ls.length === rs.length) {
            setHint(lab + "第" + (j + 1) + "次" + stepPart(ls[j], rs[j]));
          }
        }
      }
      if (rs.length > ls.length) exact = false;
    }
    return {
      exact: exact,
      miss: false,
      len_diff: lenDiff,
      step_n: stepN,
      step_t: stepT,
      left_n: leftN,
      right_n: rightN,
      hint: exact ? "" : hint
    };
  }

  function summarizeSeq(leftTrees, rightTrees, leftHists, rightHists) {
    var exactN = 0;
    var exactT = 0;
    var stepN = 0;
    var stepT = 0;
    var nLen = 0;
    var nMiss = 0;
    var per = [];
    for (var i = 0; i < leftTrees.length; i++) {
      if (leftTrees[i] == null) {
        per.push(null);
        continue;
      }
      var lh = leftHists ? leftHists[i] : null;
      var rh = rightHists ? rightHists[i] : null;
      var miss = i >= rightTrees.length || rightTrees[i] == null;
      var cmp = compareSeq(lh, miss ? null : rh, miss);
      exactT += 1;
      if (cmp.exact) exactN += 1;
      stepN += cmp.step_n;
      stepT += cmp.step_t;
      if (cmp.len_diff) nLen += 1;
      if (cmp.miss) nMiss += 1;
      per.push(cmp);
    }
    return {
      exact: rate(exactN, exactT),
      exact_n: exactN,
      exact_t: exactT,
      steps: rate(stepN, stepT),
      step_n: stepN,
      step_t: stepT,
      n_len: nLen,
      n_miss: nMiss,
      per: per
    };
  }

  function fillInitChips(ui, hist) {
    if (!ui || typeof ui !== "object" || !ui.players) return ui;
    var bySeat = {};
    ((hist && hist.players) || []).forEach(function (p) {
      if (p && p.seat != null) bySeat[p.seat] = p;
    });
    Object.keys(ui.players).forEach(function (key) {
      var node = ui.players[key];
      if (!node || typeof node !== "object") return;
      var cur = node.init_chips && node.init_chips.value;
      if (cur != null && cur !== "") return;
      var seat = parseInt(String(key).slice(1), 10);
      var p = bySeat[seat];
      var v = p ? p.init : undefined;
      if (v == null || v === "") return;
      node.init_chips = { value: v };
    });
    return ui;
  }

  function flattenHand(ui, hist) {
    fillInitChips(ui, hist);
    var flat = flattenValues(ui || {});
    var extra = flattenHistory(hist);
    Object.keys(extra).forEach(function (k) { flat[k] = extra[k]; });
    Object.keys(flat).forEach(function (path) {
      if (skipMatchPath(path)) delete flat[path];
    });
    return flat;
  }

  function skipMatchPath(path) {
    var p = String(path || "").toLowerCase();
    if (p.indexOf("history.") === 0) return false;
    return p.indexOf(".action") >= 0 || p.indexOf("bet_amount") >= 0 || p.indexOf(".comment") >= 0;
  }

  function valueAt(ui, hist, path) {
    var flat = flattenHand(ui, hist);
    return path in flat ? flat[path] : undefined;
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
    if (!u) return false;
    if (POST_SKIP[u]) return true;
    return u.indexOf("POST_") === 0 || u.indexOf("COST_") === 0;
  }

  function pickVisPot(hand) {
    if (!hand || typeof hand !== "object") return undefined;
    var settle = hand.settlement || {};
    var pots = hand.pots_structure || {};
    var info = hand.pots_info || {};
    var result = hand.result || {};
    var cands = [
      result.total_pot, settle.total_pot, pots.total_pot, info.total_pot,
      settle.pot, hand.final_pot, hand.total_pot
    ];
    for (var i = 0; i < cands.length; i++) {
      if (cands[i] == null || cands[i] === "") continue;
      var n = parseNum(cands[i]);
      return n != null ? n : cands[i];
    }
    return undefined;
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
        lastBet[seat] = parseNum(a.amount);
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
        bet_amount: { value: lastBet[seat] },
        init_chips: { value: parseNum(p.initial_chips) },
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
    var pot = pickVisPot(hand);
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
        lastBet[seat] = parseNum(amt);
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
      var initChips = cells.length > 4 ? cells[4] : null;
      players["P" + seat] = {
        name: { value: cells.length > 2 ? cells[2] : "" },
        action: { value: lastAct[seat] || "" },
        comment: { value: "" },
        cards: cardMap,
        bet_amount: { value: lastBet[seat] },
        init_chips: { value: parseNum(initChips) },
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

  function summarizePair(leftTrees, rightTrees, seqs, leftHists, rightHists) {
    var byPath = {};
    for (var i = 0; i < leftTrees.length; i++) {
      var left = leftTrees[i];
      var seq = seqs[i] != null ? seqs[i] : i + 1;
      if (left == null) continue;
      var flatL = flattenHand(left, leftHists ? leftHists[i] : null);
      var right = i < rightTrees.length ? rightTrees[i] : null;
      var rh = rightHists ? rightHists[i] : null;
      var flatR = right != null ? flattenHand(right, rh) : null;
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
        errors: b.errors,
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

  function pairRateOne(left, right, leftH, rightH) {
    if (left == null) return { rate: null, miss: true };
    var verdicts = compareFlat(flattenHand(left, leftH), right != null ? flattenHand(right, rightH) : null);
    var matchN = 0;
    var total = 0;
    Object.keys(verdicts).forEach(function (p) {
      total += 1;
      if (verdicts[p] === "match") matchN += 1;
    });
    return { rate: rate(matchN, total), miss: right == null };
  }

  function matchBatch(goldTrees, fusionAligned, goldHists) {
    var visTrees = [];
    var ruleTrees = [];
    var visHists = [];
    var ruleHists = [];
    for (var i = 0; i < goldTrees.length; i++) {
      var gold = goldTrees[i];
      var posMap = posMapFromUi(gold);
      var item = i < fusionAligned.length ? fusionAligned[i] : null;
      var body = item && item.body;
      var extracted = extractVis(body);
      visTrees.push(extracted.hand ? visToUi(extracted.hand, extracted.blinds, posMap) : null);
      visHists.push(extracted.hand ? visHistory(body, posMap) : null);
      var rr = body && typeof body === "object" ? body.ruleResult : null;
      ruleTrees.push(rr ? ruleToUi(rr, posMap) : null);
      ruleHists.push(rr ? ruleHistory(rr, posMap) : null);
    }
    var seqs = goldTrees.map(function (_, i) { return i + 1; });
    var goldHistList = goldHists || [];
    var gtVis = summarizePair(goldTrees, visTrees, seqs, goldHistList, visHists);
    var visRule = summarizePair(visTrees, ruleTrees, seqs, visHists, ruleHists);
    var gtRule = summarizePair(goldTrees, ruleTrees, seqs, goldHistList, ruleHists);
    var seqGtVis = summarizeSeq(goldTrees, visTrees, goldHistList, visHists);
    var seqVisRule = summarizeSeq(visTrees, ruleTrees, visHists, ruleHists);
    var seqGtRule = summarizeSeq(goldTrees, ruleTrees, goldHistList, ruleHists);
    var nVis = visTrees.filter(Boolean).length;
    var nRule = ruleTrees.filter(Boolean).length;
    function seqRatesOf(s) {
      return {
        exact: s.exact,
        exact_n: s.exact_n,
        exact_t: s.exact_t,
        steps: s.steps,
        step_n: s.step_n,
        step_t: s.step_t,
        n_len: s.n_len,
        n_miss: s.n_miss
      };
    }
    var hands = goldTrees.map(function (_, i) {
      var item = i < fusionAligned.length ? fusionAligned[i] : null;
      var gv = pairRateOne(goldTrees[i], visTrees[i], goldHistList[i], visHists[i]);
      var vr = pairRateOne(visTrees[i], ruleTrees[i], visHists[i], ruleHists[i]);
      var gr = pairRateOne(goldTrees[i], ruleTrees[i], goldHistList[i], ruleHists[i]);
      return {
        seq: i + 1,
        fusionHandId: (item && item.handId) || "",
        sessionId: (item && item.sessionId) || "",
        miss_vis: !visTrees[i],
        miss_rule: !ruleTrees[i],
        gt_vis: gv.rate,
        vis_rule: vr.rate,
        gt_rule: gr.rate,
        action_seq: {
          gt_vis: seqGtVis.per[i],
          vis_rule: seqVisRule.per[i],
          gt_rule: seqGtRule.per[i]
        }
      };
    });
    return {
      pair_rates: { gt_vis: gtVis.rates, vis_rule: visRule.rates, gt_rule: gtRule.rates },
      field_stats: { gt_vis: gtVis.fields, vis_rule: visRule.fields, gt_rule: gtRule.fields },
      seq_rates: {
        gt_vis: seqRatesOf(seqGtVis),
        vis_rule: seqRatesOf(seqVisRule),
        gt_rule: seqRatesOf(seqGtRule)
      },
      n_vis: nVis,
      n_rule: nRule,
      n_gold: goldTrees.length,
      hands: hands,
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

  function alignToCases(cases, fusionHands, opts) {
    opts = opts || {};
    var byStem = {};
    fusionHands.forEach(function (h) {
      var stem = videoStem(h.videoUrl || "");
      if (stem && !byStem[stem]) byStem[stem] = h;
    });
    var nHit = 0;
    cases.forEach(function (c) {
      var id = String((c && c.hand_id) || "");
      if (id && byStem[id]) nHit += 1;
    });
    var useId = !!opts.forceHandId || (
      fusionHands.length && nHit &&
      (nHit === fusionHands.length || nHit >= Math.max(1, Math.floor(0.8 * fusionHands.length)))
    );
    var used = {};
    var aligned;
    if (useId) {
      aligned = cases.map(function (c) {
        var h = byStem[String((c && c.hand_id) || "")] || null;
        if (h && h.handId) used[String(h.handId)] = 1;
        return h;
      });
    } else {
      aligned = cases.map(function (_, i) {
        var h = i < fusionHands.length ? fusionHands[i] : null;
        if (h && h.handId) used[String(h.handId)] = 1;
        return h;
      });
    }
    var unmatchedGold = [];
    aligned.forEach(function (h, i) {
      if (h) return;
      var c = cases[i] || {};
      unmatchedGold.push({ seq: c.seq != null ? c.seq : i + 1, hand_id: c.hand_id || "" });
    });
    var unmatchedFusion = fusionHands.filter(function (h) {
      return h && h.handId && !used[String(h.handId)];
    }).map(function (h) {
      return {
        fusionHandId: h.handId,
        sessionId: h.sessionId || "",
        video: videoStem(h.videoUrl || ""),
      };
    });
    var nMatched = aligned.filter(Boolean).length;
    return {
      aligned: aligned,
      mode: useId ? "hand_id" : "index",
      n_gold: cases.length,
      n_fusion: fusionHands.length,
      n_matched: nMatched,
      unmatched_gold: unmatchedGold,
      unmatched_fusion: unmatchedFusion,
    };
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
    var pack = alignToCases(cases, fusionHands, { forceHandId: sessionIds.length > 1 });
    var result = matchBatch(gold.trees, pack.aligned, gold.histories);
    result.n_fusion = fusionHands.length;
    result.align = {
      mode: pack.mode,
      n_gold: pack.n_gold,
      n_fusion: pack.n_fusion,
      n_matched: pack.n_matched,
      unmatched_gold: pack.unmatched_gold,
      unmatched_fusion: pack.unmatched_fusion,
    };
    result.session_ids = sessionIds;
    (result.hands || []).forEach(function (h, i) {
      h.hand_id = String((cases[i] && cases[i].hand_id) || "");
    });
    return result;
  }

  async function fetchHandResult(base, sessionId, handId) {
    var path =
      "/api/fusion/hand-result?sessionId=" +
      encodeURIComponent(sessionId) +
      "&handId=" +
      encodeURIComponent(handId);
    var res = await fusionGet(base, path);
    return res && typeof res === "object" ? res : null;
  }

  function stageTrees(gold, body) {
    var posMap = posMapFromUi(gold || {});
    var extracted = extractVis(body);
    var vis = extracted.hand ? visToUi(extracted.hand, extracted.blinds, posMap) : null;
    var rr = body && typeof body === "object" ? body.ruleResult : null;
    var rule = rr ? ruleToUi(rr, posMap) : null;
    return { vis: vis, rule: rule };
  }

  function displayVal(v) {
    if (v == null || v === "") return "—";
    if (Array.isArray(v) && v[0] === "__len__") return "len " + v[1];
    if (typeof v === "boolean") return v ? "true" : "false";
    if (typeof v === "object") {
      try { return JSON.stringify(v); } catch (e) { return String(v); }
    }
    return String(v);
  }

  function causeOf(g, v, r, hasVis, hasRule) {
    if (!hasVis && !hasRule) return { id: "miss", lab: "缺视觉/规则" };
    if (!hasVis) return { id: "miss", lab: "缺视觉" };
    var gv = valuesEqual(g, v);
    var vr = hasRule ? valuesEqual(v, r) : false;
    var gr = hasRule ? valuesEqual(g, r) : false;
    if (gv && (!hasRule || vr)) return { id: "ok", lab: "匹配" };
    if (!gv && hasRule && gr) return { id: "fix", lab: "规则救回" };
    if (gv && hasRule && !vr) return { id: "rule", lab: "规则引入" };
    if (!gv && (!hasRule || vr)) return { id: "vis", lab: "视觉引入" };
    return { id: "both", lab: "视觉错、规则又偏" };
  }

  function compareStages(gold, vis, rule, goldHist, visHist, ruleHist) {
    var flatG = flattenHand(gold || {}, goldHist);
    var flatV = vis ? flattenHand(vis, visHist) : {};
    var flatR = rule ? flattenHand(rule, ruleHist) : {};
    var paths = Object.keys(flatG);
    return paths.map(function (path) {
      var g = flatG[path];
      var v = vis ? (path in flatV ? flatV[path] : undefined) : undefined;
      var r = rule ? (path in flatR ? flatR[path] : undefined) : undefined;
      var cause = causeOf(g, v, r, !!vis, !!rule);
      return {
        path: path,
        gold: g,
        vis: vis ? v : undefined,
        rule: rule ? r : undefined,
        cause: cause,
      };
    });
  }

  function normStreet(s) {
    var u = String(s || "").trim().toLowerCase().replace(/[\s-]+/g, "_");
    if (u === "pre_hand" || u === "prehand" || u === "setup") return "";
    if (u === "pre_flop" || u === "preflop") return "preflop";
    if (u === "flop") return "flop";
    if (u === "turn") return "turn";
    if (u === "river") return "river";
    return u;
  }

  var STREET_ORDER = ["preflop", "flop", "turn", "river"];
  var STREET_LAB = { preflop: "翻前", flop: "翻牌", turn: "转牌", river: "河牌" };

  function winnerSeats(raw, posMap, players) {
    var list = raw == null || raw === "" ? [] : (Array.isArray(raw) ? raw : [raw]);
    var out = [];
    list.forEach(function (w) {
      if (w == null || w === "") return;
      if (typeof w === "object") {
        if (w.seat != null) w = w.seat;
        else if (w.position) w = w.position;
        else if (w.nickname) w = w.nickname;
        else if (w.name) w = w.name;
      }
      if (typeof w === "number" && isFinite(w)) {
        out.push(w);
        return;
      }
      var s = String(w).trim();
      var m = s.match(/^P(\d+)$/i);
      if (m) {
        out.push(Number(m[1]));
        return;
      }
      if (/^\d+$/.test(s)) {
        out.push(Number(s));
        return;
      }
      var pos = normPos(s);
      if (posMap && pos in posMap) {
        out.push(posMap[pos]);
        return;
      }
      (players || []).forEach(function (p) {
        if (p && p.name && p.name === s) out.push(p.seat);
        else if (p && p.hero && /hero/i.test(s)) out.push(p.seat);
      });
    });
    var seen = {};
    return out.filter(function (seat) {
      if (seat == null || seen[seat]) return false;
      seen[seat] = 1;
      return true;
    });
  }

  function visBoard(hand) {
    var by = (hand && hand.community_cards_by_street) || {};
    var flop = visCardList(by.flop);
    var turn = visCardList(by.turn);
    var river = visCardList(by.river);
    if (!flop.length && !turn.length && !river.length) {
      var all = visCardList(hand && hand.community_cards);
      flop = all.slice(0, 3);
      turn = all.slice(3, 4);
      river = all.slice(4, 5);
    }
    return { flop: flop, turn: turn, river: river };
  }

  function visCardList(raw) {
    if (raw == null || raw === "") return [];
    if (Array.isArray(raw)) return raw.filter(function (x) { return x; });
    return [raw];
  }

  function visHole(p, hand) {
    var hole = visCardList(p && (p.shown_cards || p.hole_cards || p.cards));
    if (p && p.is_hero && !hole.length) hole = visCardList(hand && hand.hero_cards);
    return hole;
  }

  function factVal(obj, keys) {
    if (!obj || typeof obj !== "object") return undefined;
    for (var i = 0; i < keys.length; i++) {
      if (!Object.prototype.hasOwnProperty.call(obj, keys[i])) continue;
      var v = obj[keys[i]];
      if (v == null || v === "") continue;
      return v;
    }
    return undefined;
  }

  function withActionFacts(base, raw) {
    var pot = factVal(raw, ["pot_after", "current_pot", "potAfter", "pot"]);
    var chips = factVal(raw, [
      "remaining_chips", "chips_after", "remainingChips",
      "stack_after", "current_chips", "chipsAfter"
    ]);
    var ts = factVal(raw, ["timestamp", "time", "elapsed", "action_time", "ts"]);
    if (pot !== undefined) {
      var pn = parseNum(pot);
      base.pot = pn != null ? pn : pot;
    }
    if (chips !== undefined) {
      var cn = parseNum(chips);
      base.chips = cn != null ? cn : chips;
    }
    if (ts !== undefined) base.timestamp = ts;
    return base;
  }

  function visHistory(body, posMap) {
    var extracted = extractVis(body);
    var hand = extracted.hand;
    if (!hand || typeof hand !== "object") return null;
    var ext = ((body && body.rawJson) || {}).llm_extraction || {};
    var blinds = extracted.blinds || {};
    var cfg = ext.blinds_config || {};
    var straddle = parseNum(cfg.straddle != null ? cfg.straddle : blinds.straddle);
    var byPos = {};
    (hand.players || []).forEach(function (p) {
      if (p && p.position) byPos[normPos(p.position)] = p;
    });
    var players = [];
    Object.keys(posMap || {}).forEach(function (pos) {
      var seat = posMap[pos];
      var p = byPos[pos];
      var init = p ? parseNum(p.initial_chips) : undefined;
      var fin = p ? parseNum(p.final_chips) : undefined;
      var net = p ? parseNum(p.net_won || p.profit || p.chips_won) : undefined;
      players.push({
        seat: seat,
        pos: pos,
        name: p ? (p.nickname || "") : "",
        init: init,
        final: fin,
        net: net,
        cards: p ? visHole(p, hand) : [],
        hero: !!(p && p.is_hero),
      });
    });
    players.sort(function (a, b) { return a.seat - b.seat; });
    var sbSeat, bbSeat, straddleSeat;
    var actions = [];
    (hand.actions || []).forEach(function (a) {
      if (!a || typeof a !== "object") return;
      var seat = resolveSeat(a.player_position, posMap);
      var pos = normPos(a.player_position);
      var up = normAction(a.action);
      if (isPost(a.action)) {
        var amt = parseNum(a.amount);
        if (/straddle/i.test(String(a.action || ""))) {
          if (straddle == null && amt != null) straddle = amt;
          if (seat != null) straddleSeat = seat;
        } else if (pos === "SB") sbSeat = seat;
        else if (pos === "BB") bbSeat = seat;
        if (seat == null) return;
        actions.push(withActionFacts({
          street: "preflop",
          seat: seat,
          pos: pos,
          action: up,
          amount: amt,
          post: true,
        }, a));
        return;
      }
      var st = normStreet(a.street);
      if (!st) return;
      actions.push(withActionFacts({
        street: st,
        seat: seat,
        pos: pos,
        action: up,
        amount: parseNum(a.amount),
        post: false,
      }, a));
    });
    if (sbSeat == null) sbSeat = posMap.SB;
    if (bbSeat == null) bbSeat = posMap.BB;
    var settle = hand.settlement || {};
    var winners = winnerSeats(
      settle.winners || settle.winner_seats || settle.winner_position ||
        settle.winner_nickname || hand.winners || hand.winner,
      posMap,
      players
    );
    return {
      sb: blinds.sb,
      bb: blinds.bb,
      ante: blinds.ante,
      straddle: straddle,
      sb_seat: sbSeat,
      bb_seat: bbSeat,
      straddle_seat: straddleSeat,
      players: players,
      actions: actions,
      board: visBoard(hand),
      pot: pickVisPot(hand),
      winners: winners,
      showdown: Boolean(settle.showdown || hand.outcome === "showdown"),
    };
  }

  function ruleHistory(rr, posMap) {
    if (!rr || typeof rr !== "object") return null;
    var blinds = rr.blinds || {};
    var byLabel = {};
    var byPos = {};
    (rr.players || []).forEach(function (row) {
      var cells = rowCells(row);
      if (cells.length < 3) return;
      byLabel[String(cells[0])] = cells;
      byPos[normPos(cells[1])] = cells;
    });
    var players = [];
    Object.keys(posMap || {}).forEach(function (pos) {
      var seat = posMap[pos];
      var cells = byPos[pos];
      var hole = [];
      if (cells) {
        var shown = cells.length > 6 ? cells[6] : null;
        var raw = Array.isArray(shown) && shown.length ? shown : (cells.length > 3 ? cells[3] : null);
        hole = visCardList(raw);
      }
      var init = cells && cells.length > 4 ? parseNum(cells[4]) : undefined;
      var fin = cells && cells.length > 5 ? parseNum(cells[5]) : undefined;
      var net = cells && cells.length > 7 ? parseNum(cells[7]) : undefined;
      players.push({
        seat: seat,
        pos: pos,
        name: cells && cells.length > 2 ? cells[2] : "",
        init: init,
        final: fin,
        net: net,
        cards: hole,
        hero: !!(cells && /hero/i.test(String(cells[2] || ""))),
      });
    });
    players.sort(function (a, b) { return a.seat - b.seat; });
    var sbSeat, bbSeat, straddleSeat;
    var straddle = parseNum(blinds.straddle);
    var actions = [];
    (rr.actions || []).forEach(function (row) {
      var cells = rowCells(row);
      if (cells.length < 3) return;
      var src = byLabel[String(cells[0])];
      var pos = src ? normPos(src[1]) : "";
      var seat = resolveSeat(pos, posMap);
      var up = normAction(cells[2]);
      var amt = cells.length > 3 ? parseNum(cells[3]) : undefined;
      var raw = (!Array.isArray(row) && row && typeof row === "object") ? row : {};
      if (isPost(cells[2])) {
        if (/straddle/i.test(String(cells[2] || ""))) {
          if (amt != null && straddle == null) straddle = amt;
          if (seat != null) straddleSeat = seat;
        } else if (pos === "SB") sbSeat = seat;
        else if (pos === "BB") bbSeat = seat;
        if (seat == null) return;
        actions.push(withActionFacts({
          street: "preflop",
          seat: seat,
          pos: pos,
          action: up,
          amount: amt,
          post: true,
        }, raw));
        return;
      }
      var st = normStreet(cells[1]);
      if (!st) return;
      actions.push(withActionFacts({
        street: st,
        seat: seat,
        pos: pos,
        action: up,
        amount: amt,
        post: false,
      }, raw));
    });
    if (sbSeat == null) sbSeat = posMap.SB;
    if (bbSeat == null) bbSeat = posMap.BB;
    var result = rr.result || {};
    var boardAll = visCardList([]);
    if (Array.isArray(rr.board)) {
      rr.board.forEach(function (x) {
        if (typeof x === "string" && x) boardAll.push(x);
        else if (Array.isArray(x)) x.forEach(function (c) { if (c) boardAll.push(c); });
      });
    }
    var winRaw = result.winners || [];
    if (Array.isArray(winRaw)) {
      winRaw = winRaw.map(function (id) {
        var cells = byLabel[String(id)];
        return cells ? (normPos(cells[1]) || id) : id;
      });
    }
    return {
      sb: blinds.sb,
      bb: blinds.bb,
      ante: blinds.ante,
      straddle: straddle,
      sb_seat: sbSeat,
      bb_seat: bbSeat,
      straddle_seat: straddleSeat,
      players: players,
      actions: actions,
      board: {
        flop: boardAll.slice(0, 3),
        turn: boardAll.slice(3, 4),
        river: boardAll.slice(4, 5),
      },
      pot: result.total_pot,
      winners: winnerSeats(winRaw, posMap, players),
      showdown: Boolean(result.showdown),
    };
  }

  function playerBySeat(hist, seat) {
    var list = (hist && hist.players) || [];
    for (var i = 0; i < list.length; i++) {
      if (list[i].seat === seat) return list[i];
    }
    return null;
  }

  function enrichGoldHist(hist) {
    if (!hist) return null;
    var out = {};
    Object.keys(hist).forEach(function (k) { out[k] = hist[k]; });
    out.actions = ((hist.actions) || []).map(function (a) {
      if (!a || typeof a !== "object") return a;
      return withActionFacts({
        street: a.street,
        seat: a.seat,
        pos: a.pos,
        who: a.who,
        action: a.action,
        amount: a.amount,
        post: a.post,
      }, a);
    });
    return out;
  }

  function packHistories(goldHist, goldTree, body) {
    var posMap = posMapFromUi(goldTree || {});
    return {
      gold: enrichGoldHist(goldHist),
      vis: visHistory(body, posMap),
      rule: ruleHistory(body && body.ruleResult, posMap),
    };
  }

  function amtEq(a, b) {
    var na = parseNum(a);
    var nb = parseNum(b);
    if (na != null && nb != null) return Math.abs(na - nb) < 1e-9;
    var sa = a == null || a === "" ? "" : String(a).trim();
    var sb = b == null || b === "" ? "" : String(b).trim();
    return sa === sb;
  }

  function fmtAmt(v) {
    if (v == null || v === "") return "—";
    var n = parseNum(v);
    if (n == null) return String(v);
    return Math.abs(n - Math.round(n)) < 1e-9 ? String(Math.round(n)) : String(n);
  }

  function actEq(a, b) {
    if (!a && !b) return true;
    if (!a || !b) return false;
    return normPos(a.who || a.pos) === normPos(b.who || b.pos) &&
      actionLabel(a.action) === actionLabel(b.action) &&
      amtEq(a.amount, b.amount);
  }

  function showAmt(act) {
    var u = compactAct(act);
    if (["BET", "RAISE", "CALL", "ALLIN"].indexOf(u) >= 0) return true;
    var raw = String(act || "").toUpperCase();
    return raw.indexOf("POST") >= 0 || raw.indexOf("STRADDLE") >= 0 || raw.indexOf("ANTE") >= 0;
  }

  function actVerb(act) {
    return actionLabel(act) || act || "";
  }

  function actCn(act) {
    var u = actionLabel(act) || String(act || "").toUpperCase().replace(/[- ]/g, "_");
    if (u === "RAISE" || u.indexOf("RAISE") >= 0) return "加注";
    if (u === "BET" || (u.indexOf("BET") >= 0 && u.indexOf("BETTER") < 0)) return "下注";
    if (u === "CALL") return "跟注";
    if (u === "CHECK") return "过牌";
    if (u === "FOLD") return "弃牌";
    if (u === "ALL-IN" || u === "ALLIN" || u === "ALL_IN") return "全下";
    if (u === "盲注") return "盲注";
    if (u === "前注") return "前注";
    if (u === "STRADDLE" || u === "straddle") return "Straddle";
    return u || "—";
  }

  function pillKind(cn) {
    if (cn === "加注" || cn === "下注") return "raise";
    if (cn === "跟注") return "call";
    if (cn === "过牌") return "check";
    if (cn === "弃牌") return "fold";
    if (cn === "全下") return "allin";
    if (cn === "盲注" || cn === "前注" || cn === "Straddle") return "post";
    return "other";
  }

  function presentActs(hist) {
    return ((hist && hist.actions) || []).map(function (a) {
      return {
        street: a.street,
        seat: a.seat,
        pos: a.pos,
        who: a.who,
        action: a.action,
        amount: a.amount,
        post: a.post,
        pot: a.pot,
        chips: a.chips
      };
    });
  }

  function actsOnDec(list, street, posts) {
    return (list || []).filter(function (a) {
      if (a.street !== street) return false;
      return posts ? !!a.post : !a.post;
    });
  }

  function lastStreetPot(acts) {
    if (!acts || !acts.length) return null;
    for (var i = acts.length - 1; i >= 0; i--) {
      if (acts[i] && acts[i].pot != null && acts[i].pot !== "") return acts[i].pot;
    }
    return null;
  }

  function fmtCount(v) {
    if (v == null || v === "") return "";
    var n = parseNum(v);
    if (n == null) return String(v);
    var s = Math.abs(n - Math.round(n)) < 1e-9 ? String(Math.round(n)) : String(n);
    return s.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  }

  function anyActFact(lists, key) {
    for (var i = 0; i < lists.length; i++) {
      var list = lists[i] || [];
      for (var j = 0; j < list.length; j++) {
        var a = list[j];
        if (a && a[key] != null && a[key] !== "") return true;
      }
    }
    return false;
  }

  function actColsOf(ag, av, ar) {
    return {
      pot: anyActFact([ag, av, ar], "pot"),
      chips: anyActFact([ag, av, ar], "chips")
    };
  }

  function actHeadHtml(cols) {
    return "<div class='act-cell act-head'>" +
      "<div class='act-who'>玩家</div>" +
      "<span class='act-pill-h'>动作</span>" +
      "<span class='act-amt'>数额</span>" +
      (cols && cols.pot ? "<span class='act-pot'>底池</span>" : "") +
      (cols && cols.chips ? "<span class='act-stack'>剩余</span>" : "") +
      "</div>";
  }

  function actHtml(a, against, hist, cols) {
    if (!a) return "<div class='act-miss'>—</div>";
    var whoOk = true, actOk = true, amtOk = true, potOk = true, chipOk = true;
    if (against) {
      whoOk = normPos(a.who || a.pos) === normPos(against.who || against.pos);
      if (a.seat != null && against.seat != null) whoOk = whoOk && a.seat === against.seat;
      actOk = actionLabel(a.action) === actionLabel(against.action);
      amtOk = amtEq(a.amount, against.amount);
      potOk = (a.pot == null || a.pot === "") && (against.pot == null || against.pot === "")
        ? true : amtEq(a.pot, against.pot);
      chipOk = (a.chips == null || a.chips === "") && (against.chips == null || against.chips === "")
        ? true : amtEq(a.chips, against.chips);
    }
    var p = hist && a.seat != null ? playerBySeat(hist, a.seat) : null;
    var pos = a.pos || a.who || (p && p.pos) || "";
    var name = "";
    if (p && p.name && !/^hero$/i.test(p.name)) name = p.name;
    else if (p && p.hero) name = "Hero";
    else name = pos;
    if (name && pos && name === pos) pos = "";
    var cn = actCn(a.action);
    var bad = whoOk ? "" : " is-bad";
    var amtTxt = a.amount == null || a.amount === "" ? "" : fmtAmt(a.amount);
    if (amtTxt === "—") amtTxt = "";
    cols = cols || {};
    return "<div class='act-cell'>" +
      "<div class='act-who'>" +
        "<span class='act-name" + bad + "'>" + hhEsc(name) + "</span>" +
        (pos ? "<span class='act-pos" + bad + "'>" + hhEsc(pos) + "</span>" : "") +
      "</div>" +
      "<span class='act-pill " + pillKind(cn) + (actOk ? "" : " is-bad") + "'>" + hhEsc(cn) + "</span>" +
      "<span class='act-amt" + (amtOk ? "" : " is-bad") + "'>" + hhEsc(amtTxt) + "</span>" +
      (cols.pot ? "<span class='act-pot" + (potOk ? "" : " is-bad") + "'>" + hhEsc(fmtCount(a.pot)) + "</span>" : "") +
      (cols.chips ? "<span class='act-stack" + (chipOk ? "" : " is-bad") + "'>" + hhEsc(fmtCount(a.chips)) + "</span>" : "") +
      "</div>";
  }

  function actsOn(hist, street, posts) {
    return ((hist && hist.actions) || []).filter(function (a) {
      if (a.street !== street) return false;
      return posts ? !!a.post : !a.post;
    });
  }

  function hhEsc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function whoHtml(p, seat) {
    if (p) seat = p.seat;
    if (seat == null) return "—";
    var pos = (p && p.pos) || "";
    var name = (p && p.name) || "";
    var hero = p && p.hero;
    var html = "P" + seat;
    if (pos) html += " <span class='pos'>" + hhEsc(pos) + "</span>";
    if (name && !/^hero$/i.test(name)) html += " <span class='hh-name'>" + hhEsc(name) + "</span>";
    if (hero) html += " <span class='hero-mark'>Hero</span>";
    return html;
  }

  function anyPlayer(pack, seat) {
    return playerBySeat(pack.gold, seat) || playerBySeat(pack.vis, seat) || playerBySeat(pack.rule, seat);
  }

  function parseCard(code) {
    var compact = String(code == null ? "" : code).trim().replace(/\s/g, "");
    if (!compact) return { cls: "unk", text: "—" };
    if (/^x+$/i.test(compact) || /^x.x$/i.test(compact)) return { cls: "unk", text: "?" };
    var last = compact.slice(-1);
    var suitCh = { s: "s", S: "s", "♠": "s", h: "h", H: "h", "♥": "h",
      d: "d", D: "d", "♦": "d", c: "c", C: "c", "♣": "c" }[last];
    var rank = compact.slice(0, -1).toUpperCase();
    if (rank === "10") rank = "T";
    var letter = { s: "S", h: "H", d: "D", c: "C" }[suitCh];
    if (!letter) return { cls: "unk", text: compact };
    return { cls: suitCh, text: rank + letter };
  }

  function cardsHtml(list) {
    if (!list || !list.length || list.every(function (v) { return v == null || v === ""; })) {
      return "—";
    }
    return list.map(function (code) {
      var p = parseCard(code);
      return "<span class='pcard " + p.cls + "'>" + p.text + "</span>";
    }).join("");
  }

  function cardsKey(list) {
    return (list || []).map(function (c) {
      var s = String(c || "").trim().toUpperCase().replace(/\s/g, "");
      if (s.indexOf("10") === 0) s = "T" + s.slice(2);
      return s;
    }).filter(Boolean).sort().join(" ");
  }

  function cardsEq(a, b) {
    return cardsKey(a) === cardsKey(b);
  }

  function winnersKey(hist) {
    return ((hist && hist.winners) || []).slice().sort(function (a, b) { return a - b; }).join(",");
  }

  function fmtWinners(hist) {
    var seats = (hist && hist.winners) || [];
    if (!seats.length) return "—";
    return seats.map(function (seat) { return whoHtml(playerBySeat(hist, seat), seat); }).join("、");
  }

  function fmtShowdown(v) {
    if (v == null) return "—";
    return v ? "是" : "否";
  }

  function boardOf(hist, st) {
    return ((hist && hist.board) || {})[st] || [];
  }

  function tripleEq(g, v, r) {
    return amtEq(g, v) && amtEq(g, r);
  }

  function causeTd(eq) {
    if (eq) return "<td></td>";
    return "<td><span class='pill vis'>不一致</span></td>";
  }

  function secRow(title, extra) {
    return "<tr class='sec'><td colspan='5'><span class='sec-in'><span>" + title + "</span>" +
      (extra ? "<span class='pot'>" + extra + "</span>" : "") + "</span></td></tr>";
  }

  function section(title, rowsHtml) {
    if (!rowsHtml) return "";
    return secRow(title) + rowsHtml;
  }

  function tripleRow(who, g, v, r, onlyDiff) {
    var eq = tripleEq(g, v, r);
    if (onlyDiff && eq) return "";
    return "<tr class='" + (eq ? "is-ok" : "is-diff") + "'>" +
      "<td class='who'>" + who + "</td>" +
      "<td class='val'>" + fmtAmt(g) + "</td>" +
      "<td class='val'>" + fmtAmt(v) + "</td>" +
      "<td class='val'>" + fmtAmt(r) + "</td>" +
      causeTd(eq) + "</tr>";
  }

  function tripleCells(who, gHtml, vHtml, rHtml, eq) {
    return "<tr class='" + (eq ? "is-ok" : "is-diff") + "'>" +
      "<td class='who'>" + who + "</td>" +
      "<td class='val'>" + gHtml + "</td>" +
      "<td class='val'>" + vHtml + "</td>" +
      "<td class='val'>" + rHtml + "</td>" +
      causeTd(eq) + "</tr>";
  }

  function seatListOf(pack) {
    var seats = {};
    var g = pack.gold || {};
    var v = pack.vis || {};
    var r = pack.rule || {};
    [(g.players || []), (v.players || []), (r.players || [])].forEach(function (list) {
      list.forEach(function (p) { if (p && p.seat != null) seats[p.seat] = 1; });
    });
    return Object.keys(seats).map(Number).sort(function (a, b) { return a - b; });
  }

  function playerTable(pack, field) {
    var rows = "";
    seatListOf(pack).forEach(function (seat) {
      var pg = playerBySeat(pack.gold, seat);
      var pv = playerBySeat(pack.vis, seat);
      var pr = playerBySeat(pack.rule, seat);
      rows += tripleRow(
        whoHtml(anyPlayer(pack, seat), seat),
        pg ? pg[field] : undefined,
        pv ? pv[field] : undefined,
        pr ? pr[field] : undefined,
        false
      );
    });
    return rows;
  }

  function actBlock(title, ag, av, ar, gHist, vHist, rHist, onlyDiff) {
    var n = Math.max(ag.length, av.length, ar.length);
    if (!n) return "";
    var cols = actColsOf(ag, av, ar);
    var rows = "";
    for (var i = 0; i < n; i++) {
      var eq = actEq(ag[i], av[i]) && actEq(ag[i], ar[i]);
      if (onlyDiff && eq) continue;
      rows += "<tr class='" + (eq ? "is-ok" : "is-diff") + "'>" +
        "<td class='who'>" + (i + 1) + "</td>" +
        "<td class='val'>" + actHtml(ag[i], null, gHist, cols) + "</td>" +
        "<td class='val'>" + actHtml(av[i], ag[i], vHist, cols) + "</td>" +
        "<td class='val'>" + actHtml(ar[i], ag[i], rHist, cols) + "</td>" +
        causeTd(eq) + "</tr>";
    }
    if (!rows) return "";
    var pot = lastStreetPot(ag);
    var head = "<tr class='act-cols'>" +
      "<td class='who'>步</td>" +
      "<td class='val'>" + actHeadHtml(cols) + "</td>" +
      "<td class='val'>" + actHeadHtml(cols) + "</td>" +
      "<td class='val'>" + actHeadHtml(cols) + "</td>" +
      "<td></td></tr>";
    return secRow(title + " <span class='n'>(" + n + ")</span>",
      pot != null ? "底池 " + fmtCount(pot) : "") + head + rows;
  }

  function historyHtml(pack, onlyDiff) {
    if (!pack || (!pack.gold && !pack.vis && !pack.rule)) return "";
    var g = pack.gold || {};
    var v = pack.vis || {};
    var r = pack.rule || {};
    var gActs = presentActs(g);
    var vActs = presentActs(v);
    var rActs = presentActs(r);
    var body = "";
    body += section("强制投入",
      tripleRow("前注", g.ante, v.ante, r.ante, false) +
        tripleRow(g.sb_seat != null ? "小盲 · " + whoHtml(anyPlayer(pack, g.sb_seat), g.sb_seat) : "小盲", g.sb, v.sb, r.sb, false) +
        tripleRow(g.bb_seat != null ? "大盲 · " + whoHtml(anyPlayer(pack, g.bb_seat), g.bb_seat) : "大盲", g.bb, v.bb, r.bb, false) +
        tripleRow(
          (g.straddle_seat != null || v.straddle_seat != null || r.straddle_seat != null)
            ? "Straddle · " + whoHtml(
              anyPlayer(pack, g.straddle_seat != null ? g.straddle_seat : (v.straddle_seat != null ? v.straddle_seat : r.straddle_seat)),
              g.straddle_seat != null ? g.straddle_seat : (v.straddle_seat != null ? v.straddle_seat : r.straddle_seat)
            )
            : "Straddle",
          g.straddle, v.straddle, r.straddle, false
        )
    );
    body += section("起始筹码", playerTable(pack, "init"));

    var cardRows = "";
    seatListOf(pack).forEach(function (seat) {
      var pg = playerBySeat(g, seat);
      var pv = playerBySeat(v, seat);
      var pr = playerBySeat(r, seat);
      var gc = pg ? pg.cards : [];
      var vc = pv ? pv.cards : [];
      var rc = pr ? pr.cards : [];
      var eq = cardsEq(gc, vc) && cardsEq(gc, rc);
      if (onlyDiff && eq) return;
      cardRows += tripleCells(whoHtml(anyPlayer(pack, seat), seat), cardsHtml(gc), cardsHtml(vc), cardsHtml(rc), eq);
    });
    body += section("手牌", cardRows);

    var boardRows = "";
    [["flop", "翻牌"], ["turn", "转牌"], ["river", "河牌"]].forEach(function (pair) {
      var gc = boardOf(g, pair[0]);
      var vc = boardOf(v, pair[0]);
      var rc = boardOf(r, pair[0]);
      var eq = cardsEq(gc, vc) && cardsEq(gc, rc);
      if (onlyDiff && eq) return;
      boardRows += tripleCells(pair[1], cardsHtml(gc), cardsHtml(vc), cardsHtml(rc), eq);
    });
    body += section("公牌", boardRows);

    STREET_ORDER.forEach(function (st) {
      if (st === "preflop") {
        body += actBlock("翻前盲注 / 前注", actsOnDec(gActs, st, true), actsOnDec(vActs, st, true), actsOnDec(rActs, st, true), g, v, r, onlyDiff);
        body += actBlock("翻前", actsOnDec(gActs, st, false), actsOnDec(vActs, st, false), actsOnDec(rActs, st, false), g, v, r, onlyDiff);
      } else {
        body += actBlock(STREET_LAB[st], actsOnDec(gActs, st, false), actsOnDec(vActs, st, false), actsOnDec(rActs, st, false), g, v, r, onlyDiff);
      }
    });

    var winEq = winnersKey(g) === winnersKey(v) && winnersKey(g) === winnersKey(r);
    var sdEq = Boolean(g.showdown) === Boolean(v.showdown) && Boolean(g.showdown) === Boolean(r.showdown);
    body += section("结算",
      tripleRow("总底池", g.pot, v.pot, r.pot, onlyDiff) +
        (onlyDiff && sdEq ? "" : tripleCells("摊牌", fmtShowdown(g.showdown), fmtShowdown(v.showdown), fmtShowdown(r.showdown), sdEq)) +
        (onlyDiff && winEq ? "" : tripleCells("赢家", fmtWinners(g), fmtWinners(v), fmtWinners(r), winEq))
    );
    body += section("终局筹码", playerTable(pack, "final"));
    body += section("净赢", playerTable(pack, "net"));
    return body;
  }

  global.E2EMatch = {
    lookup: lookup,
    parseSessionIds: parseSessionIds,
    matchBatch: matchBatch,
    fetchHandResult: fetchHandResult,
    listSessionHands: listSessionHands,
    stageTrees: stageTrees,
    compareStages: compareStages,
    flattenValues: flattenValues,
    flattenHistory: flattenHistory,
    seqGroups: seqGroups,
    compareSeq: compareSeq,
    flattenHand: flattenHand,
    valueAt: valueAt,
    valuesEqual: valuesEqual,
    causeOf: causeOf,
    displayVal: displayVal,
    isPost: isPost,
    pickVisPot: pickVisPot,
    packHistories: packHistories,
    historyHtml: historyHtml,
    visHistory: visHistory,
    ruleHistory: ruleHistory,
  };
})(window);
