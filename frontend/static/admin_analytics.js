const elements = Object.fromEntries(
  [
    "loadingState", "errorState", "errorTitle", "errorMessage", "buildCommand", "retryButton",
    "dashboardContent", "periodBadge", "qualityBadge", "generatedAt", "kpiGrid", "chartFallback",
    "repeatRate", "rankingTabs", "rankingBody", "metricHeading", "insightGrid", "qualityGrid",
  ].map((id) => [id, document.querySelector(`#${id}`)])
);

const chartIds = [
  "monthlyChart", "ageChart", "genderChart", "groupChart", "typeChart", "consumptionChart",
  "typeCostChart", "satisfactionChart", "quadrantChart",
];
const charts = [];
let dashboard = null;

const rankingDefinitions = {
  popular: { label: "热门景点", heading: "游览人次", metric: (item) => formatInteger(item.visit_count) },
  high_spend: { label: "高消费景点", heading: "平均消费", metric: (item) => formatCurrency(item.average_total_cost) },
  long_stay: { label: "长停留景点", heading: "平均停留", metric: (item) => `${formatDecimal(item.average_stay_hours)} 小时` },
  high_satisfaction: { label: "高口碑景点", heading: "平均满意度", metric: (item) => `${formatDecimal(item.average_satisfaction)} 分` },
  low_satisfaction: { label: "待改善景点", heading: "平均满意度", metric: (item) => `${formatDecimal(item.average_satisfaction)} 分` },
};

elements.retryButton.addEventListener("click", loadDashboard);
window.addEventListener("resize", resizeCharts);
window.addEventListener("beforeunload", disposeCharts);

async function loadDashboard() {
  showLoading();
  try {
    const response = await fetch("/api/admin/analytics/dashboard");
    const data = await response.json();
    if (!response.ok) {
      const error = new Error(data.detail || `HTTP ${response.status}`);
      error.status = response.status;
      if (response.status === 503) error.isSnapshotUnavailable = true;
      throw error;
    }
    dashboard = data;
    showDashboard();
    renderDashboard(data);
  } catch (error) {
    showError(error);
  }
}

function showLoading() {
  elements.loadingState.hidden = false;
  elements.errorState.hidden = true;
  elements.dashboardContent.hidden = true;
}

function showDashboard() {
  elements.loadingState.hidden = true;
  elements.errorState.hidden = true;
  elements.dashboardContent.hidden = false;
}

function showError(error) {
  elements.loadingState.hidden = true;
  elements.dashboardContent.hidden = true;
  elements.errorState.hidden = false;
  elements.errorTitle.textContent = error.isSnapshotUnavailable ? "游客分析快照尚未生成" : "游客分析加载失败";
  const message = String(error.message || "未知错误");
  const marker = "初始化命令：";
  const markerIndex = message.indexOf(marker);
  elements.errorMessage.textContent = markerIndex >= 0 ? message.slice(0, markerIndex) : message;
  elements.buildCommand.hidden = markerIndex < 0;
  elements.buildCommand.textContent = markerIndex >= 0 ? message.slice(markerIndex + marker.length) : "";
}

function renderDashboard(data) {
  renderMetadata(data.metadata, data.quality);
  renderKpis(data.kpis);
  renderDemographics(data.demographics);
  renderRankingTabs(data.attraction_rankings);
  renderInsights(data.insights);
  renderQuality(data.quality);
  renderCharts(data);
}

function renderMetadata(metadata, quality) {
  elements.periodBadge.textContent = `${metadata.period_start} — ${metadata.period_end}`;
  elements.generatedAt.textContent = `生成于 ${formatDateTime(metadata.generated_at)}`;
  const issueCount = Number(quality.invalid_rows || 0) + Number(quality.missing_cells || 0);
  elements.qualityBadge.textContent = issueCount === 0 ? "基础校验通过" : `发现 ${formatInteger(issueCount)} 项问题`;
}

function renderKpis(kpis) {
  const cards = [
    ["游览人次", formatInteger(kpis.visit_count)],
    ["独立游客", formatInteger(kpis.tourist_count)],
    ["景点数量", formatInteger(kpis.attraction_count)],
    ["平均停留", `${formatDecimal(kpis.average_stay_hours)} 小时`],
    ["平均单次消费", formatCurrency(kpis.average_total_cost)],
    ["平均满意度", `${formatDecimal(kpis.average_satisfaction)} 分`],
  ];
  clearElement(elements.kpiGrid);
  cards.forEach(([label, value]) => {
    const card = document.createElement("article");
    card.className = "kpi-card";
    const labelNode = document.createElement("span");
    labelNode.textContent = label;
    const valueNode = document.createElement("strong");
    valueNode.textContent = value;
    card.append(labelNode, valueNode);
    elements.kpiGrid.appendChild(card);
  });
}

function renderDemographics(demographics) {
  elements.repeatRate.textContent = formatPercent(demographics.repeat_visitor_rate);
}

function renderRankingTabs(rankings) {
  clearElement(elements.rankingTabs);
  Object.entries(rankingDefinitions).forEach(([key, definition], index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `ranking-tab${index === 0 ? " active" : ""}`;
    button.textContent = definition.label;
    button.addEventListener("click", () => {
      elements.rankingTabs.querySelectorAll("button").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      renderRanking(key, rankings[key] || []);
    });
    elements.rankingTabs.appendChild(button);
  });
  renderRanking("popular", rankings.popular || []);
}

function renderRanking(key, rows) {
  const definition = rankingDefinitions[key];
  elements.metricHeading.textContent = definition.heading;
  clearElement(elements.rankingBody);
  if (!rows.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 5;
    cell.textContent = "没有达到排行榜样本门槛的景点。";
    row.appendChild(cell);
    elements.rankingBody.appendChild(row);
    return;
  }
  rows.forEach((item, index) => {
    const row = document.createElement("tr");
    row.append(
      tableCell(String(index + 1), "ranking-index"),
      tableCell(item.name),
      tableCell(item.attraction_type || "未分类"),
      tableCell(formatInteger(item.visit_count)),
      tableCell(definition.metric(item))
    );
    elements.rankingBody.appendChild(row);
  });
}

function renderInsights(insights) {
  clearElement(elements.insightGrid);
  insights.forEach((item) => {
    const card = document.createElement("article");
    card.className = `insight-card insight-${item.kind || "general"}`;
    const title = document.createElement("strong");
    title.textContent = item.title;
    const description = document.createElement("p");
    description.textContent = item.description;
    card.append(title, description);
    elements.insightGrid.appendChild(card);
  });
}

function renderQuality(quality) {
  const rows = [
    ["缺失单元格", quality.missing_cells],
    ["分析字段重复行", quality.analytical_duplicate_rows],
    ["无效数据行", quality.invalid_rows],
    ["消费合计差异", quality.total_cost_mismatch_rows],
  ];
  clearElement(elements.qualityGrid);
  rows.forEach(([label, value]) => {
    const card = document.createElement("article");
    card.className = "quality-card";
    const title = document.createElement("strong");
    title.textContent = label;
    const note = document.createElement("span");
    note.textContent = "静态快照质量检查";
    const count = document.createElement("b");
    count.textContent = formatInteger(value || 0);
    card.append(title, note, count);
    elements.qualityGrid.appendChild(card);
  });
}

function renderCharts(data) {
  disposeCharts();
  if (!window.echarts) {
    elements.chartFallback.hidden = false;
    chartIds.forEach((id) => {
      const node = document.querySelector(`#${id}`);
      node.textContent = "图表暂不可用";
    });
    return;
  }
  elements.chartFallback.hidden = true;
  try {
    renderMonthlyChart(data.monthly_trend);
    renderAgeChart(data.demographics.age_groups || []);
    renderGenderChart(data.demographics.genders || []);
    renderGroupChart(data.demographics.group_sizes || []);
    renderTypeChart(data.attraction_types || []);
    renderConsumptionChart(data.consumption.categories || []);
    renderTypeCostChart(data.consumption.by_attraction_type || []);
    renderSatisfactionChart(data.satisfaction.distribution || []);
    renderQuadrantChart(data.satisfaction);
  } catch (error) {
    console.error("游客分析图表渲染失败", error);
    elements.chartFallback.hidden = false;
    disposeCharts();
  }
}

function renderMonthlyChart(rows) {
  createChart("monthlyChart", {
    color: ["#176b5b"],
    tooltip: { trigger: "axis", valueFormatter: (value) => `${formatInteger(value)} 人次` },
    grid: { left: 54, right: 24, top: 30, bottom: 45 },
    xAxis: { type: "category", data: rows.map((item) => item.month), axisTick: { show: false } },
    yAxis: { type: "value", name: "游览人次", splitLine: { lineStyle: { color: "#e7edef" } } },
    series: [{ type: "line", smooth: true, symbolSize: 8, areaStyle: { opacity: 0.12 }, data: rows.map((item) => item.visit_count) }],
  });
}

function renderAgeChart(rows) {
  createChart("ageChart", barOption(rows.map((item) => item.label), rows.map((item) => item.count), "#2f8f79"));
}

function renderGenderChart(rows) {
  createChart("genderChart", {
    color: ["#176b5b", "#d09b48", "#6d83a8"],
    tooltip: { trigger: "item" },
    legend: { bottom: 0 },
    series: [{ type: "pie", radius: ["42%", "68%"], center: ["50%", "45%"], label: { formatter: "{b}\n{d}%" }, data: rows.map((item) => ({ name: item.label, value: item.count })) }],
  });
}

function renderGroupChart(rows) {
  createChart("groupChart", barOption(rows.map((item) => item.label), rows.map((item) => item.count), "#d09b48"));
}

function renderTypeChart(rows) {
  const ordered = [...rows].sort((a, b) => a.visit_count - b.visit_count);
  createChart("typeChart", horizontalBarOption(ordered.map((item) => item.name), ordered.map((item) => item.visit_count), "#176b5b"));
}

function renderConsumptionChart(rows) {
  createChart("consumptionChart", {
    color: ["#176b5b", "#2f8f79", "#d09b48", "#6d83a8", "#a66f55"],
    tooltip: { trigger: "item", formatter: (params) => `${params.name}<br/>${formatCurrency(params.value)} · ${params.percent}%` },
    legend: { bottom: 0 },
    series: [{ type: "pie", radius: ["38%", "68%"], center: ["50%", "45%"], data: rows.map((item) => ({ name: item.label, value: item.total })) }],
  });
}

function renderTypeCostChart(rows) {
  const ordered = [...rows].sort((a, b) => a.average_total_cost - b.average_total_cost);
  const option = horizontalBarOption(ordered.map((item) => item.name), ordered.map((item) => item.average_total_cost), "#d09b48");
  option.tooltip = { trigger: "axis", valueFormatter: formatCurrency };
  createChart("typeCostChart", option);
}

function renderSatisfactionChart(rows) {
  createChart("satisfactionChart", barOption(rows.map((item) => `${item.score} 分`), rows.map((item) => item.count), "#2f8f79"));
}

function renderQuadrantChart(satisfaction) {
  const points = (satisfaction.quadrants || []).map((item) => [
    item.average_total_cost,
    item.average_satisfaction,
    item.visit_count,
    item.name,
  ]);
  const maxVisits = Math.max(...points.map((item) => item[2]), 1);
  createChart("quadrantChart", {
    color: ["#176b5b"],
    tooltip: { formatter: (params) => `${params.value[3]}<br/>平均消费：${formatCurrency(params.value[0])}<br/>满意度：${formatDecimal(params.value[1])} 分<br/>访问量：${formatInteger(params.value[2])}` },
    grid: { left: 66, right: 28, top: 30, bottom: 52 },
    xAxis: { type: "value", name: "平均消费（元）", splitLine: { lineStyle: { color: "#e7edef" } } },
    yAxis: { type: "value", name: "满意度", min: 1, max: 5, splitLine: { lineStyle: { color: "#e7edef" } } },
    series: [{
      type: "scatter",
      data: points,
      symbolSize: (value) => 16 + Math.sqrt(value[2] / maxVisits) * 34,
      label: { show: true, formatter: (params) => params.value[3], position: "top", fontSize: 10 },
      itemStyle: { opacity: 0.78 },
      markLine: {
        silent: true,
        symbol: "none",
        lineStyle: { type: "dashed", color: "#8c9aa3" },
        data: [
          { xAxis: satisfaction.overall_average_cost },
          { yAxis: satisfaction.overall_average_satisfaction },
        ],
      },
    }],
  });
}

function barOption(categories, values, color) {
  return {
    color: [color],
    tooltip: { trigger: "axis" },
    grid: { left: 48, right: 18, top: 22, bottom: 42 },
    xAxis: { type: "category", data: categories, axisTick: { show: false }, axisLabel: { interval: 0 } },
    yAxis: { type: "value", splitLine: { lineStyle: { color: "#e7edef" } } },
    series: [{ type: "bar", data: values, barMaxWidth: 28, itemStyle: { borderRadius: [6, 6, 0, 0] } }],
  };
}

function horizontalBarOption(categories, values, color) {
  return {
    color: [color],
    tooltip: { trigger: "axis" },
    grid: { left: 126, right: 28, top: 20, bottom: 32 },
    xAxis: { type: "value", splitLine: { lineStyle: { color: "#e7edef" } } },
    yAxis: { type: "category", data: categories, axisTick: { show: false }, axisLabel: { width: 112, overflow: "truncate" } },
    series: [{ type: "bar", data: values, barMaxWidth: 22, itemStyle: { borderRadius: [0, 6, 6, 0] } }],
  };
}

function createChart(id, option) {
  const instance = window.echarts.init(document.querySelector(`#${id}`));
  instance.setOption({ textStyle: { fontFamily: '"Microsoft YaHei", sans-serif', color: "#42515b" }, ...option });
  charts.push(instance);
}

function resizeCharts() {
  charts.forEach((chart) => chart.resize());
}

function disposeCharts() {
  while (charts.length) charts.pop().dispose();
}

function tableCell(value, className = "") {
  const cell = document.createElement("td");
  cell.className = className;
  cell.textContent = value;
  return cell;
}

function clearElement(element) {
  while (element.firstChild) element.removeChild(element.firstChild);
}

function formatInteger(value) {
  return new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 0 }).format(Number(value || 0));
}

function formatDecimal(value) {
  return new Intl.NumberFormat("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(value || 0));
}

function formatCurrency(value) {
  return new Intl.NumberFormat("zh-CN", { style: "currency", currency: "CNY", maximumFractionDigits: 2 }).format(Number(value || 0));
}

function formatPercent(value) {
  return new Intl.NumberFormat("zh-CN", { style: "percent", minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(Number(value || 0));
}

function formatDateTime(value) {
  if (!value) return "--";
  return new Date(value).toLocaleString("zh-CN", { hour12: false });
}

loadDashboard();
