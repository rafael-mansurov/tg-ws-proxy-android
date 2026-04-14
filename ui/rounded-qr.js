/*!
 * rounded-qr.js
 * Standalone rounded QR renderer (SVG only)
 *
 * Dependency for text->matrix:
 * - qrcode-generator (https://github.com/kazuhikoarase/qrcode-generator)
 *   CDN: https://cdn.jsdelivr.net/npm/qrcode-generator@1.4.4/qrcode.min.js
 *
 * Usage:
 *   const svg = await RoundedQR.generateSvg({ text: "https://example.com" });
 *   document.getElementById("preview").src =
 *     URL.createObjectURL(new Blob([svg], { type: "image/svg+xml" }));
 *
 */
(function (global) {
  "use strict";

  function fmt(n) {
    return Number(Number(n).toFixed(3));
  }

  function escapeXmlAttr(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/"/g, "&quot;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function roundedRectPathData(x, y, w, h, r) {
    var rr = Math.max(0, Math.min(r, w * 0.5, h * 0.5));
    var x0 = fmt(x), y0 = fmt(y), x1 = fmt(x + w), y1 = fmt(y + h);
    var xr0 = fmt(x + rr), yr0 = fmt(y + rr), xr1 = fmt(x + w - rr), yr1 = fmt(y + h - rr);
    return [
      "M", xr0, y0,
      "L", xr1, y0,
      "Q", x1, y0, x1, yr0,
      "L", x1, yr1,
      "Q", x1, y1, xr1, y1,
      "L", xr0, y1,
      "Q", x0, y1, x0, yr1,
      "L", x0, yr0,
      "Q", x0, y0, xr0, y0,
      "Z"
    ].join(" ");
  }

  function smoothModulePathData(x, y, size, neighbors) {
    var r = size * 0.5;
    var tl = !(neighbors.top || neighbors.left);
    var tr = !(neighbors.top || neighbors.right);
    var br = !(neighbors.bottom || neighbors.right);
    var bl = !(neighbors.bottom || neighbors.left);
    var x0 = fmt(x), y0 = fmt(y), x1 = fmt(x + size), y1 = fmt(y + size);
    var rx0 = fmt(x + r), ry0 = fmt(y + r), rx1 = fmt(x + size - r), ry1 = fmt(y + size - r);
    return [
      "M", tl ? rx0 : x0, y0,
      "L", tr ? rx1 : x1, y0,
      tr ? ["Q", x1, y0, x1, ry0].join(" ") : ["L", x1, y0].join(" "),
      "L", x1, br ? ry1 : y1,
      br ? ["Q", x1, y1, rx1, y1].join(" ") : ["L", x1, y1].join(" "),
      "L", bl ? rx0 : x0, y1,
      bl ? ["Q", x0, y1, x0, ry1].join(" ") : ["L", x0, y1].join(" "),
      "L", x0, tl ? ry0 : y0,
      tl ? ["Q", x0, y0, rx0, y0].join(" ") : ["L", x0, y0].join(" "),
      "Z"
    ].join(" ");
  }

  function buildQrMatrix(text, ecc) {
    if (!global.qrcode) {
      throw new Error("qrcode-generator not found. Include qrcode.min.js before rounded-qr.js");
    }
    var qr = global.qrcode(0, ecc || "H");
    qr.addData(text);
    qr.make();
    return qr;
  }

  function isFinderAt(row, col, count) {
    var inTopLeft = row <= 6 && col <= 6;
    var inTopRight = row <= 6 && col >= count - 7;
    var inBottomLeft = row >= count - 7 && col <= 6;
    return inTopLeft || inTopRight || inBottomLeft;
  }

  function getLogoBox(opts) {
    if (!opts.logoDataUrl) return null;
    var inner = opts.size - opts.margin * 2;
    var logoSize = Math.floor(inner * (opts.logoScale || 0.24));
    var x = Math.floor((opts.size - logoSize) / 2);
    var y = Math.floor((opts.size - logoSize) / 2);
    var pad = Math.max(4, Math.floor(logoSize * (opts.logoPadding || 0.12)));
    var radius = Math.floor(pad * (opts.logoBgRadiusFactor || 1.8));
    return {
      x: x,
      y: y,
      width: logoSize,
      height: logoSize,
      bgX: x - pad,
      bgY: y - pad,
      bgW: logoSize + pad * 2,
      bgH: logoSize + pad * 2,
      radius: radius
    };
  }

  function moduleIntersectsLogo(row, col, moduleSize, margin, logoBox) {
    if (!logoBox) return false;
    var x = margin + col * moduleSize;
    var y = margin + row * moduleSize;
    return !(
      x + moduleSize <= logoBox.bgX ||
      x >= logoBox.bgX + logoBox.bgW ||
      y + moduleSize <= logoBox.bgY ||
      y >= logoBox.bgY + logoBox.bgH
    );
  }

  function isRenderableDark(qr, row, col, count, moduleSize, margin, logoBox) {
    if (row < 0 || col < 0 || row >= count || col >= count) return false;
    if (!qr.isDark(row, col)) return false;
    if (moduleIntersectsLogo(row, col, moduleSize, margin, logoBox)) return false;
    return true;
  }

  function normalizeOptions(options) {
    var o = options || {};
    if (!o.text || !String(o.text).trim()) {
      throw new Error("RoundedQR: `text` is required.");
    }
    return {
      text: String(o.text),
      size: Number(o.size || 800),
      margin: Number(o.margin == null ? 24 : o.margin),
      ecc: String(o.ecc || "H"),                // L M Q H
      dotsStyle: String(o.dotsStyle || "smooth"), // square | dots | smooth
      darkColor: String(o.darkColor || "#000000"),
      lightColor: String(o.lightColor || "#ffffff"),
      logoDataUrl: o.logoDataUrl ? String(o.logoDataUrl) : "",
      logoScale: Number(o.logoScale || 0.24),
      logoPadding: Number(o.logoPadding || 0.12),
      logoBgRadiusFactor: Number(o.logoBgRadiusFactor || 1.8)
    };
  }

  function buildSvgParts(opts) {
    var qr = buildQrMatrix(opts.text, opts.ecc);
    var count = qr.getModuleCount();
    var drawSize = opts.size - opts.margin * 2;
    var moduleSize = drawSize / count;
    var logoBox = getLogoBox(opts);
    var parts = [];

    parts.push('<?xml version="1.0" encoding="UTF-8"?>');
    parts.push('<svg xmlns="http://www.w3.org/2000/svg" width="' + opts.size + '" height="' + opts.size + '" viewBox="0 0 ' + opts.size + ' ' + opts.size + '">');
    for (var row = 0; row < count; row += 1) {
      for (var col = 0; col < count; col += 1) {
        if (!isRenderableDark(qr, row, col, count, moduleSize, opts.margin, logoBox)) continue;
        if (isFinderAt(row, col, count)) continue;
        var x = opts.margin + col * moduleSize;
        var y = opts.margin + row * moduleSize;

        if (opts.dotsStyle === "square") {
          parts.push('<rect x="' + fmt(x) + '" y="' + fmt(y) + '" width="' + fmt(moduleSize) + '" height="' + fmt(moduleSize) + '" fill="' + escapeXmlAttr(opts.darkColor) + '" stroke="' + escapeXmlAttr(opts.darkColor) + '" stroke-width="' + fmt(moduleSize * 0.08) + '" shape-rendering="geometricPrecision"/>');
          continue;
        }
        if (opts.dotsStyle === "dots") {
          parts.push('<circle cx="' + fmt(x + moduleSize * 0.5) + '" cy="' + fmt(y + moduleSize * 0.5) + '" r="' + fmt(moduleSize * 0.46) + '" fill="' + escapeXmlAttr(opts.darkColor) + '" stroke="' + escapeXmlAttr(opts.darkColor) + '" stroke-width="' + fmt(moduleSize * 0.08) + '" shape-rendering="geometricPrecision"/>');
          continue;
        }

        var n = {
          top: isRenderableDark(qr, row - 1, col, count, moduleSize, opts.margin, logoBox),
          right: isRenderableDark(qr, row, col + 1, count, moduleSize, opts.margin, logoBox),
          bottom: isRenderableDark(qr, row + 1, col, count, moduleSize, opts.margin, logoBox),
          left: isRenderableDark(qr, row, col - 1, count, moduleSize, opts.margin, logoBox)
        };
        parts.push('<path d="' + smoothModulePathData(x, y, moduleSize, n) + '" fill="' + escapeXmlAttr(opts.darkColor) + '" stroke="' + escapeXmlAttr(opts.darkColor) + '" stroke-width="' + fmt(moduleSize * 0.08) + '" shape-rendering="geometricPrecision"/>');
      }
    }

    var finderPos = [
      { row: 0, col: 0 },
      { row: 0, col: count - 7 },
      { row: count - 7, col: 0 }
    ];
    finderPos.forEach(function (pos) {
      var fx = opts.margin + pos.col * moduleSize;
      var fy = opts.margin + pos.row * moduleSize;
      parts.push('<path d="' + roundedRectPathData(fx, fy, moduleSize * 7, moduleSize * 7, moduleSize * 1.45) + '" fill="' + escapeXmlAttr(opts.darkColor) + '" stroke="' + escapeXmlAttr(opts.darkColor) + '" stroke-width="' + fmt(moduleSize * 0.08) + '" shape-rendering="geometricPrecision"/>');
      parts.push('<path d="' + roundedRectPathData(fx + moduleSize, fy + moduleSize, moduleSize * 5, moduleSize * 5, moduleSize * 1.05) + '" fill="' + escapeXmlAttr(opts.lightColor) + '"/>');
      parts.push('<path d="' + roundedRectPathData(fx + moduleSize * 2, fy + moduleSize * 2, moduleSize * 3, moduleSize * 3, moduleSize * 0.75) + '" fill="' + escapeXmlAttr(opts.darkColor) + '" stroke="' + escapeXmlAttr(opts.darkColor) + '" stroke-width="' + fmt(moduleSize * 0.08) + '" shape-rendering="geometricPrecision"/>');
    });

    if (logoBox) {
      parts.push('<path d="' + roundedRectPathData(logoBox.bgX, logoBox.bgY, logoBox.bgW, logoBox.bgH, logoBox.radius) + '" fill="' + escapeXmlAttr(opts.lightColor) + '"/>');
      parts.push('<image href="' + escapeXmlAttr(opts.logoDataUrl) + '" x="' + fmt(logoBox.x) + '" y="' + fmt(logoBox.y) + '" width="' + fmt(logoBox.width) + '" height="' + fmt(logoBox.height) + '"/>');
    }

    parts.push("</svg>");
    return parts.join("");
  }

  async function generateSvg(options) {
    var opts = normalizeOptions(options);
    return buildSvgParts(opts);
  }

  global.RoundedQR = {
    generateSvg: generateSvg
  };
})(typeof window !== "undefined" ? window : globalThis);
