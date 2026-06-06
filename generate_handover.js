const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, LevelFormat, HeadingLevel,
  BorderStyle, WidthType, ShadingType, PageNumber, PageBreak
} = require("docx");

// ============================================================
// 配置
// ============================================================
const FONT = { ascii: "Arial", hAnsi: "Arial", eastAsia: "Microsoft YaHei" };
const BORDER = { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" };
const BORDERS = { top: BORDER, bottom: BORDER, left: BORDER, right: BORDER };

// 编号计数器
let numGroupCounter = 0;
const numberConfigs = [];
for (let i = 0; i < 30; i++) {
  numberConfigs.push({
    reference: `numbers-${i}`,
    levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }],
  });
}

function startNumGroup() { numGroupCounter++; }
function num(text) {
  return new Paragraph({ numbering: { reference: `numbers-${numGroupCounter}`, level: 0 }, spacing: { after: 60 }, children: [new TextRun({ text, font: FONT, size: 21 })] });
}
function bullet(text) {
  return new Paragraph({ numbering: { reference: "bullets", level: 0 }, spacing: { after: 40 }, children: [new TextRun({ text, font: FONT, size: 21 })] });
}

function heading(text, level) {
  return new Paragraph({ heading: level, children: [new TextRun({ text, font: FONT })] });
}

function para(text, opts = {}) {
  return new Paragraph({
    spacing: { after: 80 },
    ...opts,
    children: [new TextRun({ text, font: FONT, size: 21, ...(opts.run || {}) })]
  });
}

function boldPara(text) {
  return para(text, { run: { bold: true } });
}

function makeCell(text, opts = {}) {
  return new TableCell({
    borders: BORDERS,
    width: opts.width ? { size: opts.width, type: WidthType.DXA } : undefined,
    shading: opts.header ? { fill: "1A3C6E", type: ShadingType.CLEAR } : undefined,
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: [new Paragraph({
      children: [new TextRun({
        text,
        font: FONT,
        size: 19,
        bold: opts.header || false,
        color: opts.header ? "FFFFFF" : "000000",
      })]
    })]
  });
}

function makeTable(headers, rows, widths) {
  const totalWidth = widths.reduce((a, b) => a + b, 0);
  return new Table({
    width: { size: totalWidth, type: WidthType.DXA },
    columnWidths: widths,
    rows: [
      new TableRow({ cantSplit: true, children: headers.map((h, i) => makeCell(h, { header: true, width: widths[i] })) }),
      ...rows.map(row => new TableRow({ cantSplit: true, children: row.map((cell, i) => makeCell(cell, { width: widths[i] })) })),
    ]
  });
}

// ============================================================
// 文档内容
// ============================================================
const children = [];

// ---- 封面 ----
children.push(new Paragraph({ spacing: { before: 3000 }, children: [] }));
children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [new TextRun({ text: "NeoTrade3", font: { ...FONT, eastAsia: "Microsoft YaHei" }, size: 56, bold: true, color: "1A3C6E" })] }));
children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 100 }, children: [new TextRun({ text: "A\u80A1\u4F4E\u9891\u91CF\u5316\u4EA4\u6613\u7CFB\u7EDF", font: FONT, size: 36, color: "333333" })] }));
children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 600 }, children: [new TextRun({ text: "\u2014\u2014 \u9879\u76EE\u4EA4\u63A5\u6587\u6863 \u2014\u2014", font: FONT, size: 28, color: "666666" })] }));
children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 100 }, children: [new TextRun({ text: "\u7248\u672C: v0.1.0 | \u65E5\u671F: 2026-05-26", font: FONT, size: 22, color: "888888" })] }));
children.push(new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "\u72B6\u6001: \u6838\u5FC3\u529F\u80FD\u5DF2\u5B8C\u6210\uFF0C\u5F85\u524D\u7AEF\u96C6\u6210", font: FONT, size: 22, color: "888888" })] }));
children.push(new Paragraph({ children: [new PageBreak()] }));

// ---- 目录概览 ----
children.push(heading("\u76EE\u5F55", HeadingLevel.HEADING_1));
children.push(bullet("\u4E00\u3001\u9879\u76EE\u6982\u8FF0\u4E0E\u6838\u5FC3\u76EE\u6807"));
children.push(bullet("\u4E8C\u3001\u7CFB\u7EDF\u67B6\u6784\u4E0E\u76EE\u5F55\u7ED3\u6784"));
children.push(bullet("\u4E09\u3001\u73AF\u5883\u4E0E\u542F\u52A8"));
children.push(bullet("\u56DB\u3001\u6570\u636E\u5E93\u7ED3\u6784"));
children.push(bullet("\u4E94\u3001ML \u6A21\u578B\u8BAD\u7EC3\u4F53\u7CFB"));
children.push(bullet("\u516D\u3001API \u7AEF\u70B9\u5B8C\u6574\u5217\u8868"));
children.push(bullet("\u4E03\u3001\u56DE\u6D4B\u7ED3\u679C\u4E0E\u7B56\u7565\u5BF9\u6BD4"));
children.push(bullet("\u516B\u3001\u5B9E\u9A8C\u8BB0\u5F55\u4E0E\u5173\u952E\u53D1\u73B0"));
children.push(bullet("\u4E5D\u3001\u5DF2\u77E5\u95EE\u9898\u4E0E\u98CE\u9669"));
children.push(bullet("\u5341\u3001\u540E\u7EED\u4F18\u5316\u5EFA\u8BAE"));
children.push(bullet("\u5341\u4E00\u3001\u524D\u7AEF Dashboard \u6838\u5FC3\u8981\u6C42\u4E0E\u903B\u8F91"));
children.push(bullet("\u5341\u4E8C\u3001\u9644\u5F55"));
children.push(new Paragraph({ children: [new PageBreak()] }));

// ---- 一、项目概述 ----
children.push(heading("\u4E00\u3001\u9879\u76EE\u6982\u8FF0\u4E0E\u6838\u5FC3\u76EE\u6807", HeadingLevel.HEADING_1));

children.push(heading("1.1 \u9879\u76EE\u5B9A\u4F4D", HeadingLevel.HEADING_2));
children.push(para("NeoTrade3 \u662F\u4E00\u5957 A \u80A1\u4F4E\u9891\u91CF\u5316\u4EA4\u6613\u7CFB\u7EDF\uFF0C\u57FA\u4E8E\u6280\u672F\u9762\u7279\u5F81\u7684\u968F\u673A\u68EE\u6797\u6A21\u578B\uFF0C\u5BF9 Top 100 \u6210\u4EA4\u989D\u80A1\u7968\u8FDB\u884C\u6DA8\u8DCC\u9884\u6D4B\u3002\u7CFB\u7EDF\u6838\u5FC3\u7279\u70B9\uFF1A"));
children.push(bullet("\u4F4E\u9891\u4EA4\u6613\uFF1A\u6301\u6709 5 \u4E2A\u4EA4\u6613\u65E5\uFF0C\u9002\u5408\u5468\u7EA7\u8C03\u4ED3"));
children.push(bullet("\u6280\u672F\u9762\u9A71\u52A8\uFF1A\u4EC5\u4F7F\u7528\u4EF7\u91CF\u6570\u636E\uFF0C\u4E0D\u4F9D\u8D56\u57FA\u672C\u9762"));
children.push(bullet("\u7EAF Python \u6808\uFF1A\u65E0\u7B2C\u4E09\u65B9 Web \u6846\u67B6\uFF0C\u4EC5\u4F9D\u8D56 numpy + scikit-learn"));
children.push(bullet("\u6570\u636E\u5E93\u9A71\u52A8\uFF1A\u6240\u6709\u6570\u636E\u5B58\u50A8\u5728 SQLite\uFF0C\u96F6\u5916\u90E8\u670D\u52A1\u4F9D\u8D56"));

children.push(heading("1.2 \u6838\u5FC3\u76EE\u6807\u5B8C\u6210\u60C5\u51B5", HeadingLevel.HEADING_2));
children.push(makeTable(
  ["\u76EE\u6807", "\u72B6\u6001", "\u8BF4\u660E"],
  [
    ["ML \u6A21\u578B\u8BAD\u7EC3", "\u2705 \u5DF2\u5B8C\u6210", "\u6837\u672C\u5916\u51C6\u786E\u7387 76.67%\uFF0C\u5386\u53F2\u6700\u9AD8 80.39%"],
    ["\u56DE\u6D4B\u6846\u67B6", "\u2705 \u5DF2\u5B8C\u6210", "\u5E74\u5316 36.74%\uFF0C\u80DC\u7387 77.19%\uFF0C\u76C8\u4E8F\u6BD4 2.70"],
    ["\u6A21\u578B\u90E8\u7F72 API", "\u2705 \u5DF2\u5B8C\u6210", "/api/prediction/signals + /api/prediction/backtest"],
    ["\u677F\u5757\u8F6E\u52A8\u5F15\u64CE", "\u2705 \u5DF2\u5B8C\u6210", "71 \u4E2A\u677F\u5757\u6392\u540D + \u9886\u6DA8\u80A1\u7B5B\u9009"],
    ["\u677F\u5757\u8F6E\u52A8 API", "\u2705 \u5DF2\u5B8C\u6210", "/api/sector-rotation/ranking + /api/sector-rotation/signals"],
    ["\u57FA\u672C\u9762\u6570\u636E\u9002\u914D", "\u2705 \u5DF2\u5B8C\u6210", "PE/PB/ROE \u9002\u914D\u5668\uFF08\u5F53\u524D\u672A\u542F\u7528\uFF09"],
    ["\u524D\u7AEF\u96C6\u6210", "\u23F3 \u5F85\u5B8C\u6210", "Dashboard \u5DF2\u6709\u6846\u67B6\uFF0C\u9700\u96C6\u6210\u65B0\u7AEF\u70B9"],
  ],
  [2000, 1500, 5860]
));

// ---- 二、系统架构 ----
children.push(heading("\u4E8C\u3001\u7CFB\u7EDF\u67B6\u6784\u4E0E\u76EE\u5F55\u7ED3\u6784", HeadingLevel.HEADING_1));

children.push(heading("2.1 \u76EE\u5F55\u7ED3\u6784", HeadingLevel.HEADING_2));
children.push(para("\u9879\u76EE\u6839\u76EE\u5F55\u4E3A NeoTrade3/\uFF0C\u6838\u5FC3\u76EE\u5F55\u5982\u4E0B\uFF1A"));
children.push(makeTable(
  ["\u76EE\u5F55/\u6587\u4EF6", "\u7528\u9014"],
  [
    ["apps/api/main.py", "API \u670D\u52A1\uFF08\u7EA6 8400 \u884C\uFF0C\u6240\u6709\u8DEF\u7531\u5728\u6B64\u6587\u4EF6\u4E2D\uFF09"],
    ["apps/dashboard/main.py", "Web \u4EEA\u8868\u76D8\uFF08\u7AEF\u53E3 18031\uFF09"],
    ["apps/worker/main.py", "\u540E\u53F0\u4EFB\u52A1\uFF08\u6570\u636E\u91C7\u96C6\u3001\u7F16\u6392\uFF09"],
    ["neotrade3/ml/autore/train.py", "ML \u8BAD\u7EC3\u811A\u672C\uFF08\u6838\u5FC3\u5B9E\u9A8C\u6587\u4EF6\uFF09"],
    ["neotrade3/ml/autore/config.py", "ML \u5B9E\u9A8C\u914D\u7F6E\uFF08\u641C\u7D22\u7A7A\u95F4\u3001\u8BB0\u5F55\u5DE5\u5177\uFF09"],
    ["neotrade3/data/akshare_adapter.py", "\u57FA\u672C\u9762\u6570\u636E\u9002\u914D\u5668"],
    ["backtest.py", "ML \u7B56\u7565\u56DE\u6D4B\u6846\u67B6"],
    ["backtest_sector_rotation.py", "\u677F\u5757\u8F6E\u52A8\u7B56\u7565\u56DE\u6D4B"],
    ["sector_rotation.py", "\u677F\u5757\u8F6E\u52A8\u5F15\u64CE"],
    ["config/", "\u914D\u7F6E\u6587\u4EF6\uFF08\u7B5B\u9009\u5668\u3001\u7F16\u6392\u5668\u3001\u5B9E\u9A8C\u5BA4\uFF09"],
    ["var/db/stock_data.db", "SQLite \u6570\u636E\u5E93\uFF08\u6838\u5FC3\u6570\u636E\uFF09"],
    ["var/models/autore_v2_best.pkl", "\u5F53\u524D\u6700\u4F18\u6A21\u578B"],
    ["var/backtest_results/", "\u56DE\u6D4B\u7ED3\u679C JSON"],
    ["var/sector_rotation/", "\u677F\u5757\u8F6E\u52A8\u4FE1\u53F7 JSON"],
  ],
  [3200, 6160]
));

children.push(heading("2.2 \u6280\u672F\u6808", HeadingLevel.HEADING_2));
children.push(makeTable(
  ["\u7EC4\u4EF6", "\u6280\u672F", "\u8BF4\u660E"],
  [
    ["HTTP \u670D\u52A1", "Python http.server.ThreadingHTTPServer", "\u65E0\u7B2C\u4E09\u65B9\u6846\u67B6\uFF0C\u81EA\u5B9A\u4E49\u8DEF\u7531"],
    ["ML \u6A21\u578B", "sklearn RandomForestClassifier", "\u968F\u673A\u68EE\u6797\uFF0C300 \u68F5\u6811\uFF0C\u6DF1\u5EA6 20"],
    ["\u6570\u636E\u5E93", "SQLite3", "\u5355\u6587\u4EF6\uFF0C\u96F6\u5916\u90E8\u670D\u52A1"],
    ["\u6570\u636E\u5904\u7406", "numpy", "\u7279\u5F81\u8BA1\u7B97\u3001\u7EBF\u6027\u56DE\u5F52"],
    ["\u524D\u7AEF", "\u7EAF HTML/CSS/JS", "\u65E0 React/Vue\uFF0C\u7EAF\u539F\u751F"],
    ["Python \u7248\u672C", ">=3.10", "\u4F7F\u7528 f-string\u3001match-case \u7B49\u7279\u6027"],
  ],
  [2000, 3800, 3560]
));

children.push(heading("2.3 \u542F\u52A8\u987A\u5E8F", HeadingLevel.HEADING_2));
children.push(para("\u6B63\u5E38\u542F\u52A8\u987A\u5E8F\uFF1Aworker \u2192 api \u2192 dashboard\u3002\u5F53\u524D\u5F00\u53D1\u9636\u6BB5\u53EA\u9700\u8981\u542F\u52A8 API\uFF1A"));
children.push(bullet("\u6B65\u9AA4 1\uFF1Acd NeoTrade3 && source venv/bin/activate"));
children.push(bullet("\u6B65\u9AA4 2\uFF1Apython apps/api/main.py --host 0.0.0.0 --port 18030"));
children.push(bullet("\u6B65\u9AA4 3\uFF1A\u8BBF\u95EE http://localhost:18030/healthz \u786E\u8BA4\u670D\u52A1\u6B63\u5E38"));
children.push(bullet("\u6B65\u9AA4 4\uFF08\u53EF\u9009\uFF09\uFF1Apython apps/dashboard/main.py \u542F\u52A8\u4EEA\u8868\u76D8\uFF08\u7AEF\u53E3 18031\uFF09"));

// ---- 三、数据库 ----
children.push(heading("\u4E09\u3001\u6570\u636E\u5E93\u7ED3\u6784", HeadingLevel.HEADING_1));
children.push(para("\u6570\u636E\u5E93\u4F4D\u4E8E var/db/stock_data.db\uFF0C\u6838\u5FC3\u8868\u7ED3\u6784\uFF1A"));

children.push(heading("3.1 stocks \u8868", HeadingLevel.HEADING_2));
children.push(para("\u80A1\u7968\u57FA\u7840\u4FE1\u606F\u8868\uFF0C\u5305\u542B\u57FA\u672C\u9762\u6570\u636E\uFF1A"));
children.push(makeTable(
  ["\u5B57\u6BB5", "\u7C7B\u578B", "\u8BF4\u660E"],
  [
    ["code", "VARCHAR(10)", "\u80A1\u7968\u4EE3\u7801\uFF08\u4E3B\u952E\uFF09"],
    ["name", "VARCHAR", "\u80A1\u7968\u540D\u79F0"],
    ["sector_lv1", "VARCHAR", "\u7533\u4E07\u4E00\u7EA7\u884C\u4E1A\uFF08\u5982 C39=\u8BA1\u7B97\u673A\uFF09"],
    ["total_market_cap", "REAL", "\u603B\u5E02\u503C\uFF08\u5355\u4F4D\uFF1A\u5143\uFF09"],
    ["circulating_market_cap", "REAL", "\u6D41\u901A\u5E02\u503C\uFF08\u5355\u4F4D\uFF1A\u5143\uFF09"],
    ["pe_ratio", "REAL", "\u5E02\u76C8\u7387"],
    ["pb_ratio", "REAL", "\u5E02\u51C0\u7387"],
    ["roe", "REAL", "\u51C0\u8D44\u4EA7\u6536\u76CA\u7387"],
    ["revenue_growth", "REAL", "\u8425\u6536\u589E\u957F\u7387"],
    ["profit_growth", "REAL", "\u5229\u6DA6\u589E\u957F\u7387"],
    ["eps", "REAL", "\u6BCF\u80A1\u6536\u76CA"],
    ["is_delisted", "INTEGER", "\u662F\u5426\u9000\u5E02"],
  ],
  [2500, 1800, 5060]
));

children.push(heading("3.2 daily_prices \u8868", HeadingLevel.HEADING_2));
children.push(para("\u65E5\u7EBF\u884C\u60C5\u8868\uFF0C\u6838\u5FC3\u5B57\u6BB5\uFF1A"));
children.push(makeTable(
  ["\u5B57\u6BB5", "\u7C7B\u578B", "\u8BF4\u660E"],
  [
    ["code", "VARCHAR(10)", "\u80A1\u7968\u4EE3\u7801"],
    ["trade_date", "VARCHAR(10)", "\u4EA4\u6613\u65E5\u671F\uFF08YYYY-MM-DD\uFF09"],
    ["open/high/low/close", "REAL", "\u5F00\u76D8/\u6700\u9AD8/\u6700\u4F4E/\u6536\u76D8\u4EF7"],
    ["volume", "REAL", "\u6210\u4EA4\u91CF\uFF08\u80A1\uFF09"],
    ["amount", "REAL", "\u6210\u4EA4\u989D\uFF08\u5143\uFF09"],
    ["pct_change", "REAL", "\u6DA8\u8DCC\u5E45\uFF08%\uFF09"],
  ],
  [3000, 2000, 4360]
));

children.push(para("\u6570\u636E\u89C4\u6A21\uFF1A\u7EA6 5000+ \u53EA\u80A1\u7968\uFF0C\u65E5\u7EBF\u6570\u636E\u8986\u76D6 2024 \u5E74\u81F3\u4ECA\u3002\u5E02\u503C\u5355\u4F4D\u4E3A\u5143\uFF08\u5DE5\u5546\u94F6\u884C\u7EA6 2.63 \u4E07\u4EBF = 2630278177317\uFF09\u3002"));

// ---- 四、ML 模型 ----
children.push(heading("\u56DB\u3001ML \u6A21\u578B\u8BAD\u7EC3\u4F53\u7CFB", HeadingLevel.HEADING_1));

children.push(heading("4.1 \u5F53\u524D\u6700\u4F18\u914D\u7F6E", HeadingLevel.HEADING_2));
children.push(para("\u6A21\u578B\u6587\u4EF6\uFF1Avar/models/autore_v2_best.pkl\uFF0C\u8BAD\u7EC3\u811A\u672C\uFF1Aneotrade3/ml/autore/train.py\uFF0C\u5173\u952E\u53C2\u6570\uFF1A"));
children.push(makeTable(
  ["\u53C2\u6570", "\u503C", "\u8BF4\u660E"],
  [
    ["N_ESTIMATORS", "300", "\u968F\u673A\u68EE\u6797\u6811\u7684\u6570\u91CF"],
    ["MAX_DEPTH", "20", "\u6700\u5927\u6DF1\u5EA6"],
    ["MIN_SAMPLES_LEAF", "8", "\u53F6\u8282\u70B9\u6700\u5C0F\u6837\u672C\u6570"],
    ["LOOKBACK_DAYS", "120", "\u56DE\u770B\u5929\u6570\uFF08\u7279\u5F81\u8BA1\u7B97\u7A97\u53E3\uFF09"],
    ["FORWARD_DAYS", "5", "\u524D\u77BB\u5929\u6570\uFF08\u9884\u6D4B\u76EE\u6807\uFF09"],
    ["THRESHOLD_UP", "1.5", "\u4E0A\u6DA8\u9608\u503C\uFF08%\uFF09"],
    ["THRESHOLD_DOWN", "-1.5", "\u4E0B\u8DCC\u9608\u503C\uFF08%\uFF09"],
    ["UNIVERSE_SIZE", "100", "\u6BCF\u65E5\u91C7\u6837\u80A1\u7968\u6570\uFF08\u6309\u6210\u4EA4\u989D\u6392\u5E8F\uFF09"],
    ["USE_MACD", "False", "MACD \u7279\u5F81\u5F00\u5173\uFF08\u5F53\u524D\u5173\u95ED\uFF09"],
    ["USE_BOLLINGER", "True", "\u5E03\u6797\u5E26\u7279\u5F81\u5F00\u5173"],
    ["USE_VOLATILITY_REGIME", "True", "\u6CE2\u52A8\u7387\u4F53\u5236\u7279\u5F81"],
    ["USE_MARKET_BREADTH", "True", "\u5E02\u573A\u6DA8\u8DCC\u6BD4\u7279\u5F81"],
    ["USE_FUNDAMENTAL", "False", "\u57FA\u672C\u9762\u7279\u5F81\uFF08\u5F53\u524D\u5173\u95ED\uFF09"],
    ["USE_MARKET_CAP_FILTER", "False", "\u5E02\u503C\u7B5B\u9009\uFF08\u5F53\u524D\u5173\u95ED\uFF09"],
    ["USE_SECTOR_WEIGHTING", "False", "\u677F\u5757\u52A0\u6743\u91C7\u6837\uFF08\u5F53\u524D\u5173\u95ED\uFF09"],
  ],
  [3000, 1200, 5160]
));

children.push(heading("4.2 \u7279\u5F81\u5217\u8868\u4E0E\u91CD\u8981\u6027", HeadingLevel.HEADING_2));
children.push(para("\u5F53\u524D\u542F\u7528\u7684\u7279\u5F81\uFF0813 \u4E2A\uFF09\uFF1A"));
children.push(makeTable(
  ["\u6392\u540D", "\u7279\u5F81\u540D", "\u91CD\u8981\u6027", "\u8BF4\u660E"],
  [
    ["1", "market_return_20d", "15.41%", "\u5E02\u573A 20 \u65E5\u6536\u76CA"],
    ["2", "volume_trend_5d", "11.87%", "\u6210\u4EA4\u91CF 5 \u65E5\u8D8B\u52BF"],
    ["3", "sector_return_5d", "11.76%", "\u677F\u5757 5 \u65E5\u6536\u76CA"],
    ["4", "market_volatility", "10.11%", "\u5E02\u573A\u6CE2\u52A8\u7387"],
    ["5", "volume_ratio", "7.19%", "\u91CF\u6BD4\uFF08\u4ECA\u65E5/\u5747\u91CF\uFF09"],
    ["6", "volatility_regime", "6.37%", "\u6CE2\u52A8\u7387\u4F53\u5236\uFF08\u9AD8/\u4E2D/\u4F4E\uFF09"],
    ["7", "market_return_5d", "6.29%", "\u5E02\u573A 5 \u65E5\u6536\u76CA"],
    ["8", "return_5d", "5.93%", "\u4E2A\u80A1 5 \u65E5\u6536\u76CA"],
    ["9", "volatility_20d", "5.77%", "20 \u65E5\u6CE2\u52A8\u7387"],
    ["10", "bollinger_position", "5.68%", "\u5E03\u6797\u5E26\u4F4D\u7F6E"],
    ["11", "return_20d", "-", "\u4E2A\u80A1 20 \u65E5\u6536\u76CA"],
    ["12", "return_60d", "-", "\u4E2A\u80A1 60 \u65E5\u6536\u76CA"],
    ["13", "market_breadth", "-", "\u5E02\u573A\u6DA8\u8DCC\u6BD4"],
  ],
  [800, 2800, 1200, 4560]
));

children.push(heading("4.3 \u5DF2\u5B9A\u4E49\u4F46\u5173\u95ED\u7684\u7279\u5F81", HeadingLevel.HEADING_2));
children.push(para("\u4EE5\u4E0B\u7279\u5F81\u5DF2\u5B9E\u73B0\u4F46\u5F53\u524D\u5173\u95ED\uFF08\u5B9E\u9A8C\u8BC1\u660E\u4F1A\u964D\u4F4E\u51C6\u786E\u7387\uFF09\uFF1A"));
children.push(bullet("RSI_14\uFF1A\u76F8\u5BF9\u5F3A\u5F31\u6307\u6807\uFF08\u79FB\u9664\u540E\u51C6\u786E\u7387\u4E0A\u5347\uFF09"));
children.push(bullet("MACD_histogram\uFF1AMACD \u67F1\uFF08\u5F53\u524D\u5173\u95ED\uFF09"));
children.push(bullet("pe_ratio / pb_ratio / roe\uFF1A\u57FA\u672C\u9762\u7279\u5F81\uFF08\u52A0\u5165\u540E\u51C6\u786E\u7387\u4ECE 76.67% \u964D\u81F3 61.61%\uFF09"));
children.push(bullet("revenue_growth / profit_growth / eps\uFF1A\u589E\u957F\u7C7B\u57FA\u672C\u9762\u7279\u5F81"));

// ---- 五、API 端点 ----
children.push(heading("\u4E94\u3001API \u7AEF\u70B9\u5B8C\u6574\u5217\u8868", HeadingLevel.HEADING_1));
children.push(para("\u6240\u6709 API \u5728 apps/api/main.py \u4E2D\u5B9E\u73B0\uFF0C\u4F7F\u7528 if/elif \u94FE\u5F0F\u8DEF\u7531\u5206\u53D1\u3002\u4EE5\u4E0B\u4E3A\u65B0\u589E\u7684 ML \u76F8\u5173\u7AEF\u70B9\uFF1A"));

children.push(heading("5.1 ML \u9884\u6D4B\u7AEF\u70B9", HeadingLevel.HEADING_2));
children.push(makeTable(
  ["\u7AEF\u70B9", "\u65B9\u6CD5", "\u53C2\u6570", "\u8BF4\u660E"],
  [
    ["/api/prediction/signals", "GET", "date, threshold(0.6), top_n(20)", "\u5F53\u65E5 ML \u9884\u6D4B\u4E70\u5356\u4FE1\u53F7"],
    ["/api/prediction/backtest", "GET", "\u65E0", "\u6700\u8FD1\u56DE\u6D4B\u7ED3\u679C\u6458\u8981"],
  ],
  [2800, 800, 2800, 2960]
));

children.push(heading("5.2 \u677F\u5757\u8F6E\u52A8\u7AEF\u70B9", HeadingLevel.HEADING_2));
children.push(makeTable(
  ["\u7AEF\u70B9", "\u65B9\u6CD5", "\u53C2\u6570", "\u8BF4\u660E"],
  [
    ["/api/sector-rotation/ranking", "GET", "date, top_n(10)", "71 \u4E2A\u677F\u5757\u5F3A\u5EA6\u6392\u540D"],
    ["/api/sector-rotation/signals", "GET", "date", "\u5468\u7EA7\u522B\u4EA4\u6613\u4FE1\u53F7"],
  ],
  [2800, 800, 2800, 2960]
));

children.push(heading("5.3 \u539F\u6709\u7CFB\u7EDF\u7AEF\u70B9\uFF08\u90E8\u5206\uFF09", HeadingLevel.HEADING_2));
children.push(makeTable(
  ["\u7AEF\u70B9", "\u8BF4\u660E"],
  [
    ["/healthz", "\u5065\u5EB7\u68C0\u67E5"],
    ["/api/trading-day?date=", "\u4EA4\u6613\u65E5\u67E5\u8BE2"],
    ["/api/sector-rotation?date=", "\u539F\u6709\u677F\u5757\u8F6E\u52A8\uFF08\u7CFB\u7EDF\u5185\u7F6E\uFF09"],
    ["/api/signals?codes=&date=", "\u4EA4\u6613\u4FE1\u53F7\uFF08\u7CFB\u7EDF\u5185\u7F6E\uFF09"],
    ["/api/backtest?codes=&date=", "\u56DE\u6D4B\uFF08\u7CFB\u7EDF\u5185\u7F6E\uFF09"],
    ["/api/stocks/lookup?code=", "\u80A1\u7968\u67E5\u8BE2"],
    ["/api/data-control/sync-daily-prices", "POST \u540C\u6B65\u884C\u60C5"],
    ["/api/data-control/update-daily-prices/tencent", "POST \u817E\u8BAF\u6570\u636E\u66F4\u65B0"],
    ["/api/screeners/run", "POST \u8FD0\u884C\u7B5B\u9009\u5668"],
    ["/api/orchestration/run", "POST \u8FD0\u884C\u7F16\u6392"],
  ],
  [4500, 4860]
));

children.push(para("\u5B8C\u6574\u7AEF\u70B9\u5217\u8868\u8BF7\u53C2\u89C1 apps/api/main.py \u4E2D\u7684 dispatch() \u548C dispatch_post() \u65B9\u6CD5\uFF08\u7EA6 6494 \u884C\u548C 7408 \u884C\uFF09\u3002", { run: { color: "666666", size: 19 } }));

// ---- 六、回测结果 ----
children.push(heading("\u516D\u3001\u56DE\u6D4B\u7ED3\u679C\u4E0E\u7B56\u7565\u5BF9\u6BD4", HeadingLevel.HEADING_1));
children.push(para("\u56DE\u6D4B\u533A\u95F4\uFF1A2026-02-21 ~ 2026-05-22\uFF0C\u521D\u59CB\u8D44\u91D1 100 \u4E07\u5143\u3002"));

children.push(heading("6.1 \u7B56\u7565\u5BF9\u6BD4", HeadingLevel.HEADING_2));
children.push(makeTable(
  ["\u6307\u6807", "ML \u9884\u6D4B\u7B56\u7565", "\u677F\u5757\u8F6E\u52A8\u7B56\u7565"],
  [
    ["\u603B\u6536\u76CA\u7387", "+7.74%", "-44.91%"],
    ["\u5E74\u5316\u6536\u76CA\u7387", "+36.74%", "-91.82%"],
    ["\u6700\u5927\u56DE\u64A4", "5.16%", "28.90%"],
    ["\u80DC\u7387", "77.19%", "34.62%"],
    ["\u76C8\u4E8F\u6BD4", "2.70", "-"],
    ["\u4EA4\u6613\u6B21\u6570", "57", "26"],
    ["\u5E73\u5747\u6536\u76CA", "+5.91%", "-1.83%"],
    ["\u7ED3\u8BBA", "\u2705 \u63A8\u8350\u4F7F\u7528", "\u274C \u4EC5\u4F5C\u53C2\u8003"],
  ],
  [2500, 3430, 3430]
));

children.push(heading("6.2 ML \u7B56\u7565\u8BE6\u60C5", HeadingLevel.HEADING_2));
children.push(para("\u7B56\u7565\u903B\u8F91\uFF1A\u6BCF\u4E2A\u4EA4\u6613\u65E5\u5BF9 Top 100 \u80A1\u7968\u505A\u9884\u6D4B\uFF0C\u6A21\u578B\u7ED9\u51FA prob >= 0.6 \u7684\u4E70\u5165\u4FE1\u53F7\u7EB3\u5165\u6301\u4ED3\uFF0C\u6301\u6709 5 \u5929\u540E\u5356\u51FA\u3002\u7B49\u6743\u5206\u914D\u8D44\u91D1\uFF0C\u6700\u591A\u6301\u6709 10 \u53EA\u3002"));
children.push(para("\u56DE\u6D4B\u7ED3\u679C\u6587\u4EF6\uFF1Avar/backtest_results/backtest_2026-02-21_2026-05-22.json"));

children.push(heading("6.3 \u677F\u5757\u8F6E\u52A8\u7B56\u7565\u8BE6\u60C5", HeadingLevel.HEADING_2));
children.push(para("\u7B56\u7565\u903B\u8F91\uFF1A\u6BCF\u5468\u8BA1\u7B97 71 \u4E2A\u677F\u5757\u7684\u7EFC\u5408\u8BC4\u5206\uFF08\u52A8\u91CF+\u91CF\u6BD4+\u4E0A\u6DA8\u6BD4+\u9886\u6DA8\u80A1\u5F3A\u5EA6\uFF09\uFF0C\u9009 Top 3 \u5F3A\u52BF\u677F\u5757\u7684\u9886\u6DA8\u80A1\u3002"));
children.push(para("\u5931\u8D25\u539F\u56E0\uFF1A\u8FFD\u6DA8\u6740\u8DCC\u3001\u9886\u6DA8\u80A1\u6CE2\u52A8\u5927\u3001\u7F3A\u4E4F\u98CE\u63A7\u3002\u5EFA\u8BAE\u4EC5\u4F5C\u4E3A\u5E02\u573A\u98CE\u683C\u53C2\u8003\uFF0C\u4E0D\u76F4\u63A5\u4F5C\u4E3A\u4EA4\u6613\u4FE1\u53F7\u3002"));
children.push(para("\u56DE\u6D4B\u7ED3\u679C\u6587\u4EF6\uFF1Avar/backtest_results/sector_rotation_2026-02-21_2026-05-22.json"));

// ---- 七、实验记录 ----
children.push(heading("\u4E03\u3001\u5B9E\u9A8C\u8BB0\u5F55\u4E0E\u5173\u952E\u53D1\u73B0", HeadingLevel.HEADING_1));

children.push(heading("7.1 \u6A21\u578B\u4F18\u5316\u5386\u7A0B", HeadingLevel.HEADING_2));
children.push(para("\u4ECE\u57FA\u7EBF 63.50% \u5230\u6700\u4F18 80.39%\uFF0C\u5171\u7ECF\u8FC7 5 \u6B21\u5173\u952E\u5B9E\u9A8C\uFF08\u8BE6\u89C1 neotrade3/ml/autore/SUCCESS.md\uFF09\uFF1A"));
children.push(makeTable(
  ["\u5B9E\u9A8C", "\u53D8\u66F4", "\u51C6\u786E\u7387", "\u63D0\u5347"],
  [
    ["#1 \u589E\u52A0\u6811\u6DF1\u5EA6", "MAX_DEPTH: 10 \u2192 15", "71.83%", "+8.33%"],
    ["#2 \u589E\u5927\u53F6\u8282\u70B9", "MIN_SAMPLES_LEAF: 1 \u2192 8", "73.53%", "+1.70%"],
    ["#3 \u6269\u5927\u9608\u503C", "THRESHOLD: +-1% \u2192 +-1.5%", "73.58%", "+0.05%"],
    ["#4 \u79FB\u9664 RSI", "USE_RSI: True \u2192 False", "74.07%", "+0.49%"],
    ["#5 \u7EC4\u5408\u4F18\u5316", "300\u6811+\u6DF1\u5EA620", "80.39%", "+6.32%"],
  ],
  [2000, 3500, 1500, 2360]
));

children.push(heading("7.2 \u5931\u8D25\u5B9E\u9A8C\uFF08\u91CD\u8981\u8E29\u5751\uFF09", HeadingLevel.HEADING_2));
children.push(para("\u4EE5\u4E0B\u5B9E\u9A8C\u5747\u5BFC\u81F4\u51C6\u786E\u7387\u4E0B\u964D\uFF0C\u8BE6\u89C1 neotrade3/ml/autore/FAILED.md\uFF1A"));
children.push(makeTable(
  ["\u5B9E\u9A8C", "\u7ED3\u679C", "\u539F\u56E0\u5206\u6790"],
  [
    ["Universe \u6269\u5927\u5230 500", "58.97%\uFF08-21%\uFF09", "\u5C0F\u76D8\u80A1\u566A\u58F0\u5927\uFF0C\u7279\u5F81\u4E0D\u9002\u7528"],
    ["\u5E02\u503C\u7B5B\u9009 200-400\u4EBF", "59.87%\uFF08-20%\uFF09", "\u4E2D\u76D8\u80A1\u6CE2\u52A8\u7279\u5F81\u4E0D\u540C"],
    ["\u5E02\u503C\u7B5B\u9009 100-500\u4EBF", "52.37%\uFF08-28%\uFF09", "\u66F4\u5BBD\u8303\u56F4\u66F4\u5DEE"],
    ["\u52A0\u5165\u57FA\u672C\u9762\u7279\u5F81", "61.61%\uFF08-15%\uFF09", "PE/ROE \u6570\u636E\u8D28\u91CF\u4E0D\u8DB3"],
    ["\u677F\u5757\u52A0\u6743\u91C7\u6837", "58.97%\uFF08-21%\uFF09", "\u52A0\u6743\u5F15\u5165\u504F\u5DEE"],
    ["N_ESTIMATORS=500", "\u65E0\u660E\u663E\u63D0\u5347", "\u8FC7\u62DF\u5408\u98CE\u9669\u589E\u52A0"],
    ["LOOKBACK_DAYS=90/150/180", "\u65E0\u660E\u663E\u63D0\u5347", "120 \u5929\u662F\u6700\u4F18\u7A97\u53E3"],
  ],
  [2800, 2000, 4560]
));

children.push(heading("7.3 \u5173\u952E\u7ED3\u8BBA", HeadingLevel.HEADING_2));
startNumGroup();
children.push(num("\u6A21\u578B\u5BF9\u5927\u76D8\u80A1\uFF08Top 100 \u6210\u4EA4\u989D\uFF09\u6548\u679C\u6700\u597D\uFF0C\u6269\u5927 Universe \u4F1A\u663E\u8457\u964D\u4F4E\u51C6\u786E\u7387"));
children.push(num("\u57FA\u672C\u9762\u7279\u5F81\u5728\u5F53\u524D\u6570\u636E\u8D28\u91CF\u4E0B\u65E0\u6548\uFF0C\u7EAF\u6280\u672F\u9762\u66F4\u4F18"));
children.push(num("\u677F\u5757\u8F6E\u52A8\u7B56\u7565\u5728\u56DE\u6D4B\u4E2D\u8868\u73B0\u6781\u5DEE\uFF0C\u4EC5\u9002\u5408\u4F5C\u4E3A\u8F85\u52A9\u53C2\u8003"));
children.push(num("LOOKBACK_DAYS=120 \u662F\u6700\u4F18\u56DE\u770B\u7A97\u53E3\uFF0C\u8FC7\u77ED\u6216\u8FC7\u957F\u90FD\u4F1A\u964D\u4F4E\u6548\u679C"));
children.push(num("\u7279\u5F81\u91CD\u8981\u6027\uFF1A\u5E02\u573A\u7EA7\u7279\u5F81\uFF08market_return_20d\uFF09\u6700\u91CD\u8981\uFF0C\u5360 15.41%"));

// ---- 八、已知问题 ----
children.push(heading("\u516B\u3001\u5DF2\u77E5\u95EE\u9898\u4E0E\u98CE\u9669", HeadingLevel.HEADING_1));

children.push(heading("8.1 \u67B6\u6784\u5C42\u9762", HeadingLevel.HEADING_2));
startNumGroup();
children.push(num("apps/api/main.py \u5355\u6587\u4EF6 8400+ \u884C\uFF0C\u6240\u6709\u8DEF\u7531\u901A\u8FC7 if/elif \u94FE\u5B9E\u73B0\uFF0C\u7EF4\u62A4\u6210\u672C\u9AD8\u3002\u65B0\u589E\u7AEF\u70B9\u9700\u5728 dispatch() \u65B9\u6CD5\u7684 fallback \u4E4B\u524D\u63D2\u5165\u3002"));
children.push(num("\u6CA1\u6709\u4F7F\u7528 Web \u6846\u67B6\uFF08FastAPI/Flask\uFF09\uFF0C\u6CA1\u6709\u81EA\u52A8\u6587\u6863\u3001\u6CA1\u6709\u7C7B\u578B\u68C0\u67E5\u3002"));
children.push(num("\u6CA1\u6709 Dockerfile\u3001docker-compose.yml\u3001Makefile \u7B49\u5DE5\u7A0B\u5316\u914D\u7F6E\u3002"));
children.push(num("pyproject.toml \u4E2D\u6CA1\u6709\u58F0\u660E\u8FD0\u884C\u65F6\u4F9D\u8D56\uFF08numpy, scikit-learn \u7B49\uFF09\uFF0C\u4EC5\u6709 dev \u4F9D\u8D56\u3002"));

children.push(heading("8.2 \u6570\u636E\u5C42\u9762", HeadingLevel.HEADING_2));
startNumGroup();
children.push(num("\u57FA\u672C\u9762\u6570\u636E\uFF08PE/ROE/PB\uFF09\u8D28\u91CF\u4E0D\u8DB3\uFF0C\u5F88\u591A\u80A1\u7968\u7F3A\u5C11\u6570\u636E\uFF0C\u5BFC\u81F4\u57FA\u672C\u9762\u7279\u5F81\u65E0\u6548\u3002"));
children.push(num("\u65E5\u7EBF\u6570\u636E\u4E2D\u6CA1\u6709 change_pct \u5B57\u6BB5\uFF0C\u5B9E\u9645\u5B57\u6BB5\u540D\u4E3A pct_change\uFF0C\u6CE8\u610F\u533A\u5206\u3002"));
children.push(num("\u5E02\u503C\u5355\u4F4D\u4E3A\u5143\uFF08\u4E0D\u662F\u4EBF\u5143\uFF09\uFF0C\u67E5\u8BE2\u65F6\u9700\u8981\u8F6C\u6362\u3002"));
children.push(num("\u677F\u5757\u4EE3\u7801\u4E3A\u7533\u4E07\u884C\u4E1A\u7F16\u7801\uFF08\u5982 C39=\u8BA1\u7B97\u673A\uFF09\uFF0C\u4E0D\u662F\u4E2D\u6587\u540D\u79F0\u3002"));

children.push(heading("8.3 \u6A21\u578B\u5C42\u9762", HeadingLevel.HEADING_2));
startNumGroup();
children.push(num("\u6A21\u578B\u6709\u968F\u673A\u6027\uFF1A\u591A\u6B21\u8BAD\u7EC3\u7ED3\u679C\u5728 76-80% \u4E4B\u95F4\u6CE2\u52A8\uFF0C\u9700\u8981\u56FA\u5B9A\u968F\u673A\u79CD\u5B50\u624D\u80FD\u590D\u73B0\u3002"));
children.push(num("\u6A21\u578B\u4FDD\u5B58\u4F7F\u7528 joblib.dump() \uFF0C\u52A0\u8F7D\u65F6\u9700\u8981 scikit-learn \u7248\u672C\u517C\u5BB9\u3002"));
children.push(num("\u6A21\u578B\u6CA1\u6709\u7248\u672C\u7BA1\u7406\uFF0C\u5386\u53F2\u6A21\u578B\u5DF2\u5F52\u6863\u5230 var/models/archive/\u3002"));

// ---- 九、后续建议 ----
children.push(heading("\u4E5D\u3001\u540E\u7EED\u4F18\u5316\u5EFA\u8BAE", HeadingLevel.HEADING_1));

children.push(heading("9.1 \u9AD8\u4F18\u5148\u7EA7", HeadingLevel.HEADING_2));
startNumGroup();
children.push(num("\u524D\u7AEF\u96C6\u6210\uFF1A\u5C06 ML \u9884\u6D4B\u548C\u677F\u5757\u8F6E\u52A8\u7AEF\u70B9\u96C6\u6210\u5230 Dashboard\uFF0C\u5C55\u793A\u4E70\u5356\u4FE1\u53F7\u548C\u677F\u5757\u6392\u540D\u3002"));
children.push(num("\u56FA\u5B9A\u968F\u673A\u79CD\u5B50\uFF1A\u5728 train.py \u4E2D\u8BBE\u7F6E np.random.seed() \u786E\u4FDD\u7ED3\u679C\u53EF\u590D\u73B0\u3002"));
children.push(num("\u6A21\u578B\u7248\u672C\u7BA1\u7406\uFF1A\u6A21\u578B\u6587\u4EF6\u547D\u540D\u52A0\u5165\u65E5\u671F\u548C\u51C6\u786E\u7387\uFF0C\u5982 autore_v2_8039_20260526.pkl\u3002"));

children.push(heading("9.2 \u4E2D\u4F18\u5148\u7EA7", HeadingLevel.HEADING_2));
startNumGroup();
children.push(num("\u6539\u9020 API \u67B6\u6784\uFF1A\u5C06 apps/api/main.py \u62C6\u5206\u4E3A\u591A\u4E2A\u6A21\u5757\uFF0C\u6216\u8FC1\u79FB\u5230 FastAPI\u3002"));
children.push(num("\u6DFB\u52A0\u81EA\u52A8\u91CD\u8BAD\u7EC3\uFF1A\u76D1\u63A7\u6A21\u578B\u6027\u80FD\u8870\u51CF\uFF0C\u81EA\u52A8\u89E6\u53D1\u91CD\u8BAD\u7EC3\u3002"));
children.push(num("\u6539\u5584\u57FA\u672C\u9762\u6570\u636E\u8D28\u91CF\uFF1A\u901A\u8FC7 akshare \u6216\u5176\u4ED6\u6570\u636E\u6E90\u8865\u5145 PE/ROE \u6570\u636E\u3002"));
children.push(num("\u6DFB\u52A0\u6B62\u635F\u673A\u5236\uFF1A\u5728\u677F\u5757\u8F6E\u52A8\u7B56\u7565\u4E2D\u52A0\u5165\u6B62\u635F\uFF0C\u53EF\u80FD\u6539\u5584\u56DE\u6D4B\u8868\u73B0\u3002"));

children.push(heading("9.3 \u4F4E\u4F18\u5148\u7EA7", HeadingLevel.HEADING_2));
startNumGroup();
children.push(num("\u5BB9\u5668\u5316\uFF1A\u6DFB\u52A0 Dockerfile \u548C docker-compose.yml\u3002"));
children.push(num("\u6D4B\u8BD5\u8986\u76D6\uFF1A\u4E3A\u65B0\u589E\u7AEF\u70B9\u6DFB\u52A0\u5355\u5143\u6D4B\u8BD5\u3002"));
children.push(num("pyproject.toml \u8865\u5168\u4F9D\u8D56\u58F0\u660E\u3002"));

// ---- 十、前端 Dashboard ----
children.push(heading("\u5341\u3001\u524D\u7AEF Dashboard \u6838\u5FC3\u8981\u6C42\u4E0E\u903B\u8F91", HeadingLevel.HEADING_1));

children.push(heading("10.1 \u6280\u672F\u67B6\u6784", HeadingLevel.HEADING_2));
children.push(para("\u524D\u7AEF\u91C7\u7528\u7EAF\u539F\u751F\u6280\u672F\u6808\uFF0C\u65E0\u4EFB\u4F55\u524D\u7AEF\u6846\u67B6\uFF08React/Vue/Angular\uFF09\uFF0C\u65E0\u6A21\u677F\u5F15\u64CE\uFF1A"));
children.push(makeTable(
  ["\u7EC4\u4EF6", "\u6280\u672F", "\u89C4\u6A21"],
  [
    ["HTML", "Python f-string \u5185\u8054\u751F\u6210", "main.py \u7B2C 54-483 \u884C"],
    ["CSS", "\u539F\u751F CSS + CSS \u53D8\u91CF\u7CFB\u7EDF", "dashboard.css\uFF0C1419 \u884C"],
    ["JavaScript", "\u539F\u751F JS + Fetch API", "dashboard.js\uFF0C4560 \u884C"],
    ["HTTP \u670D\u52A1", "Python http.server", "\u7AEF\u53E3 18031"],
    ["\u6570\u636E\u6765\u6E90", "\u540E\u7AEF API\uFF08\u7AEF\u53E3 18030\uFF09", "\u524D\u7AEF\u4E0D\u76F4\u63A5\u8BBF\u95EE\u6570\u636E\u5E93"],
  ],
  [2000, 3800, 3560]
));

children.push(heading("10.2 \u9875\u9762\u7ED3\u6784\u4E0E Section \u5217\u8868", HeadingLevel.HEADING_2));
children.push(para("Dashboard \u91C7\u7528\u4FA7\u8FB9\u680F + \u5185\u5BB9\u533A\u5E03\u5C40\uFF0C\u4FA7\u8FB9\u680F 240px\u3001sticky \u5B9A\u4F4D\u3002Focus \u6A21\u5F0F\u4E0B\u901A\u8FC7 hash \u8DEF\u7531\u5207\u6362\u663E\u793A\u5BF9\u5E94 section\u3002\u5B8C\u6574 section \u5217\u8868\uFF1A"));
children.push(makeTable(
  ["Section ID", "\u540D\u79F0", "\u8BF4\u660E", "\u72B6\u6001"],
  [
    ["section-overview", "\u4ECA\u65E5\u5206\u6790\u603B\u89C8", "\u5E02\u573A\u9636\u6BB5\u3001\u5019\u9009\u3001\u4FE1\u53F7\u3001\u677F\u5757\u3001\u7B5B\u9009\u5668\u547D\u4E2D", "\u5DF2\u5B8C\u6210"],
    ["section-daily-workbench", "\u56E2\u961F\u64CD\u4F5C", "\u5DE5\u4F5C\u53F0\u5019\u9009\u8868\u683C\u3001\u4E00\u952E\u64CD\u4F5C", "\u5DF2\u5B8C\u6210"],
    ["section-data-control", "\u6570\u636E\u4E3B\u94FE", "\u884C\u60C5\u540C\u6B65\u3001\u6570\u636E\u72B6\u6001\u6307\u793A\u5668", "\u5DF2\u5B8C\u6210"],
    ["section-orchestration", "\u6BCF\u65E5\u4EFB\u52A1\u8FD0\u884C", "\u7F16\u6392\u5668\u8FD0\u884C\u8BB0\u5F55", "\u5DF2\u5B8C\u6210"],
    ["section-screeners", "\u7B5B\u9009\u5668", "\u7B5B\u9009\u5668\u8FD0\u884C\u9762\u677F\u3001\u53C2\u6570\u914D\u7F6E\u5F39\u7A97", "\u5DF2\u5B8C\u6210"],
    ["section-cup-handle", "\u676F\u67C4\u5F62\u6001", "\u5B9E\u9A8C\u5BA4\u529F\u80FD", "\u5DF2\u5B8C\u6210"],
    ["section-five-flags", "\u8001\u9E2D\u5934\u4E94\u56FE", "\u5B9E\u9A8C\u5BA4\u529F\u80FD", "\u5DF2\u5B8C\u6210"],
    ["section-quant", "\u91CF\u5316\u4EA4\u6613", "\u56E0\u5B50\u77E9\u9635\u3001\u5019\u9009\u77E9\u9635\u3001\u4E2A\u80A1\u67E5\u8BE2", "\u5DF2\u5B8C\u6210"],
    ["section-strategy-pools", "\u7B56\u7565\u6C60\u7BA1\u7406", "\u624B\u5DE5\u76D1\u63A7\u6C60\u3001CSV \u4E0A\u4F20", "\u5DF2\u5B8C\u6210"],
    ["section-stock", "\u5355\u6807\u7684\u89E3\u91CA", "\u4E2A\u80A1\u68C0\u67E5\u3001\u589E\u5F3A\u4FE1\u606F\uFF08\u677F\u5757/\u5206\u5C42/RPS\uFF09", "\u5DF2\u5B8C\u6210"],
    ["section-issue-center", "\u95EE\u9898\u6C60", "\u95EE\u9898\u5217\u8868\u3001\u544A\u8B66", "\u5DF2\u5B8C\u6210"],
    ["section-roadmap", "\u8DEF\u7EBF\u56FE", "\u9879\u76EE\u89C4\u5212\uFF08dev-only\uFF09", "\u5DF2\u5B8C\u6210"],
    ["section-management", "\u7CFB\u7EDF\u8BBE\u7F6E", "API Key\u3001\u5F00\u53D1\u8005\u6A21\u5F0F\u3001V2 \u6570\u636E\u6E90", "\u5DF2\u5B8C\u6210"],
    ["section-diff", "\u5BF9\u7167\u4E0E\u53D8\u5316", "\u6570\u636E\u53D8\u5316\u5BF9\u6BD4", "\u5DF2\u5B8C\u6210"],
    ["section-learning", "\u5B66\u4E60\u95ED\u73AF", "\u5B66\u4E60\u6A21\u5757\uFF08dev-only\uFF09", "\u5DF2\u5B8C\u6210"],
    ["section-migration", "\u8FC1\u79FB\u53F0\u8D26", "\u7279\u6027\u6620\u5C04\u8986\u76D6\u7387\uFF08dev-only\uFF09", "\u5DF2\u5B8C\u6210"],
    ["section-config-contracts", "\u914D\u7F6E\u5951\u7EA6", "\u914D\u7F6E\u5951\u7EA6\u67E5\u770B\uFF08dev-only\uFF09", "\u5DF2\u5B8C\u6210"],
    ["section-labs", "\u5B9E\u9A8C\u5BA4", "\u5B9E\u9A8C\u5BA4\u8FD0\u884C\u8BB0\u5F55", "\u5DF2\u5B8C\u6210"],
  ],
  [2200, 2000, 3800, 1360]
));

children.push(heading("10.3 \u5F85\u96C6\u6210\u7684 ML \u65B0\u7AEF\u70B9", HeadingLevel.HEADING_2));
children.push(para("\u4EE5\u4E0B\u65B0\u589E\u7684 API \u7AEF\u70B9\u9700\u8981\u5728 Dashboard \u524D\u7AEF\u4E2D\u5C55\u793A\uFF0C\u76EE\u524D\u5C1A\u672A\u96C6\u6210\uFF1A"));
children.push(makeTable(
  ["API \u7AEF\u70B9", "\u5EFA\u8BAE\u5C55\u793A\u4F4D\u7F6E", "\u5C55\u793A\u5185\u5BB9", "\u5EFA\u8BAE Section"],
  [
    ["/api/prediction/signals", "\u603B\u89C8\u5361\u7247 + \u72EC\u7ACB Section", "ML \u4E70\u5356\u4FE1\u53F7\u5217\u8868\uFF08\u80A1\u7968\u4EE3\u7801/\u540D\u79F0/\u4FE1\u53F7/\u7F6E\u4FE1\u5EA6\uFF09", "\u65B0\u5EFA section-ml-prediction"],
    ["/api/prediction/backtest", "\u603B\u89C8\u5361\u7247 + \u56DE\u6D4B\u8BE6\u60C5", "\u56DE\u6D4B\u6307\u6807\uFF08\u6536\u76CA\u7387/\u80DC\u7387/\u56DE\u64A4\uFF09+\u8FD1\u671F\u4EA4\u6613\u8BB0\u5F55", "\u65B0\u5EFA section-ml-backtest"],
    ["/api/sector-rotation/ranking", "\u603B\u89C8\u5361\u7247 + \u677F\u5757\u6392\u540D\u8868", "71 \u4E2A\u677F\u5757\u7684\u7EFC\u5408\u8BC4\u5206\u3001\u52A8\u91CF\u3001\u91CF\u6BD4\u3001\u4E0A\u6DA8\u6BD4", "\u5DF2\u6709 section-overview \u6269\u5C55"],
    ["/api/sector-rotation/signals", "\u4EA4\u6613\u4FE1\u53F7\u8868", "\u5F3A\u52BF\u677F\u5757 Top3 + \u9886\u6DA8\u80A1\u4E70\u5165\u4FE1\u53F7\uFF08\u7F6E\u4FE1\u5EA6/\u539F\u56E0\uFF09", "\u65B0\u5EFA section-sector-signals"],
  ],
  [2200, 1800, 3200, 2160]
));

children.push(heading("10.4 \u96C6\u6210\u65B9\u6848\u4E0E\u5B9E\u73B0\u6B65\u9AA4", HeadingLevel.HEADING_2));
children.push(para("\u96C6\u6210\u65B0\u7AEF\u70B9\u9700\u8981\u4FEE\u6539\u4E09\u4E2A\u6587\u4EF6\uFF0C\u6309\u4EE5\u4E0B\u987A\u5E8F\u64CD\u4F5C\uFF1A"));

children.push(boldPara("\u6B65\u9AA4 1\uFF1A\u5728 main.py \u4E2D\u6DFB\u52A0 HTML Section \u9AA8\u67B6"));
children.push(para("\u5728 apps/dashboard/main.py \u7684 render_index() \u65B9\u6CD5\u4E2D\uFF0C\u5728\u73B0\u6709 section \u4E4B\u540E\uFF08\u7EA6\u7B2C 483 \u884C\u4E4B\u524D\uFF09\u6DFB\u52A0\u65B0\u7684 section HTML\u3002\u53C2\u8003\u73B0\u6709 section \u7684\u5199\u6CD5\uFF0C\u4F7F\u7528 f-string \u751F\u6210\u3002\u9700\u8981\u6DFB\u52A0\u7684 section\uFF1A"));
children.push(bullet("section-ml-prediction\uFF1AML \u9884\u6D4B\u4FE1\u53F7\u5C55\u793A\u533A\u57DF"));
children.push(bullet("section-ml-backtest\uFF1A\u56DE\u6D4B\u7ED3\u679C\u5C55\u793A\u533A\u57DF"));
children.push(bullet("section-sector-signals\uFF1A\u677F\u5757\u8F6E\u52A8\u4FE1\u53F7\u5C55\u793A\u533A\u57DF"));

children.push(boldPara("\u6B65\u9AA4 2\uFF1A\u5728 dashboard.js \u4E2D\u6DFB\u52A0 API \u8C03\u7528\u548C\u6E32\u67D3\u903B\u8F91"));
children.push(para("\u5728 dashboard.js \u7684 loadDashboard() \u51FD\u6570\uFF08\u7B2C 3530 \u884C\uFF09\u4E2D\uFF0C\u6DFB\u52A0\u5BF9\u65B0\u7AEF\u70B9\u7684 fetch \u8C03\u7528\u3002\u7136\u540E\u6DFB\u52A0\u5BF9\u5E94\u7684\u6E32\u67D3\u51FD\u6570\uFF1A"));
children.push(bullet("renderMLPrediction() \u2014\u2014 \u89E3\u6790 /api/prediction/signals \u8FD4\u56DE\u7684 JSON\uFF0C\u6E32\u67D3\u4E70\u5165/\u5356\u51FA\u4FE1\u53F7\u8868\u683C"));
children.push(bullet("renderMLBacktest() \u2014\u2014 \u89E3\u6790 /api/prediction/backtest \u8FD4\u56DE\u7684 JSON\uFF0C\u6E32\u67D3\u56DE\u6D4B\u6307\u6807\u5361\u7247\u548C\u4EA4\u6613\u8BB0\u5F55"));
children.push(bullet("renderSectorSignals() \u2014\u2014 \u89E3\u6790 /api/sector-rotation/signals \u8FD4\u56DE\u7684 JSON\uFF0C\u6E32\u67D3\u5F3A\u52BF\u677F\u5757\u548C\u4E70\u5165\u4FE1\u53F7"));
children.push(para("\u53C2\u8003\u73B0\u6709\u6E32\u67D3\u51FD\u6570\u7684\u5199\u6CD5\uFF08\u5982 renderOverviewSummary()\u3001renderSectorDetail()\uFF09\uFF0C\u4F7F\u7528\u76F8\u540C\u7684\u98CE\u683C\u548C CSS \u7C7B\u540D\u3002"));

children.push(boldPara("\u6B65\u9AA4 3\uFF1A\u5728 dashboard.css \u4E2D\u6DFB\u52A0\u6837\u5F0F\uFF08\u5982\u9700\uFF09"));
children.push(para("\u5982\u679C\u65B0 section \u9700\u8981\u72EC\u7279\u7684\u6837\u5F0F\uFF0C\u5728 dashboard.css \u672B\u5C3E\u6DFB\u52A0\u3002\u5EFA\u8BAE\u590D\u7528\u73B0\u6709\u7EC4\u4EF6\u7C7B\uFF1A"));
children.push(bullet(".metric-card \u2014\u2014 \u6307\u6807\u5361\u7247\uFF08\u7528\u4E8E\u56DE\u6D4B\u6307\u6807\u5C55\u793A\uFF09"));
children.push(bullet(".table \u2014\u2014 \u6570\u636E\u8868\u683C\uFF08\u7528\u4E8E\u4FE1\u53F7\u5217\u8868\uFF09"));
children.push(bullet(".pill.ok / .pill.bad \u2014\u2014 \u72B6\u6001\u6807\u7B7E\uFF08\u7528\u4E8E\u4E70\u5165/\u5356\u51FA\u6807\u8BB0\uFF09"));
children.push(bullet(".sector-card \u2014\u2014 \u677F\u5757\u5361\u7247\uFF08\u7528\u4E8E\u5F3A\u52BF\u677F\u5757\u5C55\u793A\uFF09"));

children.push(heading("10.5 \u524D\u7AEF\u4EA4\u4E92\u4E0E\u72B6\u6001\u7BA1\u7406", HeadingLevel.HEADING_2));
children.push(para("\u524D\u7AEF\u7684\u6838\u5FC3\u4EA4\u4E92\u903B\u8F91\uFF1A"));
children.push(makeTable(
  ["\u529F\u80FD", "\u5B9E\u73B0\u65B9\u5F0F", "\u5173\u952E\u53D8\u91CF"],
  [
    ["Focus \u6A21\u5F0F", "hash \u8DEF\u7531\u5207\u6362 section", "location.hash \u6620\u5C04 section ID"],
    ["\u65E5\u671F\u5207\u6362", "URL \u53C2\u6570 date=YYYY-MM-DD", "effectiveDate \u5168\u5C40\u53D8\u91CF"],
    ["\u6570\u636E\u6E90\u5207\u6362", "URL \u53C2\u6570 source=live/stored", "sourceMode \u5168\u5C40\u53D8\u91CF"],
    ["API Key \u7BA1\u7406", "localStorage \u6301\u4E45\u5316", "apiKey = localStorage.neo_api_key"],
    ["\u5F00\u53D1\u8005\u6A21\u5F0F", "URL \u53C2\u6570 dev=1", "body.dev-mode \u63A7\u5236 .dev-only \u663E\u793A"],
    ["\u4E3B\u9898\u5207\u6362", "URL \u53C2\u6570 theme=editorial/industrial", "body.theme-industrial \u63A7\u5236\u6697\u8272\u4E3B\u9898"],
    ["\u7B5B\u9009\u5668\u914D\u7F6E", "\u5F39\u7A97 JSON \u7F16\u8F91 + \u8868\u5355\u7F16\u8F91", "screener-config-modal"],
    ["\u624B\u5DE5\u6C60\u4E0A\u4F20", "CSV/TXT \u6587\u4EF6\u89E3\u6790 6 \u4F4D\u4EE3\u7801", "POST /api/pools/manual/snapshot"],
    ["\u5B9E\u65F6\u65F6\u949F", "setInterval \u6BCF\u79D2\u66F4\u65B0", "\u5BF9\u5E94 DOM \u5143\u7D20"],
  ],
  [1800, 3200, 4360]
));

children.push(heading("10.6 \u6837\u5F0F\u7CFB\u7EDF\u8BF4\u660E", HeadingLevel.HEADING_2));
children.push(para("CSS \u91C7\u7528\u53D8\u91CF\u7CFB\u7EDF\uFF0C\u901A\u8FC7 :root \u5B9A\u4E49\u5168\u5C40\u53D8\u91CF\uFF1A"));
children.push(makeTable(
  ["\u53D8\u91CF", "\u9ED8\u8BA4\u503C\uFF08Editorial\uFF09", "\u6697\u8272\u4E3B\u9898\u503C\uFF08Industrial\uFF09", "\u7528\u9014"],
  [
    ["--bg", "#fbfaf7", "#0b0f14", "\u9875\u9762\u80CC\u666F"],
    ["--paper", "#ffffff", "#151b23", "\u5361\u7247/\u5185\u5BB9\u533A\u80CC\u666F"],
    ["--ink", "#1a1a1a", "#e2e8f0", "\u4E3B\u6587\u5B57\u989C\u8272"],
    ["--muted", "#6b7280", "#64748b", "\u6B21\u8981\u6587\u5B57\u989C\u8272"],
    ["--accent", "#1d4ed8", "#22c55e", "\u5F3A\u8C03\u8272"],
    ["--danger", "#dc2626", "#ef4444", "\u5371\u9669/\u8B66\u544A\u8272"],
    ["--border", "#e5e7eb", "#1e293b", "\u8FB9\u6846\u989C\u8272"],
  ],
  [2000, 2400, 2400, 2560]
));
children.push(para("\u5F00\u53D1\u8005\u6A21\u5F0F\uFF1A.dev-only \u7C7B\u9ED8\u8BA4 display:none\uFF0C\u901A\u8FC7 body.dev-mode .dev-only \u663E\u793A\u3002\u539F\u59CB\u6570\u636E\u5C55\u793A\uFF1A.raw-payload \u7C7B\u540C\u7406\u3002\u54CD\u5E94\u5F0F\uFF1A@media (max-width: 900px) \u9690\u85CF\u4FA7\u8FB9\u680F\u3002"));

children.push(heading("10.7 \u65B0\u7AEF\u70B9\u96C6\u6210\u793A\u4F8B\u4EE3\u7801", HeadingLevel.HEADING_2));
children.push(para("\u4EE5\u4E0B\u4E3A ML \u9884\u6D4B\u4FE1\u53F7\u7684\u96C6\u6210\u793A\u4F8B\uFF0C\u53C2\u8003\u73B0\u6709\u4EE3\u7801\u98CE\u683C\uFF1A"));
children.push(para("// dashboard.js \u4E2D\u6DFB\u52A0\u7684 API \u8C03\u7528", { run: { color: "666666", size: 18 } }));
children.push(para("const mlPrediction = await safeFetch(`${apiBaseUrl}/api/prediction/signals?date=${effectiveDate}`);", { run: { color: "666666", size: 18 } }));
children.push(para("// \u6E32\u67D3\u51FD\u6570", { run: { color: "666666", size: 18 } }));
children.push(para("function renderMLPrediction(data) {", { run: { color: "666666", size: 18 } }));
children.push(para("  const el = document.getElementById('section-ml-prediction');", { run: { color: "666666", size: 18 } }));
children.push(para("  if (!data.signals || data.signals.length === 0) {", { run: { color: "666666", size: 18 } }));
children.push(para("    el.innerHTML = '<p class=\"muted\">\u5F53\u65E5\u65E0 ML \u4E70\u5356\u4FE1\u53F7</p>'; return;", { run: { color: "666666", size: 18 } }));
children.push(para("  }", { run: { color: "666666", size: 18 } }));
children.push(para("  let html = '<table class=\"table\"><thead><tr>' +", { run: { color: "666666", size: 18 } }));
children.push(para("    '<th>\u4EE3\u7801</th><th>\u540D\u79F0</th><th>\u4FE1\u53F7</th><th>\u7F6E\u4FE1\u5EA6</th></tr></thead><tbody>';", { run: { color: "666666", size: 18 } }));
children.push(para("  data.signals.forEach(s => {", { run: { color: "666666", size: 18 } }));
children.push(para("    const pill = s.signal === 'buy' ? 'pill ok' : 'pill bad';", { run: { color: "666666", size: 18 } }));
children.push(para("    html += `<tr><td>${s.code}</td><td>${s.name}</td>` +", { run: { color: "666666", size: 18 } }));
children.push(para("      `<td><span class=\"${pill}\">${s.signal}</span></td><td>${s.confidence}</td></tr>`;", { run: { color: "666666", size: 18 } }));
children.push(para("  });", { run: { color: "666666", size: 18 } }));
children.push(para("  el.innerHTML = html + '</tbody></table>';", { run: { color: "666666", size: 18 } }));
children.push(para("}", { run: { color: "666666", size: 18 } }));

// ---- 十一、附录 ----
children.push(heading("\u5341\u4E00\u3001\u9644\u5F55", HeadingLevel.HEADING_1));

children.push(heading("11.1 \u5173\u952E\u6587\u4EF6\u7D22\u5F15", HeadingLevel.HEADING_2));
children.push(makeTable(
  ["\u6587\u4EF6", "\u4F4D\u7F6E", "\u8BF4\u660E"],
  [
    ["\u8BAD\u7EC3\u811A\u672C", "neotrade3/ml/autore/train.py", "\u6838\u5FC3\u5B9E\u9A8C\u6587\u4EF6\uFF0C\u53EF\u8C03\u53C2\u6570"],
    ["\u5B9E\u9A8C\u914D\u7F6E", "neotrade3/ml/autore/config.py", "\u641C\u7D22\u7A7A\u95F4\u3001\u5B9E\u9A8C\u8BB0\u5F55\u5DE5\u5177"],
    ["\u6210\u529F\u8BB0\u5F55", "neotrade3/ml/autore/SUCCESS.md", "5 \u6B21\u5173\u952E\u5B9E\u9A8C\u8BB0\u5F55"],
    ["\u5931\u8D25\u8BB0\u5F55", "neotrade3/ml/autore/FAILED.md", "\u7EA6 20 \u6B21\u5931\u8D25\u5B9E\u9A8C"],
    ["\u7814\u7A76\u8BA1\u5212", "neotrade3/ml/autore/program.md", "ML \u7814\u7A76\u76EE\u6807\u548C\u89C4\u5212"],
    ["\u56DE\u6D4B\u6846\u67B6", "backtest.py", "ML \u7B56\u7565\u56DE\u6D4B"],
    ["\u677F\u5757\u8F6E\u52A8", "sector_rotation.py", "\u677F\u5757\u8F6E\u52A8\u5F15\u64CE"],
    ["\u677F\u5757\u56DE\u6D4B", "backtest_sector_rotation.py", "\u677F\u5757\u8F6E\u52A8\u56DE\u6D4B"],
    ["\u57FA\u672C\u9762\u9002\u914D", "neotrade3/data/akshare_adapter.py", "PE/PB/ROE \u6570\u636E\u9002\u914D\u5668"],
    ["API \u670D\u52A1", "apps/api/main.py", "\u6240\u6709 API \u7AEF\u70B9\uFF088400+ \u884C\uFF09"],
    ["Dashboard", "apps/dashboard/main.py", "Web \u4EEA\u8868\u76D8\uFF08\u7AEF\u53E3 18031\uFF09"],
    ["Worker", "apps/worker/main.py", "\u540E\u53F0\u4EFB\u52A1\uFF08\u6570\u636E\u91C7\u96C6\uFF09"],
  ],
  [2000, 3800, 3560]
));

children.push(heading("11.2 \u5F52\u6863\u6587\u4EF6", HeadingLevel.HEADING_2));
children.push(para("\u4EE5\u4E0B\u6587\u4EF6\u5DF2\u79FB\u81F3 scripts/archive/\uFF1A"));
children.push(bullet("optimize_model.py / optimize_model_v2.py \u2014\u2014 \u53C2\u6570\u4F18\u5316\u5B9E\u9A8C\u811A\u672C"));
children.push(para("\u4EE5\u4E0B\u6587\u4EF6\u5DF2\u79FB\u81F3 var/models/archive/\uFF1A"));
children.push(bullet("rf_model_v1.pkl ~ rf_model_v4.pkl \u2014\u2014 \u5386\u53F2\u6A21\u578B\u7248\u672C"));

// ============================================================
// 生成文档
// ============================================================
const doc = new Document({
  styles: {
    default: {
      document: { run: { font: FONT, size: 21 } }
    },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, font: FONT },
        paragraph: { spacing: { before: 360, after: 200 }, outlineLevel: 0, keepNext: false, keepLines: false } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 26, bold: true, font: FONT },
        paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1, keepNext: false, keepLines: false } },
    ]
  },
  numbering: {
    config: [
      { reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "\u2022", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
      ...numberConfigs,
    ]
  },
  sections: [{
    properties: {
      page: { size: { width: 11906, height: 16838 }, margin: { top: 1440, right: 1200, bottom: 1440, left: 1200 } }
    },
    headers: {
      default: new Header({ children: [new Paragraph({ children: [new TextRun({ text: "NeoTrade3 \u9879\u76EE\u4EA4\u63A5\u6587\u6863", font: FONT, size: 18, color: "999999" })] })] })
    },
    footers: {
      default: new Footer({ children: [new Paragraph({ children: [new TextRun({ text: "\u7B2C ", font: FONT, size: 18, color: "999999" }), new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 18, color: "999999" }), new TextRun({ text: " \u9875", font: FONT, size: 18, color: "999999" })] })] })
    },
    children
  }]
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync("/sessions/6a114a44ee100de4314469d7/workspace/NeoTrade3/NeoTrade3_交接文档.docx", buffer);
  console.log("文档生成完成: NeoTrade3_交接文档.docx");
});
