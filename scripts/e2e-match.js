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
  var DEFAULT_TRACE = "http://192.168.110.73:8071";

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

  function hasVal(v) {
    if (v == null || v === "") return false;
    if (isLen(v)) return Number(v[1]) > 0;
    if (Array.isArray(v)) {
      for (var i = 0; i < v.length; i++) if (hasVal(v[i])) return true;
      return false;
    }
    return true;
  }

  function wrapDiff(html, side, goldVal, thisVal, eqFn) {
    if (!side || side === "gold") return html;
    if (!hasVal(goldVal) && !hasVal(thisVal)) return html;
    var eq = eqFn || valuesEqual;
    if (eq(goldVal, thisVal)) return html;
    return "<span class='diff-mark " + side + "'>" + html + "</span>";
  }

  function skipComparePath(path) {
    var p = String(path || "");
    if (p.indexOf("history.post.") !== 0) return false;
    return !/\.pot$/.test(p);
  }

  function playerSeatKey(path) {
    var m = String(path || "").match(/^players\.(P\d+)\./);
    return m ? m[1] : "";
  }

  function playerOccupied(flat, key) {
    if (!key || !flat) return false;
    var prefix = "players." + key + ".";
    var names = Object.keys(flat);
    for (var i = 0; i < names.length; i++) {
      if (names[i].indexOf(prefix) === 0) return true;
    }
    return false;
  }

  function isPlayerFollowOn(path) {
    var key = playerSeatKey(path);
    if (!key) return false;
    if (/\.position\.value$/.test(path)) return false;
    return /\.(name|seat|init_chips|chips|dealer|status)\.value$/.test(path) ||
      /\.cards(\.|$)/.test(path);
  }

  function compareFlat(left, right) {
    var out = {};
    right = right || {};
    var paths = Object.keys(left);
    for (var i = 0; i < paths.length; i++) {
      var path = paths[i];
      if (skipComparePath(path)) continue;
      var lv = left[path];
      if (!hasVal(lv)) continue;
      var key = playerSeatKey(path);
      if (key && /\.position\.value$/.test(path)) {
        if (!(path in right) || !hasVal(right[path])) {
          out[path] = "missing";
          continue;
        }
        out[path] = posEq(lv, right[path]) ? "match" : "mismatch";
        continue;
      }
      if (isPlayerFollowOn(path) && !playerOccupied(right, key)) continue;
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
    fillActionPots(hist);
    var posts = { preflop: [], flop: [], turn: [], river: [] };
    var vols = { preflop: [], flop: [], turn: [], river: [] };
    ((hist.actions) || []).forEach(function (a) {
      if (!a) return;
      var st = a.street || "preflop";
      if (!vols[st]) return;
      (a.post ? posts : vols)[st].push(a);
    });
    var out = {};
    var prevPot = null;
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
          var pv = a.pot;
          if (pv == null || pv === "") return;
          if (prevPot == null || !valuesEqual(pv, prevPot)) {
            out[p + ".pot"] = pv;
            prevPot = pv;
          }
        });
      });
    });
    return out;
  }

  function seqGroups(hist) {
    var vols = { preflop: [], flop: [], turn: [], river: [] };
    (((hist && hist.actions) || [])).forEach(function (a) {
      if (!a || a.post) return;
      var st = a.street || "preflop";
      if (!vols[st]) return;
      vols[st].push({
        who: normPos(a.pos || a.who || ""),
        action: actionLabel(a.action),
        amount: a.amount
      });
    });
    var groups = [];
    STREET_FLAT.forEach(function (st) {
      groups.push({
        key: "vol." + st,
        lab: SEQ_STREET_LAB[st] || st,
        steps: vols[st]
      });
    });
    return groups;
  }

  function stepEqual(a, b) {
    return posEq(a.who, b.who) && a.action === b.action && valuesEqual(a.amount, b.amount);
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
      if (cmp.miss) nMiss += 1;
      per.push(cmp);
      if (miss) continue;
      exactT += 1;
      if (cmp.exact) exactN += 1;
      stepN += cmp.step_n;
      stepT += cmp.step_t;
      if (cmp.len_diff) nLen += 1;
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

  function actionPutsChips(act) {
    var u = normAction(act);
    if (u === "BET" || u === "RAISE" || u === "CALL" || u === "ALL-IN") return true;
    var lab = actionLabel(act);
    return lab === "盲注" || lab === "前注" || lab === "straddle";
  }

  function fillActionPots(hist) {
    if (!hist || !Array.isArray(hist.actions)) return hist;
    var pot = 0;
    var ante = parseNum(hist.ante) || 0;
    var antePosted = hist.actions.some(function (a) {
      return a && actionLabel(a.action) === "前注";
    });
    if (ante > 0 && !antePosted) {
      var n = ((hist.players) || []).filter(function (p) {
        return p && p.seat != null;
      }).length;
      if (n) pot += ante * n;
    }
    hist.actions.forEach(function (a) {
      if (!a) return;
      if (actionPutsChips(a.action)) {
        var amt = parseNum(a.amount);
        if (amt != null && amt > 0) pot += amt;
      }
      if (a.pot != null && a.pot !== "") return;
      a.pot = roundChips(pot);
    });
    return fillActionStacks(hist);
  }

  function fillActionStacks(hist) {
    if (!hist || !Array.isArray(hist.actions)) return hist;
    var remaining = {};
    ((hist.players) || []).forEach(function (p) {
      if (!p || p.seat == null) return;
      var init = parseNum(p.init);
      if (init == null) return;
      remaining[p.seat] = init;
    });
    var antePosted = hist.actions.some(function (a) {
      return a && actionLabel(a.action) === "前注";
    });
    var ante = parseNum(hist.ante) || 0;
    if (ante > 0 && !antePosted) {
      Object.keys(remaining).forEach(function (s) {
        var seat = Number(s);
        remaining[seat] -= Math.min(ante, remaining[seat]);
      });
    }
    hist.actions.forEach(function (a) {
      if (!a) return;
      var seat = a.seat;
      if (seat != null && remaining[seat] != null && actionPutsChips(a.action)) {
        var amt = parseNum(a.amount);
        if (amt != null && amt > 0) remaining[seat] -= Math.min(amt, remaining[seat]);
      }
      if (a.chips != null && a.chips !== "") {
        var cn = parseNum(a.chips);
        if (cn != null && seat != null) remaining[seat] = cn;
        return;
      }
      if (seat != null && remaining[seat] != null) a.chips = roundChips(remaining[seat]);
    });
    return hist;
  }

  function roundChips(v) {
    var n = Number(v);
    if (!isFinite(n)) return v;
    return Math.abs(n - Math.round(n)) < 1e-6 ? Math.round(n) : n;
  }

  function inferFinals(hist) {
    if (!hist || !Array.isArray(hist.players) || !hist.players.length) return hist;
    hist.players.forEach(function (p) {
      if (!p || hasVal(p.final) || !hasVal(p.init) || !hasVal(p.net)) return;
      var init = parseNum(p.init);
      var net = parseNum(p.net);
      if (init == null || net == null) return;
      p.final = roundChips(init + net);
    });
    var missing = hist.players.filter(function (p) {
      return p && p.seat != null && hasVal(p.init) && !hasVal(p.final);
    });
    if (!missing.length) return hist;
    var remaining = {};
    var invested = {};
    var streetPut = {};
    hist.players.forEach(function (p) {
      if (!p || p.seat == null) return;
      var init = parseNum(p.init);
      if (init == null) return;
      remaining[p.seat] = init;
      invested[p.seat] = 0;
      streetPut[p.seat] = 0;
    });
    var antePosted = ((hist.actions) || []).some(function (a) {
      return a && actionLabel(a.action) === "前注";
    });
    var ante = parseNum(hist.ante) || 0;
    if (ante > 0 && !antePosted) {
      Object.keys(remaining).forEach(function (s) {
        var seat = Number(s);
        var put = Math.min(ante, remaining[seat]);
        remaining[seat] -= put;
        invested[seat] += put;
      });
    }
    var lastStreet = "";
    var folded = {};
    ((hist.actions) || []).forEach(function (a) {
      if (!a || a.seat == null) return;
      var st = a.street || "preflop";
      if (st !== lastStreet) {
        if (lastStreet) Object.keys(streetPut).forEach(function (s) { streetPut[s] = 0; });
        lastStreet = st;
      }
      if (normAction(a.action) === "FOLD") folded[a.seat] = 1;
      if (!actionPutsChips(a.action)) return;
      if (remaining[a.seat] == null) return;
      var amt = parseNum(a.amount);
      if (amt == null || amt <= 0) return;
      var put = Math.min(amt, remaining[a.seat]);
      remaining[a.seat] -= put;
      invested[a.seat] += put;
      streetPut[a.seat] = (streetPut[a.seat] || 0) + put;
    });
    var streetSeats = Object.keys(streetPut).map(Number);
    var ranked = streetSeats.map(function (s) { return streetPut[s] || 0; }).sort(function (a, b) { return b - a; });
    if (ranked[0] > 0) {
      var uncalled = ranked[0] - (ranked[1] || 0);
      if (uncalled > 1e-9) {
        var who = null;
        streetSeats.forEach(function (s) {
          if ((streetPut[s] || 0) + 1e-9 >= ranked[0]) who = s;
        });
        if (who != null) {
          remaining[who] += uncalled;
          invested[who] -= uncalled;
        }
      }
    }
    var pot = 0;
    Object.keys(invested).forEach(function (s) { pot += invested[s]; });
    var winners = ((hist.winners) || []).map(Number).filter(function (s) { return remaining[s] != null; });
    if (!winners.length) {
      winners = Object.keys(remaining).map(Number).filter(function (s) { return !folded[s]; });
      if (winners.length !== 1) winners = [];
    }
    if (winners.length && pot > 0) {
      var share = pot / winners.length;
      winners.forEach(function (s) { remaining[s] += share; });
    }
    hist.players.forEach(function (p) {
      if (!p || hasVal(p.final) || remaining[p.seat] == null) return;
      p.final = roundChips(remaining[p.seat]);
      if (!hasVal(p.net) && hasVal(p.init)) {
        var init = parseNum(p.init);
        if (init != null) p.net = roundChips(p.final - init);
      }
    });
    return hist;
  }

  function fillPlayerChip(ui, hist, field, histKey) {
    if (!ui || typeof ui !== "object" || !ui.players) return ui;
    var bySeat = {};
    ((hist && hist.players) || []).forEach(function (p) {
      if (p && p.seat != null) bySeat[p.seat] = p;
    });
    Object.keys(ui.players).forEach(function (key) {
      var node = ui.players[key];
      if (!node || typeof node !== "object") return;
      var cur = node[field] && node[field].value;
      if (cur != null && cur !== "") return;
      var seat = parseInt(String(key).slice(1), 10);
      var p = bySeat[seat];
      var v = p ? p[histKey] : undefined;
      if (v == null || v === "") return;
      node[field] = { value: v };
    });
    return ui;
  }

  function fillInitChips(ui, hist) {
    return fillPlayerChip(ui, hist, "init_chips", "init");
  }

  function fillFinalChips(ui, hist) {
    inferFinals(hist);
    return fillPlayerChip(ui, hist, "chips", "final");
  }

  function flattenHand(ui, hist) {
    fillInitChips(ui, hist);
    fillFinalChips(ui, hist);
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
    if (p === "players") return true;
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

  function posTwin(pos) {
    var p = normPos(pos);
    if (p === "UTG+1") return "HJ";
    if (p === "HJ") return "UTG+1";
    if (p === "UTG+2") return "CO";
    if (p === "CO") return "UTG+2";
    return "";
  }

  function lookupByPos(byPos, pos) {
    var p = normPos(pos);
    if (byPos[p]) return byPos[p];
    var twin = posTwin(p);
    if (twin && byPos[twin]) return byPos[twin];
    return null;
  }

  function nativeSeatOf(obj, fallback) {
    if (obj != null && typeof obj === "object" && !Array.isArray(obj)) {
      var keys = ["seat", "seat_no", "seatNo", "seat_id", "player_seat", "playerSeat"];
      for (var i = 0; i < keys.length; i++) {
        if (!Object.prototype.hasOwnProperty.call(obj, keys[i])) continue;
        var n = parseNum(obj[keys[i]]);
        if (n != null) return n;
        var m = /^P?(\d+)$/i.exec(String(obj[keys[i]]).trim());
        if (m) return Number(m[1]);
      }
    } else if (obj != null && obj !== "") {
      var n2 = parseNum(obj);
      if (n2 != null) return n2;
      var m2 = /^P?(\d+)$/i.exec(String(obj).trim());
      if (m2) return Number(m2[1]);
    }
    return fallback;
  }

  function resolveSeat(pos, posMap) {
    var p = normPos(pos);
    if (!p || !posMap) return null;
    if (p in posMap) return posMap[p];
    var twin = posTwin(p);
    if (twin && twin in posMap) return posMap[twin];
    return null;
  }

  function nickKey(s) {
    return String(s || "").trim().toLowerCase().replace(/\s+/g, "");
  }

  function goldSlotsFromUi(ui) {
    var out = [];
    var players = (ui && ui.players) || {};
    Object.keys(players).forEach(function (key) {
      if (key.charAt(0) !== "P") return;
      var seat = parseInt(key.slice(1), 10);
      if (!isFinite(seat)) return;
      var pl = players[key] || {};
      out.push({
        seat: seat,
        name: ((pl.name || {}).value) || "",
        pos: normPos(((pl.position || {}).value)),
      });
    });
    out.sort(function (a, b) { return a.seat - b.seat; });
    return out;
  }

  function nameToSeatFromUi(ui) {
    var out = {};
    goldSlotsFromUi(ui).forEach(function (s) {
      var k = nickKey(s.name);
      if (k && !(k in out)) out[k] = s.seat;
    });
    return out;
  }

  function resolveSeatByNick(name, nameToSeat, pos, posMap) {
    var k = nickKey(name);
    if (k && nameToSeat && Object.prototype.hasOwnProperty.call(nameToSeat, k)) {
      return nameToSeat[k];
    }
    return resolveSeat(pos, posMap);
  }

  function visActionNick(a, byPos) {
    var n = (a && (a.player || a.nickname || a.player_name || a.name)) || "";
    if (n) return n;
    var pos = normPos(a && a.player_position);
    if (!pos || !byPos) return "";
    var hit = byPos[pos] || (posTwin(pos) ? byPos[posTwin(pos)] : null);
    if (!hit) return "";
    var p = hit.p || hit;
    return (p && (p.nickname || p.name)) || "";
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

  function visToUi(hand, blinds, posMap, goldUi) {
    if (!hand || typeof hand !== "object" || !posMap || !Object.keys(posMap).length) return null;
    var byPos = {};
    var byNick = {};
    (hand.players || []).forEach(function (p, idx) {
      if (!p || typeof p !== "object") return;
      if (p.position) byPos[normPos(p.position)] = { p: p, idx: idx };
      var k = nickKey(p.nickname);
      if (k && !(k in byNick)) byNick[k] = { p: p, idx: idx };
    });
    var nameToSeat = nameToSeatFromUi(goldUi);
    var lastAct = {};
    var lastBet = {};
    var folded = {};
    (hand.actions || []).forEach(function (a) {
      if (!a || typeof a !== "object" || isPost(a.action)) return;
      var seat = resolveSeatByNick(visActionNick(a, byPos), nameToSeat, a.player_position, posMap);
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
    function putVisPlayer(seat, p, idx, visPos) {
      if (p == null || seat == null) return;
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
        seat: { value: nativeSeatOf(p, idx) },
        dealer: { value: Boolean(p.is_dealer) },
        status: { value: status },
        position: { value: visPos || normPos(p.position) },
      };
    }
    var slots = goldSlotsFromUi(goldUi);
    var useNick = slots.some(function (s) { return nickKey(s.name); });
    if (useNick) {
      slots.forEach(function (s) {
        var hit = byNick[nickKey(s.name)];
        if (!hit) return;
        putVisPlayer(s.seat, hit.p, hit.idx, normPos(hit.p.position));
      });
    } else {
      Object.keys(posMap).forEach(function (pos) {
        var seat = posMap[pos];
        var hit = lookupByPos(byPos, pos);
        if (!hit) return;
        putVisPlayer(seat, hit.p, hit.idx, pos);
      });
    }
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

  function ruleToUi(rr, posMap, goldUi) {
    if (!rr || typeof rr !== "object" || !posMap || !Object.keys(posMap).length) return null;
    var byLabel = {};
    var byPos = {};
    var byNick = {};
    (rr.players || []).forEach(function (row) {
      var cells = rowCells(row);
      if (cells.length < 3) return;
      byLabel[String(cells[0])] = cells;
      byPos[normPos(cells[1])] = cells;
      var k = nickKey(cells[2]);
      if (k && !(k in byNick)) byNick[k] = cells;
    });
    var nameToSeat = nameToSeatFromUi(goldUi);
    var lastAct = {};
    var lastBet = {};
    var folded = {};
    (rr.actions || []).forEach(function (a) {
      var cells = rowCells(a);
      if (cells.length < 3 || isPost(cells[2])) return;
      var src = byLabel[String(cells[0])];
      var seat = resolveSeatByNick(
        src && src.length > 2 ? src[2] : "",
        nameToSeat,
        src ? src[1] : null,
        posMap
      );
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
    function putRulePlayer(seat, cells, visPos) {
      if (!cells || seat == null) return;
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
        seat: { value: nativeSeatOf(cells[0], undefined) },
        dealer: { value: normPos(cells[1]) === "BTN" },
        status: { value: status },
        position: { value: visPos || normPos(cells[1]) },
      };
    }
    var slots = goldSlotsFromUi(goldUi);
    var useNick = slots.some(function (s) { return nickKey(s.name); });
    if (useNick) {
      slots.forEach(function (s) {
        var cells = byNick[nickKey(s.name)];
        if (!cells) return;
        putRulePlayer(s.seat, cells, normPos(cells[1]));
      });
    } else {
      Object.keys(posMap).forEach(function (pos) {
        var cells = lookupByPos(byPos, pos);
        if (!cells) return;
        putRulePlayer(posMap[pos], cells, pos);
      });
    }
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

  var DIM_KEYS = ["牌", "位置", "动作", "金额", "底池"];

  function dimOfPath(path) {
    var p = String(path || "");
    if (p.indexOf("history.") === 0) {
      if (/\.who$/.test(p)) return "位置";
      if (/\.action$/.test(p)) return "动作";
      if (/\.amount$/.test(p)) return "金额";
      if (/\.pot$/.test(p)) return "底池";
      return "";
    }
    var low = p.toLowerCase();
    if (low.indexOf("card") >= 0) return "牌";
    if (low.indexOf(".position") >= 0) return "位置";
    return "";
  }

  function emptyDimTot() {
    var tot = {};
    DIM_KEYS.forEach(function (d) { tot[d] = { m: 0, t: 0 }; });
    return tot;
  }

  function addVerdictsToDim(tot, verdicts) {
    Object.keys(verdicts || {}).forEach(function (p) {
      var d = dimOfPath(p);
      if (!d || !tot[d]) return;
      tot[d].t += 1;
      if (verdicts[p] === "match") tot[d].m += 1;
    });
    return tot;
  }

  function dimPackFromTot(tot, nIn, nAll5) {
    var rates = {};
    var allM = 0;
    var allT = 0;
    DIM_KEYS.forEach(function (d) {
      var row = tot[d] || { m: 0, t: 0 };
      allM += row.m;
      allT += row.t;
      rates[d] = rate(row.m, row.t);
    });
    return {
      all: rate(allM, allT),
      all5: rate(nAll5, nIn),
      dims: rates,
      n: nIn || 0,
      n_all5: nAll5 || 0
    };
  }

  function summarizeDims(leftTrees, rightTrees, leftHists, rightHists) {
    var tot = emptyDimTot();
    var nIn = 0;
    var nAll5 = 0;
    for (var i = 0; i < leftTrees.length; i++) {
      if (leftTrees[i] == null || rightTrees[i] == null) continue;
      nIn += 1;
      var verdicts = compareFlat(
        flattenHand(leftTrees[i], leftHists ? leftHists[i] : null),
        flattenHand(rightTrees[i], rightHists ? rightHists[i] : null)
      );
      var one = emptyDimTot();
      addVerdictsToDim(one, verdicts);
      addVerdictsToDim(tot, verdicts);
      var all5 = true;
      var any = false;
      DIM_KEYS.forEach(function (d) {
        if (one[d].t <= 0) return;
        any = true;
        if (one[d].m !== one[d].t) all5 = false;
      });
      if (any && all5) nAll5 += 1;
    }
    return dimPackFromTot(tot, nIn, nAll5);
  }

  function dimRatesFromFieldStats(fieldStats, hands, missKey) {
    var tot = emptyDimTot();
    var fields = fieldStats || {};
    var errSeq = {};
    Object.keys(fields).forEach(function (path) {
      var d = dimOfPath(path);
      if (!d || !tot[d]) return;
      var st = fields[path] || {};
      tot[d].m += st.match || 0;
      tot[d].t += st.total || 0;
      (st.errors || []).forEach(function (seq) { errSeq[seq] = 1; });
    });
    var nIn = 0;
    var nAll5 = 0;
    (hands || []).forEach(function (h) {
      if (!h || h[missKey]) return;
      nIn += 1;
      if (!errSeq[h.seq]) nAll5 += 1;
    });
    return dimPackFromTot(tot, nIn, nAll5);
  }

  function summarizePair(leftTrees, rightTrees, seqs, leftHists, rightHists) {
    var byPath = {};
    for (var i = 0; i < leftTrees.length; i++) {
      var left = leftTrees[i];
      var seq = seqs[i] != null ? seqs[i] : i + 1;
      if (left == null) continue;
      var right = i < rightTrees.length ? rightTrees[i] : null;
      if (right == null) continue;
      var flatL = flattenHand(left, leftHists ? leftHists[i] : null);
      var rh = rightHists ? rightHists[i] : null;
      var flatR = flattenHand(right, rh);
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
    if (left == null || right == null) return { rate: null, miss: true };
    var verdicts = compareFlat(flattenHand(left, leftH), flattenHand(right, rightH));
    var matchN = 0;
    var total = 0;
    Object.keys(verdicts).forEach(function (p) {
      total += 1;
      if (verdicts[p] === "match") matchN += 1;
    });
    return { rate: rate(matchN, total), miss: false };
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
      visTrees.push(extracted.hand ? visToUi(extracted.hand, extracted.blinds, posMap, gold) : null);
      visHists.push(extracted.hand ? visHistory(body, posMap, gold) : null);
      var rr = body && typeof body === "object" ? body.ruleResult : null;
      ruleTrees.push(rr ? ruleToUi(rr, posMap, gold) : null);
      ruleHists.push(rr ? ruleHistory(rr, posMap, gold) : null);
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
        videoUrl: (item && (item.videoUrl || item.video_url)) || "",
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
      dim_rates: {
        vis: summarizeDims(goldTrees, visTrees, goldHistList, visHists),
        rule: summarizeDims(goldTrees, ruleTrees, goldHistList, ruleHists)
      },
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

  async function jsonGet(base, path, label) {
    var url = String(base || "").replace(/\/+$/, "") + path;
    var lab = label || "接口";
    var res;
    try {
      res = await fetch(url);
    } catch (e) {
      throw new Error("连不上 " + lab + "：" + url);
    }
    if (!res.ok) throw new Error(lab + " " + res.status + " " + path);
    return unwrap(await res.json());
  }

  async function fusionGet(base, path) {
    return jsonGet(base, path, "fusion");
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
        errorMsg: rec.errorMsg || item.errorMsg || "",
        segmentId: rec.segmentId || item.segmentId || "",
        videoUrl: rec.videoUrl || item.videoUrl || "",
        createTimeMs: rec.createTime || item.createTime || 0,
      });
    });
    return sortSessionHands(hands);
  }

  var sessionRecs = {};

  async function clipUrlForHand(base, sessionId, fusionHandId) {
    var sid = String(sessionId || "");
    var hid = String(fusionHandId || "");
    if (!sid || !hid) return "";
    if (!sessionRecs[sid]) {
      sessionRecs[sid] = listSessionRecords(base, sid).catch(function (err) {
        delete sessionRecs[sid];
        throw err;
      });
    }
    var recs = await sessionRecs[sid];
    for (var i = 0; i < recs.length; i++) {
      var r = recs[i] || {};
      if (String(r.handId || "") !== hid) continue;
      var url = String(r.videoUrl || r.video_url || "").trim();
      if (url) return url;
    }
    return "";
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

  function isFailStatus(st) {
    var u = String(st || "").toUpperCase();
    return u === "FAILED" || u === "ERROR" || u === "REJECTED";
  }

  function isParsedStatus(st) {
    var u = String(st || "").toUpperCase();
    return u === "PARSED" || u === "SUCCESS" || u === "COMPLETED";
  }

  function shortReject(reason) {
    var s = String(reason || "").replace(/\s+/g, " ").trim();
    if (!s) return "下游拒绝";
    if (/is_hero/i.test(s)) return "缺 Hero";
    if (/BOARD_INCOMPLETE/i.test(s)) return "公牌不足";
    if (/SHOWDOWN_CARDS_MISSING/i.test(s)) return "缺摊牌底牌";
    var coded = s.match(/^[A-Z][A-Z0-9_]+:\s*([^|；;]+)/);
    if (coded) return coded[1].trim().slice(0, 16);
    var first = s.split(/[|；;]/)[0].replace(/^[^:]+:\s*/, "").trim();
    return (first || s).slice(0, 16);
  }

  async function fetchRequestTraces(traceBase, sessionIds) {
    var base = String(traceBase || DEFAULT_TRACE).replace(/\/+$/, "");
    var records = [];
    for (var i = 0; i < sessionIds.length; i++) {
      var sid = sessionIds[i];
      var path = "/api/poker-review/request-traces?sessionId=" +
        encodeURIComponent(sid) + "&onlyAbnormal=false";
      var res = await jsonGet(base, path, "trace");
      var chunk = [];
      if (Array.isArray(res)) chunk = res;
      else if (res && typeof res === "object") chunk = res.records || [];
      records = records.concat(chunk);
    }
    return records;
  }

  function segsForCases(records, cases) {
    var byNo = {};
    var byStem = {};
    (records || []).forEach(function (rec) {
      var videoBySeg = {};
      (rec.outboxes || []).forEach(function (o) {
        if (o && o.segmentId && o.videoUrl) videoBySeg[String(o.segmentId)] = o.videoUrl;
      });
      (rec.segments || []).forEach(function (s) {
        if (!s) return;
        var info = {
          segmentId: s.segmentId || "",
          segmentNo: s.segmentNo,
          videoParseStatus: s.videoParseStatus || "",
          dataProcessStatus: s.dataProcessStatus || "",
          pipelineStatus: s.pipelineStatus || "",
          failureMessage: s.failureMessage || "",
          videoUrl: videoBySeg[String(s.segmentId || "")] || "",
        };
        var no = Number(s.segmentNo);
        if (Number.isFinite(no) && no > 0) byNo[no] = info;
        var stem = videoStem(info.videoUrl);
        if (stem) byStem[stem] = info;
      });
    });
    return (cases || []).map(function (c, i) {
      var seq = c && c.seq != null ? Number(c.seq) : i + 1;
      return byNo[seq] || byStem[String((c && c.hand_id) || "")] || null;
    });
  }

  function buildDownstream(hand, item, seg) {
    var body = item && item.body;
    var fusionErr = (item && item.errorMsg) || (body && body.errorMsg) || "";
    var fusionFail = !!(item && isFailStatus(item.status));
    var videoFail = !!(seg && isFailStatus(seg.videoParseStatus));
    var videoOk = seg ? isParsedStatus(seg.videoParseStatus) : !videoFail;
    var dataFail = !!(seg && isFailStatus(seg.dataProcessStatus)) || fusionFail;
    var reason = ((seg && seg.failureMessage) || fusionErr || "").trim();
    var reject = !videoFail && dataFail;
    if (!reject && !videoFail) return null;
    var affect = "both";
    if (hand && !hand.miss_vis && hand.miss_rule) affect = "rule";
    else if (hand && hand.miss_vis && !hand.miss_rule) affect = "vis";
    return {
      reject: reject,
      parse_fail: videoFail,
      video_ok: videoOk && !videoFail,
      data_ok: !dataFail,
      reason: reason,
      short: shortReject(reason) || (videoFail ? "视频解析失败" : "下游拒绝"),
      affect: affect,
      video_parse: (seg && seg.videoParseStatus) || "",
      data_process: (seg && seg.dataProcessStatus) || (fusionFail ? "FAILED" : ""),
      segment_id: (seg && seg.segmentId) || (item && item.segmentId) || "",
    };
  }

  function attachDownstream(hands, aligned, segs) {
    var rejected = [];
    (hands || []).forEach(function (h, i) {
      var item = aligned && i < aligned.length ? aligned[i] : null;
      var seg = segs && i < segs.length ? segs[i] : null;
      var down = buildDownstream(h, item, seg);
      if (down) h.downstream = down;
      else delete h.downstream;
      if (seg && seg.videoUrl && !h.videoUrl) h.videoUrl = seg.videoUrl;
      if (seg && seg.segmentId) h.segmentId = seg.segmentId;
      if (down && down.reject) {
        rejected.push({
          seq: h.seq,
          hand_id: h.hand_id || "",
          short: down.short || "",
          reason: down.reason || "",
          affect: down.affect || "",
        });
      }
    });
    return rejected;
  }

  async function fetchRejects(opts) {
    var sessionIds = parseSessionIds(opts && opts.sessionId);
    var cases = (opts && opts.cases) || [];
    if (!sessionIds.length || !cases.length) return [];
    var records = await fetchRequestTraces((opts && opts.traceBase) || DEFAULT_TRACE, sessionIds);
    return segsForCases(records, cases);
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
    result.session_ids = sessionIds;
    (result.hands || []).forEach(function (h, i) {
      h.hand_id = String((cases[i] && cases[i].hand_id) || "");
    });
    var segs = [];
    try {
      if (onProgress) onProgress("正在拉下游拒绝原因…");
      var records = await fetchRequestTraces((opts && opts.traceBase) || DEFAULT_TRACE, sessionIds);
      segs = segsForCases(records, cases);
    } catch (e) {
      segs = cases.map(function () { return null; });
    }
    var rejected = attachDownstream(result.hands, pack.aligned, segs);
    var rejSeq = {};
    rejected.forEach(function (x) { rejSeq[x.seq] = 1; });
    result.align = {
      mode: pack.mode,
      n_gold: pack.n_gold,
      n_fusion: pack.n_fusion,
      n_matched: pack.n_matched,
      unmatched_gold: pack.unmatched_gold.filter(function (x) { return !rejSeq[x.seq]; }),
      unmatched_fusion: pack.unmatched_fusion,
      rejected: rejected,
    };
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
    var vis = extracted.hand ? visToUi(extracted.hand, extracted.blinds, posMap, gold) : null;
    var rr = body && typeof body === "object" ? body.ruleResult : null;
    var rule = rr ? ruleToUi(rr, posMap, gold) : null;
    return { vis: vis, rule: rule };
  }

  function emptyTxt(side, goldVal) {
    return (side === "gold" || !hasVal(goldVal)) ? "—" : "缺失";
  }

  function emptyHtml(side, goldVal) {
    return (side === "gold" || !hasVal(goldVal)) ? "—" : "<span class='miss-lab'>缺失</span>";
  }

  function displayVal(v, side, goldVal) {
    if (v == null || v === "") return emptyHtml(side || "gold", goldVal !== undefined ? goldVal : v);
    if (Array.isArray(v) && v[0] === "__len__") return "len " + v[1];
    if (typeof v === "boolean") return v ? "true" : "false";
    if (typeof v === "object") {
      try { return JSON.stringify(v); } catch (e) { return String(v); }
    }
    return String(v);
  }

  function causeOf(g, v, r, hasVis, hasRule) {
    if (!hasVal(g)) {
      if (!hasVal(v) && !hasVal(r)) return { id: "ok", lab: "匹配" };
      if (hasVal(v) && (!hasRule || valuesEqual(v, r))) return { id: "vis", lab: "视觉引入" };
      if (!hasVal(v) && hasVal(r)) return { id: "rule", lab: "规则引入" };
      return { id: "both", lab: "视觉错、规则又偏" };
    }
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

  function visHistory(body, posMap, goldUi) {
    var extracted = extractVis(body);
    var hand = extracted.hand;
    if (!hand || typeof hand !== "object") return null;
    var ext = ((body && body.rawJson) || {}).llm_extraction || {};
    var blinds = extracted.blinds || {};
    var cfg = ext.blinds_config || {};
    var straddle = parseNum(cfg.straddle != null ? cfg.straddle : blinds.straddle);
    var byPos = {};
    var byNick = {};
    (hand.players || []).forEach(function (p) {
      if (!p || typeof p !== "object") return;
      if (p.position) byPos[normPos(p.position)] = p;
      var k = nickKey(p.nickname);
      if (k && !(k in byNick)) byNick[k] = p;
    });
    var nameToSeat = nameToSeatFromUi(goldUi);
    var slots = goldSlotsFromUi(goldUi);
    var useNick = slots.some(function (s) { return nickKey(s.name); });
    var players = [];
    if (useNick) {
      slots.forEach(function (s) {
        var p = byNick[nickKey(s.name)];
        var init = p ? parseNum(p.initial_chips) : undefined;
        var fin = p ? parseNum(p.final_chips) : undefined;
        var net = p ? parseNum(p.net_won || p.profit || p.chips_won) : undefined;
        players.push({
          seat: s.seat,
          pos: p ? normPos(p.position) : s.pos,
          name: p ? (p.nickname || "") : "",
          init: init,
          final: fin,
          net: net,
          cards: p ? visHole(p, hand) : [],
          hero: !!(p && p.is_hero),
        });
      });
    } else {
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
    }
    players.sort(function (a, b) { return a.seat - b.seat; });
    var sbSeat, bbSeat, straddleSeat;
    var actions = [];
    (hand.actions || []).forEach(function (a) {
      if (!a || typeof a !== "object") return;
      var pos = normPos(a.player_position);
      var visP = byPos[pos] || (posTwin(pos) ? byPos[posTwin(pos)] : null);
      var nick = visActionNick(a, byPos);
      var seat = resolveSeatByNick(nick, nameToSeat, a.player_position, posMap);
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
          name: visP ? (visP.nickname || visP.name || "") : nick,
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
        name: visP ? (visP.nickname || visP.name || "") : nick,
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
    return fillActionPots({
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
    });
  }

  function ruleHistory(rr, posMap, goldUi) {
    if (!rr || typeof rr !== "object") return null;
    var blinds = rr.blinds || {};
    var byLabel = {};
    var byPos = {};
    var byNick = {};
    (rr.players || []).forEach(function (row) {
      var cells = rowCells(row);
      if (cells.length < 3) return;
      byLabel[String(cells[0])] = cells;
      byPos[normPos(cells[1])] = cells;
      var k = nickKey(cells[2]);
      if (k && !(k in byNick)) byNick[k] = cells;
    });
    var nameToSeat = nameToSeatFromUi(goldUi);
    var slots = goldSlotsFromUi(goldUi);
    var useNick = slots.some(function (s) { return nickKey(s.name); });
    var players = [];
    function ruleHistPlayer(seat, cells, pos) {
      var hole = [];
      if (cells) {
        var shown = cells.length > 6 ? cells[6] : null;
        var raw = Array.isArray(shown) && shown.length ? shown : (cells.length > 3 ? cells[3] : null);
        hole = visCardList(raw);
      }
      var init = cells && cells.length > 4 ? parseNum(cells[4]) : undefined;
      var fin = cells && cells.length > 5 ? parseNum(cells[5]) : undefined;
      var net = cells && cells.length > 7 ? parseNum(cells[7]) : undefined;
      return {
        seat: seat,
        pos: pos,
        name: cells && cells.length > 2 ? String(cells[2] || "") : "",
        init: init,
        final: fin,
        net: net,
        cards: hole,
        hero: !!(cells && /hero/i.test(String(cells[2] || ""))),
      };
    }
    if (useNick) {
      slots.forEach(function (s) {
        var cells = byNick[nickKey(s.name)];
        players.push(ruleHistPlayer(s.seat, cells, cells ? normPos(cells[1]) : s.pos));
      });
    } else {
      Object.keys(posMap).forEach(function (pos) {
        players.push(ruleHistPlayer(posMap[pos], byPos[pos], pos));
      });
    }
    players.sort(function (a, b) { return a.seat - b.seat; });
    var sbSeat, bbSeat, straddleSeat;
    var straddle = parseNum(blinds.straddle);
    var actions = [];
    (rr.actions || []).forEach(function (row) {
      var cells = rowCells(row);
      if (cells.length < 3) return;
      var src = byLabel[String(cells[0])];
      var pos = src ? normPos(src[1]) : "";
      var name = src && src.length > 2 ? String(src[2] || "") : "";
      var seat = resolveSeatByNick(name, nameToSeat, pos, posMap);
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
          name: name,
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
        name: name,
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
    return fillActionPots({
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
    });
  }

  function playerBySeat(hist, seat) {
    var list = (hist && hist.players) || [];
    for (var i = 0; i < list.length; i++) {
      if (list[i].seat === seat) return list[i];
    }
    return null;
  }

  function playerByRole(hist, role) {
    if (!hist) return null;
    var seat = role === "SB" ? hist.sb_seat : role === "BB" ? hist.bb_seat : hist.straddle_seat;
    if (seat != null) return playerBySeat(hist, seat) || { seat: seat, pos: role === "STRADDLE" ? "" : role };
    if (role === "STRADDLE") return null;
    var list = hist.players || [];
    for (var i = 0; i < list.length; i++) {
      if (normPos(list[i] && list[i].pos) === role) return list[i];
    }
    return null;
  }

  function playerIdEq(a, b) {
    if (!a && !b) return true;
    if (!a || !b) return false;
    if (a.seat != null && b.seat != null && a.seat !== b.seat) return false;
    if (!posEq(a.pos, b.pos)) return false;
    var na = rosterNameKey(a.name);
    var nb = rosterNameKey(b.name);
    if (na && nb) return na === nb;
    return a.seat === b.seat;
  }

  function rosterNameKey(s) {
    return nickKey(s);
  }

  function playerByName(hist, name) {
    var want = rosterNameKey(name);
    if (!want) return null;
    var list = (hist && hist.players) || [];
    var exact = [];
    var loose = [];
    for (var i = 0; i < list.length; i++) {
      var n = rosterNameKey(list[i] && list[i].name);
      if (!n) continue;
      if (n === want) exact.push(list[i]);
      else if (want.length >= 2 && n.length >= 2 && (n.indexOf(want) === 0 || want.indexOf(n) === 0)) {
        loose.push(list[i]);
      }
    }
    if (exact.length === 1) return exact[0];
    if (!exact.length && loose.length === 1) return loose[0];
    return null;
  }

  function chipPeer(p, gp, goldHist) {
    if (!p || !goldHist) return gp;
    return playerByName(goldHist, p.name) || gp;
  }

  function enrichGoldHist(hist) {
    if (!hist) return null;
    var out = {};
    Object.keys(hist).forEach(function (k) { out[k] = hist[k]; });
    out.players = ((hist.players) || []).map(function (p) {
      if (!p || typeof p !== "object") return p;
      var c = {};
      Object.keys(p).forEach(function (k) { c[k] = p[k]; });
      return c;
    });
    out.actions = ((hist.actions) || []).map(function (a) {
      if (!a || typeof a !== "object") return a;
      return withActionFacts({
        street: a.street,
        seat: a.seat,
        pos: a.pos,
        who: a.who,
        name: a.name,
        action: a.action,
        amount: a.amount,
        post: a.post,
      }, a);
    });
    inferFinals(out);
    fillActionPots(out);
    return out;
  }

  function packHistories(goldHist, goldTree, body) {
    var posMap = posMapFromUi(goldTree || {});
    return {
      gold: enrichGoldHist(goldHist),
      vis: visHistory(body, posMap, goldTree),
      rule: ruleHistory(body && body.ruleResult, posMap, goldTree),
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

  function straddleOff(v) {
    if (v == null || v === "" || v === false) return true;
    if (v === true) return false;
    var n = parseNum(v);
    if (n != null) return Math.abs(n) < 1e-9;
    var s = String(v).trim().toLowerCase();
    return s === "false" || s === "no" || s === "none" || s === "null" || s === "—" || s === "-";
  }

  function straddleEq(a, b) {
    if (straddleOff(a) && straddleOff(b)) return true;
    return amtEq(a, b);
  }

  function fmtAmt(v, side, goldVal) {
    if (v == null || v === "") return emptyHtml(side || "gold", goldVal !== undefined ? goldVal : v);
    var n = parseNum(v);
    if (n == null) return String(v);
    return Math.abs(n - Math.round(n)) < 1e-9 ? String(Math.round(n)) : String(n);
  }

  function posEq(a, b) {
    var x = normPos(a);
    var y = normPos(b);
    if (x === y) return true;
    var twin = posTwin(x);
    return !!(twin && twin === y);
  }

  function actEq(a, b) {
    if (!a && !b) return true;
    if (!a || !b) return false;
    if (!posEq(a.who || a.pos, b.who || b.pos)) return false;
    if (a.seat != null && b.seat != null && a.seat !== b.seat) return false;
    return actionLabel(a.action) === actionLabel(b.action) && amtEq(a.amount, b.amount);
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
    return u || emptyTxt("gold");
  }

  function pillKind(cn) {
    if (cn === "加注") return "raise";
    if (cn === "下注") return "bet";
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
        name: a.name,
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

  function actCellClass(cols, extra) {
    var c = "act-cell" + (extra ? " " + extra : "");
    if (cols && cols.pot) c += " has-pot";
    if (cols && cols.chips) c += " has-chips";
    return c;
  }

  function actHeadHtml(cols) {
    return "<div class='" + actCellClass(cols, "act-head") + "'>" +
      "<span class='act-seat'>桌位</span>" +
      "<span class='act-name'>昵称</span>" +
      "<span class='act-pos'>位置</span>" +
      "<span class='act-pill-h'>动作</span>" +
      "<span class='act-amt'>数额</span>" +
      (cols && cols.pot ? "<span class='act-pot'>底池</span>" : "") +
      (cols && cols.chips ? "<span class='act-stack'>剩余</span>" : "") +
      "</div>";
  }

  function actHtml(a, against, hist, cols, side) {
    if (!a) {
      var miss = "<div class='act-miss'>" + emptyHtml(side || "gold", against) + "</div>";
      return (side && side !== "gold" && against) ? wrapDiff(miss, side, 1, 0) : miss;
    }
    var whoOk = true, nameOk = true, actOk = true, amtOk = true, potOk = true, chipOk = true;
    if (side && side !== "gold" && !against) {
      whoOk = nameOk = actOk = amtOk = potOk = chipOk = false;
    } else if (against) {
      whoOk = posEq(a.who || a.pos, against.who || against.pos);
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
    var seat = a.seat != null ? a.seat : (p && p.seat);
    if (seat == null && hist && pos) {
      var want = {};
      want[normPos(pos)] = 1;
      var twin = posTwin(pos);
      if (twin) want[twin] = 1;
      var plist = hist.players || [];
      for (var si = 0; si < plist.length; si++) {
        if (want[normPos(plist[si].pos)]) {
          seat = plist[si].seat;
          p = plist[si];
          break;
        }
      }
    }
    var seatLab = seat != null ? "P" + seat : "";
    var name = "";
    if (a.name && !/^hero$/i.test(a.name)) name = a.name;
    else if (p && p.name) name = p.name;
    else if (p && p.hero) name = "Hero";
    if (against) {
      var gName = "";
      if (against.name && !/^hero$/i.test(against.name)) gName = against.name;
      if (gName && name) nameOk = valuesEqual(gName, name);
    }
    var cn = actCn(a.action);
    var mark = function (ok, kind) {
      if (ok) return "";
      if (!side || side === "gold") return " is-bad";
      if (kind === "pill") return " is-bad is-bad-" + side;
      return " is-bad diff-mark " + side;
    };
    var amtTxt = a.amount == null || a.amount === "" ? "" : fmtAmt(a.amount);
    if (amtTxt === "—") amtTxt = "";
    cols = cols || {};
    return "<div class='" + actCellClass(cols) + "'>" +
      "<span class='act-seat" + mark(whoOk) + "'>" + hhEsc(seatLab) + "</span>" +
      "<span class='act-name" + mark(nameOk) + "'>" + hhEsc(name) + "</span>" +
      "<span class='act-pos" + mark(whoOk) + "'>" + hhEsc(pos) + "</span>" +
      "<span class='act-pill " + pillKind(cn) + mark(actOk, "pill") + "'>" + hhEsc(cn) + "</span>" +
      "<span class='act-amt" + mark(amtOk) + "'>" + hhEsc(amtTxt) + "</span>" +
      (cols.pot ? "<span class='act-pot" + mark(potOk) + "'>" + hhEsc(fmtCount(a.pot)) + "</span>" : "") +
      (cols.chips ? "<span class='act-stack" + mark(chipOk) + "'>" + hhEsc(fmtCount(a.chips)) + "</span>" : "") +
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

  function cardsHtml(list, side, goldList) {
    if (!list || !list.length || list.every(function (v) { return v == null || v === ""; })) {
      return emptyHtml(side || "gold", goldList !== undefined ? goldList : list);
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

  function fmtWinners(hist, side, goldHist) {
    var seats = (hist && hist.winners) || [];
    if (!seats.length) return emptyHtml(side || "gold", goldHist !== undefined ? (goldHist && goldHist.winners) : seats);
    return seats.map(function (seat) { return whoHtml(playerBySeat(hist, seat), seat); }).join("、");
  }

  function fmtShowdown(v, side, goldVal) {
    if (v == null) return emptyHtml(side || "gold", goldVal !== undefined ? goldVal : v);
    return v ? "是" : "否";
  }

  function boardOf(hist, st) {
    return ((hist && hist.board) || {})[st] || [];
  }

  function tripleEq(g, v, r, eqFn) {
    eqFn = eqFn || amtEq;
    return eqFn(g, v) && eqFn(g, r);
  }

  function causeTd(eq) {
    if (eq) return "<td class='cause'></td>";
    return "<td class='cause'><span class='pill vis'>不一致</span></td>";
  }

  function secRow(title, extra) {
    return "<tr class='sec'><td colspan='5'><span class='sec-in'><span>" + title + "</span>" +
      (extra ? "<span class='pot'>" + extra + "</span>" : "") + "</span></td></tr>";
  }

  function foldBody(title, extra, rowsHtml, nBad) {
    if (!rowsHtml) return "";
    var mark = nBad ? "<span class='fold-n'>" + nBad + " 处不一致</span>" : "";
    return "<tbody class='cmp-fold'>" +
      "<tr class='sec'><td colspan='5'><span class='sec-in'><span><span class='caret'>▾</span> " + title + mark +
      "</span>" + (extra ? "<span class='pot'>" + extra + "</span>" : "") + "</span></td></tr>" +
      rowsHtml +
      "</tbody>";
  }

  function section(title, rowsHtml) {
    if (!rowsHtml) return "";
    var nBad = (rowsHtml.match(/class='is-diff'/g) || []).length;
    return foldBody(title, "", rowsHtml, nBad);
  }

  function tripleRow(who, g, v, r, onlyDiff, eqFn) {
    var eq = tripleEq(g, v, r, eqFn);
    if (onlyDiff && eq) return "";
    eqFn = eqFn || amtEq;
    return "<tr class='" + (eq ? "is-ok" : "is-diff") + "'>" +
      "<td class='who'>" + who + "</td>" +
      "<td class='val'>" + fmtAmt(g, "gold") + "</td>" +
      "<td class='val'>" + wrapDiff(fmtAmt(v, "vis", g), "vis", g, v, eqFn) + "</td>" +
      "<td class='val'>" + wrapDiff(fmtAmt(r, "rule", g), "rule", g, r, eqFn) + "</td>" +
      causeTd(eq) + "</tr>";
  }

  function tripleCells(who, gHtml, vHtml, rHtml, visEq, ruleEq) {
    if (ruleEq == null) ruleEq = visEq;
    var eq = !!(visEq && ruleEq);
    return "<tr class='" + (eq ? "is-ok" : "is-diff") + "'>" +
      "<td class='who'>" + who + "</td>" +
      "<td class='val'>" + gHtml + "</td>" +
      "<td class='val'>" + (visEq ? vHtml : wrapDiff(vHtml, "vis", 1, 0)) + "</td>" +
      "<td class='val'>" + (ruleEq ? rHtml : wrapDiff(rHtml, "rule", 1, 0)) + "</td>" +
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

  function markedTriple(who, gHtml, vHtml, rHtml, visEq, ruleEq) {
    var eq = !!(visEq && ruleEq);
    return "<tr class='" + (eq ? "is-ok" : "is-diff") + "'>" +
      "<td class='who'>" + who + "</td>" +
      "<td class='val'>" + gHtml + "</td>" +
      "<td class='val'>" + vHtml + "</td>" +
      "<td class='val'>" + rHtml + "</td>" +
      causeTd(eq) + "</tr>";
  }

  function postCellHtml(hist, role, amt, side, goldHist, goldAmt, eqFn) {
    eqFn = eqFn || amtEq;
    var p = playerByRole(hist, role);
    var gp = playerByRole(goldHist, role);
    var hasP = !!(p && p.seat != null);
    var hasAmt = role === "STRADDLE" ? !straddleOff(amt) : hasVal(amt);
    if (!hasP && !hasAmt) return emptyHtml(side || "gold", goldAmt);
    var who = hasP ? whoHtml(p, p.seat) : "<span class='miss-lab'>缺失</span>";
    if (side && side !== "gold" && !playerIdEq(p, gp)) {
      who = "<span class='diff-mark " + side + "'>" + who + "</span>";
    }
    var amtHtml = wrapDiff(fmtAmt(hasAmt ? amt : "", side || "gold", goldAmt), side, goldAmt, hasAmt ? amt : "", eqFn);
    var stack = hasP ? rosterDash(p.init) : "—";
    if (side && side !== "gold") {
      stack = wrapDiff(stack, side, gp && gp.init, p && p.init, amtEq);
    }
    return "<div class='post-cell'><span class='post-who'>" + who + "</span>" +
      "<span class='post-stack'>" + stack + "</span>" +
      "<span class='post-amt'>" + amtHtml + "</span></div>";
  }

  function postRoleRow(lab, role, amtKey, pack, eqFn) {
    eqFn = eqFn || amtEq;
    var g = pack.gold || {};
    var v = pack.vis || {};
    var r = pack.rule || {};
    var visEq = playerIdEq(playerByRole(v, role), playerByRole(g, role)) && eqFn(v[amtKey], g[amtKey]);
    var ruleEq = playerIdEq(playerByRole(r, role), playerByRole(g, role)) && eqFn(r[amtKey], g[amtKey]);
    return markedTriple(
      lab,
      postCellHtml(g, role, g[amtKey], "gold", g, g[amtKey], eqFn),
      postCellHtml(v, role, v[amtKey], "vis", g, g[amtKey], eqFn),
      postCellHtml(r, role, r[amtKey], "rule", g, g[amtKey], eqFn),
      visEq,
      ruleEq
    );
  }

  function playerCellHtml(p, field, side, gp) {
    if (!p) return emptyHtml(side || "gold", gp ? gp[field] : undefined);
    var who = whoHtml(p, p.seat);
    if (side && side !== "gold" && !playerIdEq(p, gp)) {
      who = "<span class='diff-mark " + side + "'>" + who + "</span>";
    }
    var val = wrapDiff(fmtAmt(p[field], side || "gold", gp ? gp[field] : undefined), side, gp ? gp[field] : undefined, p[field], amtEq);
    return "<div class='post-cell'><span class='post-who'>" + who + "</span><span class='post-amt'>" + val + "</span></div>";
  }

  function whoCardsHtml(p, cards, side, gp, goldCards) {
    var who = p ? whoHtml(p, p.seat) : "<span class='miss-lab'>缺失</span>";
    if (side && side !== "gold" && !playerIdEq(p, gp)) {
      who = "<span class='diff-mark " + side + "'>" + who + "</span>";
    }
    return "<div class='post-cell'><span class='post-who'>" + who + "</span><span class='post-cards'>" +
      wrapDiff(cardsHtml(cards, side, goldCards), side, goldCards, cards, cardsEq) + "</span></div>";
  }

  function playerTable(pack, field) {
    var rows = "";
    var g = pack.gold || {};
    var v = pack.vis || {};
    var r = pack.rule || {};
    seatListOf(pack).forEach(function (seat) {
      var pg = playerBySeat(g, seat);
      var pv = playerBySeat(v, seat);
      var pr = playerBySeat(r, seat);
      var visEq = playerIdEq(pv, pg) && amtEq(pv && pv[field], pg && pg[field]);
      var ruleEq = playerIdEq(pr, pg) && amtEq(pr && pr[field], pg && pg[field]);
      rows += markedTriple(
        "P" + seat,
        playerCellHtml(pg, field, "gold", pg),
        playerCellHtml(pv, field, "vis", pg),
        playerCellHtml(pr, field, "rule", pg),
        visEq,
        ruleEq
      );
    });
    return rows;
  }

  function actBlock(title, ag, av, ar, gHist, vHist, rHist, onlyDiff, skipMatch) {
    var n = Math.max(ag.length, av.length, ar.length);
    if (!n) return "";
    var cols = actColsOf(ag, av, ar);
    var rows = "";
    for (var i = 0; i < n; i++) {
      var eq = skipMatch ? true : (actEq(ag[i], av[i]) && actEq(ag[i], ar[i]));
      if (onlyDiff && !skipMatch && eq) continue;
      rows += "<tr class='" + (eq ? "is-ok" : "is-diff") + "'>" +
        "<td class='who'>" + (i + 1) + "</td>" +
        "<td class='val'>" + actHtml(ag[i], null, gHist, cols, "gold") + "</td>" +
        "<td class='val'>" + actHtml(av[i], skipMatch ? null : ag[i], vHist, cols, "vis") + "</td>" +
        "<td class='val'>" + actHtml(ar[i], skipMatch ? null : ag[i], rHist, cols, "rule") + "</td>" +
        causeTd(eq) + "</tr>";
    }
    if (!rows) return "";
    var pot = lastStreetPot(ag);
    var nBad = skipMatch ? 0 : (rows.match(/class='is-diff'/g) || []).length;
    var head = "<tr class='act-cols'>" +
      "<td class='who'>步</td>" +
      "<td class='val'>" + actHeadHtml(cols) + "</td>" +
      "<td class='val'>" + actHeadHtml(cols) + "</td>" +
      "<td class='val'>" + actHeadHtml(cols) + "</td>" +
      "<td class='cause'></td></tr>";
    var lab = title + " <span class='n'>(" + n + ")</span>" +
      (skipMatch ? " <span class='fold-skip'>不比对</span>" : "");
    return foldBody(lab, pot != null ? "底池 " + fmtCount(pot) : "", head + rows, nBad);
  }

  function rosterDash(v) {
    if (v == null || v === "") return "—";
    if (typeof v === "boolean") return v ? "true" : "false";
    var n = parseNum(v);
    if (n == null) return hhEsc(String(v));
    return Math.abs(n - Math.round(n)) < 1e-9 ? String(Math.round(n)) : String(n);
  }

  function rosterPlayerOn(p, strict) {
    if (!p) return false;
    if (!strict) return true;
    if (p.name) return true;
    if (p.hero) return true;
    if (hasVal(p.init) || hasVal(p.final) || hasVal(p.net)) return true;
    if (p.cards && p.cards.length) return true;
    return false;
  }

  function rosterCards(list) {
    if (!list || !list.length || list.every(function (v) { return v == null || v === ""; })) return "—";
    return list.map(function (code) {
      var p = parseCard(code);
      return "<span class='pcard " + p.cls + "'>" + hhEsc(p.text) + "</span>";
    }).join("");
  }

  function rosterPnl(p) {
    var n = parseNum(p && p.net);
    if (n == null && p) {
      var a = parseNum(p.init);
      var b = parseNum(p.final);
      if (a != null && b != null) n = b - a;
    }
    if (n == null) return "—";
    var txt = (n > 0 ? "+" : "") + (Math.abs(n - Math.round(n)) < 1e-9 ? String(Math.round(n)) : String(n));
    var cls = n > 0 ? "pnl-up" : (n < 0 ? "pnl-dn" : "");
    return cls ? "<span class='" + cls + "'>" + txt + "</span>" : txt;
  }

  function rosterBlind(hist, p) {
    if (!hist || !p || p.seat == null) return "—";
    var bits = [];
    if (hist.sb_seat === p.seat && hasVal(hist.sb)) bits.push("小盲" + rosterDash(hist.sb));
    if (hist.bb_seat === p.seat && hasVal(hist.bb)) bits.push("大盲" + rosterDash(hist.bb));
    if (hist.straddle_seat === p.seat && !straddleOff(hist.straddle)) bits.push("Straddle" + rosterDash(hist.straddle));
    return bits.length ? bits.join(" ") : "—";
  }

  function rosterHeadMeta(hist, goldHist, side) {
    if (!hist && !goldHist) return "";
    var src = hist || {};
    var bits = [];
    function bit(lab, hv, gv) {
      if (!hasVal(hv) && !hasVal(gv)) return;
      var txt = lab + " " + rosterDash(hv);
      bits.push(wrapDiff(txt, side, gv, hv));
    }
    bit("小盲", src.sb, goldHist && goldHist.sb);
    bit("大盲", src.bb, goldHist && goldHist.bb);
    bit("前注", src.ante, goldHist && goldHist.ante);
    if (!straddleOff(src.straddle) || (goldHist && !straddleOff(goldHist.straddle))) {
      bit("Straddle", src.straddle, goldHist && goldHist.straddle);
    }
    return bits.length ? "<span class='meta'>" + bits.join("　") + "</span>" : "";
  }

  function rosterNet(p) {
    var n = parseNum(p && p.net);
    if (n == null && p) {
      var a = parseNum(p.init);
      var b = parseNum(p.final);
      if (a != null && b != null) n = b - a;
    }
    return n;
  }

  function rosterOne(title, hist, strict, goldHist, side) {
    var head = "<div class='roster-h'><span class='src'>" + title + "</span>" +
      rosterHeadMeta(hist, goldHist, side) + "</div>";
    if (!hist && !goldHist) return "<div class='roster-block'>" + head + "<p class='roster-empty'>没有这份数据</p></div>";
    var seats = {};
    ((hist && hist.players) || []).forEach(function (p) {
      if (p && p.seat != null && rosterPlayerOn(p, strict)) seats[p.seat] = 1;
    });
    if (goldHist && side !== "gold") {
      (goldHist.players || []).forEach(function (p) {
        if (p && p.seat != null) seats[p.seat] = 1;
      });
    }
    var seatList = Object.keys(seats).map(Number).sort(function (a, b) { return a - b; });
    if (!seatList.length) {
      return "<div class='roster-block'>" + head + "<p class='roster-empty'>没有记下玩家</p></div>";
    }
    var cells = "<span>桌位</span><span>昵称</span><span>位置</span><span>初始</span><span>最终</span><span>盈亏</span><span>牌</span><span>盲注</span>";
    cells += seatList.map(function (seatNo) {
      var p = (hist && playerBySeat(hist, seatNo)) || { seat: seatNo };
      var gp = goldHist ? playerBySeat(goldHist, seatNo) : null;
      var chipsGp = chipPeer(p, gp, goldHist);
      var name = p.name ? hhEsc(p.name) : "—";
      if (p.hero) name += " <span class='hero-star'>★</span>";
      var seat = p.seat != null && p.seat !== "" ? "P" + p.seat : "—";
      var pos = p.pos ? hhEsc(p.pos) : "—";
      return "<span>" + seat + "</span>" +
        "<span>" + wrapDiff(name, side, gp && gp.name, p.name) + "</span>" +
        "<span>" + wrapDiff(pos, side, gp && gp.pos, p.pos) + "</span>" +
        "<span>" + wrapDiff(rosterDash(p.init), side, chipsGp && chipsGp.init, p.init, amtEq) + "</span>" +
        "<span>" + wrapDiff(rosterDash(p.final), side, chipsGp && chipsGp.final, p.final, amtEq) + "</span>" +
        "<span>" + wrapDiff(rosterPnl(p), side, rosterNet(chipsGp), rosterNet(p), amtEq) + "</span>" +
        "<span>" + wrapDiff(rosterCards(p.cards), side, chipsGp && chipsGp.cards, p.cards, cardsEq) + "</span>" +
        "<span>" + wrapDiff(rosterBlind(hist, p), side, gp ? rosterBlind(goldHist, gp) : "", rosterBlind(hist, p)) + "</span>";
    }).join("");
    return "<div class='roster-block'>" + head +
      "<div class='roster-scroll'><div class='roster-grid'>" + cells + "</div></div></div>";
  }

  function rosterHtml(pack) {
    if (!pack || (!pack.gold && !pack.vis && !pack.rule)) return "";
    return "<div class='roster'>" +
      rosterOne("源数据", pack.gold, false, null, "gold") +
      rosterOne("视觉", pack.vis, true, pack.gold, "vis") +
      rosterOne("规则", pack.rule, true, pack.gold, "rule") +
      "</div>";
  }

  function lockGridTracks(els, trackOfChild) {
    if (!els || !els.length) return;
    var maxN = 0;
    var i;
    els.forEach(function (el) {
      for (i = 0; i < el.children.length; i++) {
        maxN = Math.max(maxN, trackOfChild(el, i) + 1);
      }
    });
    if (!maxN) return;
    els.forEach(function (el) {
      el.style.gridTemplateColumns = "repeat(" + maxN + ", max-content)";
    });
    var max = [];
    for (i = 0; i < maxN; i++) max[i] = 0;
    els.forEach(function (el) {
      for (i = 0; i < el.children.length; i++) {
        var col = trackOfChild(el, i);
        var w = Math.ceil(el.children[i].getBoundingClientRect().width);
        if (w > max[col]) max[col] = w;
      }
    });
    var tpl = max.map(function (x) { return Math.max(x, 8) + "px"; }).join(" ");
    els.forEach(function (el) { el.style.gridTemplateColumns = tpl; });
  }

  function syncCompareLayout(root) {
    if (!root) return;
    [].slice.call(root.querySelectorAll(".roster-grid")).forEach(function (el) {
      el.style.width = "100%";
      el.style.gridTemplateColumns = "";
    });
    [].slice.call(root.querySelectorAll(".act-cell, .post-cell")).forEach(function (el) {
      el.style.width = "max-content";
      el.style.minWidth = "";
      el.style.maxWidth = "100%";
      el.style.gridTemplateColumns = "";
    });
    var table = root.querySelector("table.compare");
    if (!table) return;
    table.style.width = "max-content";
    table.style.maxWidth = "100%";
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
        postRoleRow("小盲", "SB", "sb", pack) +
        postRoleRow("大盲", "BB", "bb", pack) +
        postRoleRow("Straddle", "STRADDLE", "straddle", pack, straddleEq)
    );
    STREET_ORDER.forEach(function (st) {
      body += actBlock(STREET_LAB[st], actsOnDec(gActs, st, false), actsOnDec(vActs, st, false), actsOnDec(rActs, st, false), g, v, r, onlyDiff);
    });

    var visWin = winnersKey(g) === winnersKey(v);
    var ruleWin = winnersKey(g) === winnersKey(r);
    var winEq = visWin && ruleWin;
    var visSd = Boolean(g.showdown) === Boolean(v.showdown);
    var ruleSd = Boolean(g.showdown) === Boolean(r.showdown);
    var sdEq = visSd && ruleSd;
    body += section("结算",
      tripleRow("总底池", g.pot, v.pot, r.pot, onlyDiff) +
        (onlyDiff && sdEq ? "" : tripleCells("摊牌", fmtShowdown(g.showdown, "gold"), fmtShowdown(v.showdown, "vis", g.showdown), fmtShowdown(r.showdown, "rule", g.showdown), visSd, ruleSd)) +
        (onlyDiff && winEq ? "" : tripleCells("赢家", fmtWinners(g, "gold"), fmtWinners(v, "vis", g), fmtWinners(r, "rule", g), visWin, ruleWin))
    );
    body += section("终局筹码", playerTable(pack, "final"));

    var cardRows = "";
    var cardBad = 0;
    seatListOf(pack).forEach(function (seat) {
      var pg = playerBySeat(g, seat);
      var pv = playerBySeat(v, seat);
      var pr = playerBySeat(r, seat);
      var gc = pg ? pg.cards : [];
      var vc = pv ? pv.cards : [];
      var rc = pr ? pr.cards : [];
      var visEq = playerIdEq(pv, pg) && cardsEq(gc, vc);
      var ruleEq = playerIdEq(pr, pg) && cardsEq(gc, rc);
      var eq = visEq && ruleEq;
      if (onlyDiff && eq) return;
      if (!eq) cardBad += 1;
      cardRows += markedTriple(
        "P" + seat,
        whoCardsHtml(pg, gc, "gold", pg, gc),
        whoCardsHtml(pv, vc, "vis", pg, gc),
        whoCardsHtml(pr, rc, "rule", pg, gc),
        visEq,
        ruleEq
      );
    });
    var boardRows = "";
    [["flop", "翻牌"], ["turn", "转牌"], ["river", "河牌"]].forEach(function (pair) {
      var gc = boardOf(g, pair[0]);
      var vc = boardOf(v, pair[0]);
      var rc = boardOf(r, pair[0]);
      var visEq = cardsEq(gc, vc);
      var ruleEq = cardsEq(gc, rc);
      var eq = visEq && ruleEq;
      if (onlyDiff && eq) return;
      boardRows += tripleCells(pair[1], cardsHtml(gc, "gold"), cardsHtml(vc, "vis", gc), cardsHtml(rc, "rule", gc), visEq, ruleEq);
    });
    var cards = "";
    cards += section("起始筹码", playerTable(pack, "init"));
    if (cardRows) cards += foldBody("手牌", "", cardRows, cardBad);
    cards += section("公牌", boardRows);
    return { play: body, cards: cards };
  }

  global.E2EMatch = {
    lookup: lookup,
    DIM_KEYS: DIM_KEYS,
    dimOfPath: dimOfPath,
    summarizeDims: summarizeDims,
    dimRatesFromFieldStats: dimRatesFromFieldStats,
    DEFAULT_TRACE: DEFAULT_TRACE,
    parseSessionIds: parseSessionIds,
    matchBatch: matchBatch,
    fetchRejects: fetchRejects,
    attachDownstream: attachDownstream,
    shortReject: shortReject,
    fetchHandResult: fetchHandResult,
    listSessionHands: listSessionHands,
    clipUrlForHand: clipUrlForHand,
    videoName: videoName,
    stageTrees: stageTrees,
    compareStages: compareStages,
    flattenValues: flattenValues,
    flattenHistory: flattenHistory,
    seqGroups: seqGroups,
    compareSeq: compareSeq,
    flattenHand: flattenHand,
    compareFlat: compareFlat,
    skipComparePath: skipComparePath,
    isPlayerFollowOn: isPlayerFollowOn,
    playerSeatKey: playerSeatKey,
    valueAt: valueAt,
    inferFinals: inferFinals,
    wrapDiff: wrapDiff,
    valuesEqual: valuesEqual,
    posEq: posEq,
    cardsEq: cardsEq,
    hasVal: hasVal,
    emptyTxt: emptyTxt,
    emptyHtml: emptyHtml,
    causeOf: causeOf,
    displayVal: displayVal,
    isPost: isPost,
    pickVisPot: pickVisPot,
    packHistories: packHistories,
    normPos: normPos,
    rosterHtml: rosterHtml,
    syncCompareLayout: syncCompareLayout,
    historyHtml: historyHtml,
    visHistory: visHistory,
    ruleHistory: ruleHistory,
  };
})(window);
