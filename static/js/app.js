// 全局变量：存储告警数据
let alertsData = [];
// 全局图表实例：避免重复渲染
let cpuTrendChart = null;
let alertTypeChart = null;

// 页面加载完成后执行
document.addEventListener('DOMContentLoaded', function() {
    // 1. 初始化：加载告警数据
    refreshAlerts();
    // 2. 绑定表单提交事件
    document.getElementById('alert-form').addEventListener('submit', submitAlert);
    // 阶段二新增：绑定搜索表单提交事件
    document.getElementById('search-form').addEventListener('submit', searchAlerts);
});

// 1. 刷新全部告警数据（无筛选）
async function refreshAlerts() {
    try {
        const response = await fetch('/alerts/');
        if (!response.ok) throw new Error('接口请求失败');
        
        const result = await response.json();
        alertsData = result.alerts || [];
        
        // 同步更新：列表 + 核心指标 + 图表
        renderAlertsTable();
        updateCoreMetrics();
        renderCharts();
    } catch (error) {
        alert('刷新数据失败：' + error.message);
        console.error(error);
    }
}

// 阶段二新增：搜索告警数据（带筛选条件）
async function searchAlerts(e) {
    e.preventDefault(); // 阻止表单默认提交

    // 获取搜索条件
    const hostname = document.getElementById('search-hostname').value.trim();
    const startTime = document.getElementById('search-start-time').value;
    const endTime = document.getElementById('search-end-time').value;

    // 构建搜索参数
    const params = new URLSearchParams();
    if (hostname) params.append('hostname', hostname);
    if (startTime) params.append('start_time', startTime);
    if (endTime) params.append('end_time', endTime);

    try {
        // 调用搜索接口
        const response = await fetch(`/alerts/search?${params.toString()}`, {
            method: 'GET',
            headers: { 'Content-Type': 'application/json' }
        });

        if (!response.ok) throw new Error('搜索失败');
        const result = await response.json();
        alertsData = result.alerts || [];
        
        // 更新页面展示
        renderAlertsTable();
        updateCoreMetrics();
        renderCharts();
        
        // 提示搜索结果
        alert(`搜索完成，共找到 ${alertsData.length} 条记录`);
    } catch (error) {
        alert('搜索告警失败：' + error.message);
        console.error(error);
    }
}

// 阶段二新增：重置搜索表单
function resetSearch() {
    document.getElementById('search-form').reset();
    // 重置后刷新全部数据
    refreshAlerts();
}

// 2. 渲染告警列表
function renderAlertsTable() {
    const tbody = document.getElementById('alerts-table-body');
    tbody.innerHTML = ''; // 清空原有内容

    if (alertsData.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="text-center">暂无告警数据</td></tr>';
        return;
    }

    // 遍历数据渲染行
    alertsData.forEach(alert => {
        const tr = document.createElement('tr');
        // 状态标签：数值>80为警告，否则为提示
        const statusLabel = alert.value > 80 
            ? '<span class="badge bg-warning">警告</span>' 
            : '<span class="badge bg-info">提示</span>';
        
        tr.innerHTML = `
            <td>${alert.created_at}</td>
            <td>${alert.hostname}</td>
            <td>${formatMetricName(alert.metric)}</td>
            <td>${alert.value}%</td>
            <td>${statusLabel}</td>
        `;
        tbody.appendChild(tr);
    });
}

// 3. 更新核心指标卡片
function updateCoreMetrics() {
    // 总告警数
    document.getElementById('total-alerts').textContent = alertsData.length;
    // 异常主机数：去重 + 数值>80的主机
    const errorHosts = [...new Set(alertsData.filter(a => a.value > 80).map(a => a.hostname))];
    document.getElementById('error-hosts').textContent = errorHosts.length;
    // 正常运行数：总告警 - 异常告警
    const normalCount = alertsData.filter(a => a.value <= 80).length;
    document.getElementById('normal-count').textContent = normalCount;
    // 系统状态：有异常则警告，否则正常
    const systemStatus = errorHosts.length > 0 ? '警告' : '正常';
    const statusElement = document.getElementById('system-status');
    statusElement.textContent = systemStatus;
    // 样式适配
    statusElement.className = systemStatus === '警告' 
        ? 'card-text display-4 text-warning' 
        : 'card-text display-4 text-success';
}

// 4. 渲染图表
function renderCharts() {
    // 4.1 处理图表数据
    const chartData = processChartData();
    // 4.2 渲染CPU趋势图
    renderCpuTrendChart(chartData.cpuData);
    // 4.3 渲染告警类型分布饼图
    renderAlertTypeChart(chartData.alertTypeData);
}

// 5. 处理图表所需数据（适配Chart.js格式）
function processChartData() {
    // 筛选CPU使用率数据（取最新10条，按时间排序）
    const cpuAlerts = alertsData
        .filter(a => a.metric === 'cpu_usage')
        .sort((a, b) => new Date(a.created_at) - new Date(b.created_at))
        .slice(-10); // 只取最后10条
    
    // CPU趋势图数据：时间轴 + 数值
    const cpuLabels = cpuAlerts.map(a => a.created_at.split(' ')[1]); // 取时分秒
    const cpuValues = cpuAlerts.map(a => a.value);

    // 告警类型分布数据：指标分组统计
    const metricCount = {};
    alertsData.forEach(a => {
        const metricName = formatMetricName(a.metric);
        metricCount[metricName] = (metricCount[metricName] || 0) + 1;
    });
    const alertTypeLabels = Object.keys(metricCount);
    const alertTypeValues = Object.values(metricCount);

    return {
        cpuData: { labels: cpuLabels, values: cpuValues },
        alertTypeData: { labels: alertTypeLabels, values: alertTypeValues }
    };
}

// 6. 渲染CPU使用率趋势图（折线图）
function renderCpuTrendChart(data) {
    const ctx = document.getElementById('cpuTrendChart').getContext('2d');
    // 销毁旧实例：避免重复渲染
    if (cpuTrendChart) cpuTrendChart.destroy();

    cpuTrendChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.labels,
            datasets: [{
                label: 'CPU使用率(%)',
                data: data.values,
                borderColor: '#0d6efd',
                backgroundColor: 'rgba(13, 110, 253, 0.1)',
                tension: 0.3,
                fill: true,
                pointBackgroundColor: '#0d6efd'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    title: { display: true, text: '使用率(%)' }
                }
            },
            plugins: {
                legend: { display: false }
            }
        }
    });
}

// 7. 渲染告警类型分布饼图
function renderAlertTypeChart(data) {
    const ctx = document.getElementById('alertTypeChart').getContext('2d');
    // 销毁旧实例：避免重复渲染
    if (alertTypeChart) alertTypeChart.destroy();

    // 饼图配色（适配Bootstrap主题）
    const colors = [
        '#0d6efd', '#198754', '#ffc107', '#dc3545', '#6f42c1', '#20c997'
    ];

    alertTypeChart = new Chart(ctx, {
        type: 'doughnut', // 环形图更美观
        data: {
            labels: data.labels,
            datasets: [{
                data: data.values,
                backgroundColor: colors.slice(0, data.labels.length),
                borderWidth: 1,
                borderColor: '#fff'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'right',
                    labels: { boxWidth: 15, padding: 15 }
                }
            }
        }
    });
}

// 8. 提交新告警
async function submitAlert(e) {
    e.preventDefault(); // 阻止表单默认提交

    // 获取表单数据
    const hostname = document.getElementById('hostname').value.trim();
    const metric = document.getElementById('metric').value;
    const value = parseInt(document.getElementById('value').value);
    const message = document.getElementById('message').value.trim() || `${formatMetricName(metric)}异常`;

    try {
        // 调用后端接口提交数据
        const response = await fetch('/alerts/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: new URLSearchParams({ hostname, metric, value, message })
        });

        if (!response.ok) throw new Error('提交失败');
        const result = await response.json();
        alert(result.message);
        
        // 重置表单 + 刷新数据（自动更新图表）
        document.getElementById('alert-form').reset();
        refreshAlerts();
    } catch (error) {
        alert('提交告警失败：' + error.message);
        console.error(error);
    }
}

// 辅助函数：格式化指标名称（如cpu_usage → CPU使用率）
function formatMetricName(metric) {
    const map = {
        'cpu_usage': 'CPU使用率',
        'mem_usage': '内存使用率',
        'disk_usage': '磁盘使用率',
        'network_in': '入站流量',
        'network_out': '出站流量'
    };
    return map[metric] || metric;
}