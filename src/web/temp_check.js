        const { createApp, ref, reactive, onMounted, nextTick, computed } = Vue;

        createApp({
            setup() {
                const currentTab = ref('dashboard');

                // Dashboard State
                const filters = reactive({
                    item_name: '',
                    station: '',
                    product: '',
                    line: '',
                    start_time: '',
                    end_time: ''
                });

                // Initialize with 24h default
                onMounted(() => {
                    const end = new Date();
                    const start = new Date(end.getTime() - 24 * 60 * 60 * 1000);
                    // Format to YYYY-MM-DD (input type="date")
                    filters.end_time = end.toISOString().split('T')[0];
                    filters.start_time = start.toISOString().split('T')[0];
                    fetchOptions();
                    fetchConfigs();
                    // Do not auto-search on load anymore, as context is required
                });

                const options = ref({ items: [], stations: [], products: [], lines: [] });
                const alertRecords = ref([]);
                const showModal = ref(false);
                const selectedRecord = ref(null);
                let mainChart = null, baselineChart = null, detailChart = null;

                const searchHistory = async () => {
                    if (!filters.item_name) return;

                    // --- Strict Context Validation ---
                    if (!filters.station || !filters.product || !filters.line) {
                        alert("请先选择完整的 Context (Station, Product, Line) 以确保数据唯一性。");
                        return;
                    }

                    try {
                        let query = `?item_name=${encodeURIComponent(filters.item_name)}`;
                        if (filters.station) query += `&station=${encodeURIComponent(filters.station)}`;
                        if (filters.product) query += `&product=${encodeURIComponent(filters.product)}`;
                        if (filters.line) query += `&line=${encodeURIComponent(filters.line)}`;
                        if (filters.start_time) query += `&start_time=${filters.start_time}T00:00:00`;
                        if (filters.end_time) query += `&end_time=${filters.end_time}T23:59:59`;

                        const response = await fetch(`/api/v1/history${query}`);
                        const data = await response.json();
                        alertRecords.value = data;
                        updateMainChart(data);
                    } catch (error) {
                        console.error('Search failed:', error);
                    }
                };

                // Config State
                const configList = reactive({ item_configs: {} });
                const globalDefaults = ref({});
                const showConfigModal = ref(false);
                const showImportModal = ref(false); // NEW
                const editingItemName = ref('');
                const editingConfig = reactive({});
                const importText = ref(''); // NEW: Text area input
                const importMode = ref('text'); // 'text' or 'csv'
                const configSearch = ref('');
                const showBatchSettings = ref(false);
                const batchConfig = reactive({
                    target_shift_sigma: 1.0,
                    target_arl0: 250,
                    cooldown_periods: 10,
                    monitoring_side: 'upper'
                });

                // Batch Selection
                const selectedItems = ref([]);

                const configFilters = reactive({
                    itemName: '',
                    product: '',
                    station: '',
                    line: ''
                });

                const filteredConfigs = computed(() => {
                    const all = configList.item_configs;
                    const result = {};

                    // Filter terms
                    const fName = (configFilters.itemName || '').toLowerCase();
                    const fProduct = (configFilters.product || '').toLowerCase();
                    const fStation = (configFilters.station || '').toLowerCase();
                    const fLine = (configFilters.line || '').toLowerCase();

                    for (const key in all) {
                        const conf = all[key];
                        // Parse Key or Use Stored Metadata
                        let product = '', line = '', station = '', itemName = key;

                        // Priority 1: Use stored metadata if available (from manual import)
                        if (conf.meta_data) {
                            product = conf.meta_data.product || '';
                            line = conf.meta_data.line || '';
                            station = conf.meta_data.station || '';
                            // If key is composite, extract true item name, otherwise use key
                            if (key.includes('::')) {
                                const parts = key.split('::');
                                itemName = parts[parts.length - 1];
                            }
                        }
                        // Priority 2: Parse from Key (legacy/auto-generated)
                        else if (key.includes('::')) {
                            const parts = key.split('::');
                            if (parts.length === 4) {
                                [product, line, station, itemName] = parts;
                            }
                        }

                        // precise matching logic
                        if (fName && !itemName.toLowerCase().includes(fName)) continue;
                        if (fProduct && !product.toLowerCase().includes(fProduct)) continue;
                        if (fStation && !station.toLowerCase().includes(fStation)) continue;
                        if (fLine && !line.toLowerCase().includes(fLine)) continue;

                        result[key] = {
                            conf: conf,
                            meta: {
                                product: product.toUpperCase(),
                                line: line.toUpperCase(),
                                station: station.toUpperCase(),
                                item_name: itemName
                            }
                        };
                    }
                    return result;
                });

                const isAllSelected = computed(() => {
                    const allKeys = Object.keys(filteredConfigs.value);
                    return allKeys.length > 0 && selectedItems.value.length === allKeys.length;
                });

                const toggleSelectAll = () => {
                    if (isAllSelected.value) {
                        selectedItems.value = [];
                    } else {
                        selectedItems.value = Object.keys(filteredConfigs.value);
                    }
                };

                const batchDelete = async () => {
                    if (selectedItems.value.length === 0) return;
                    if (!confirm(`Are you sure you want to delete ${selectedItems.value.length} items? This cannot be undone.`)) return;

                    try {
                        const res = await fetch('/api/v1/configs/batch-delete', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ items: selectedItems.value })
                        });

                        const data = await res.json();
                        if (res.ok) {
                            alert(data.message);
                            selectedItems.value = [];
                            fetchConfigs();
                        } else {
                            alert('Batch delete failed: ' + (data.detail || 'Unknown error'));
                        }
                    } catch (e) {
                        console.error(e);
                        alert('Network error');
                    }
                };

                // Format Time
                const formatTime = (isoStr) => {
                    if (!isoStr) return '-';
                    const d = new Date(isoStr);
                    return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
                };

                // Helper: Calculate H
                const calculateH = (shift, arl0) => {
                    if (!shift || !arl0 || shift <= 0 || arl0 <= 1) return '-';
                    // Formula: h = (2 / shift^2) * ln(arl0)
                    const h = (2.0 / (shift * shift)) * Math.log(arl0);
                    return h.toFixed(4);
                };

                // --- Config Methods ---
                const fetchConfigs = async () => {
                    try {
                        const res = await fetch('/api/v1/configs');
                        const data = await res.json();
                        configList.item_configs = data.item_configs;
                        globalDefaults.value = data.global_defaults;
                    } catch (e) {
                        console.error("Failed to load configs", e);
                    }
                };

                const saveGlobalConfig = async () => {
                    try {
                        const res = await fetch('/api/v1/configs/global', {
                            method: 'PUT',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(globalDefaults.value)
                        });
                        if (res.ok) {
                            alert('全局策略已更新并广播到所有检测器!');
                            fetchConfigs();
                        } else {
                            alert('Global config update failed');
                        }
                    } catch (e) { console.error(e); alert('Network error'); }
                };

                const batchContext = reactive({ product: '', line: '', station: '' }); // NEW

                const batchImport = async () => {
                    if (!importText.value.trim()) return;

                    // Split by newlines, taking first column if comma/tab separated
                    const items = importText.value.split(/\n/).map(line => {
                        line = line.trim();
                        if (!line) return null;
                        // Handle CSV row: "ItemName, ..."
                        if (line.includes(',')) return line.split(',')[0].trim();
                        if (line.includes('\t')) return line.split('\t')[0].trim();
                        return line;
                    }).filter(Boolean);

                    if (items.length === 0) {
                        alert('无有效监控项 (No valid items found)');
                        return;
                    }

                    // Enforce Mandatory Metadata
                    if (!batchContext.product || !batchContext.station || !batchContext.line) {
                        alert('错误：必须指定 产品(Product)、工站(Station) 和 产线(Line)！\n这些参数定义了检测服务的生效范围。');
                        return;
                    }

                    // Construct meta_data (Force Lowercase)
                    const meta_data = {
                        product: batchContext.product.trim().toLowerCase(),
                        station: batchContext.station.trim().toLowerCase(),
                        line: batchContext.line.trim().toLowerCase()
                    };

                    try {
                        const res = await fetch('/api/v1/items/batch-import', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                items: items,
                                config: showBatchSettings.value ? batchConfig : null,
                                meta_data: meta_data
                            })
                        });
                        console.log("Batch Import Payload:", { items, meta_data, config: batchConfig }); // DEBUG log
                        const data = await res.json();
                        if (res.ok) {
                            alert(data.message);
                            showImportModal.value = false;
                            importText.value = '';
                            batchContext.product = ''; // Reset
                            batchContext.line = '';
                            batchContext.station = '';
                            fetchConfigs();
                            fetchOptions(); // update dropdowns too
                        } else {
                            alert('Import failed');
                        }
                    } catch (e) {
                        console.error(e);
                        alert('Network Error');
                    }
                };

                const openConfigEdit = (name, conf) => {
                    editingItemName.value = name;
                    // Merge global defaults if value is missing
                    Object.assign(editingConfig, {
                        target_shift_sigma: conf.target_shift_sigma ?? globalDefaults.value.target_shift_sigma,
                        target_arl0: conf.target_arl0 ?? globalDefaults.value.target_arl0,
                        cooldown_periods: conf.cooldown_periods ?? globalDefaults.value.cooldown_periods,
                        mu0: conf.mu0, // mu0 optional defined at item level
                        monitoring_side: conf.monitoring_side || 'upper', // default
                        base_uph: conf.base_uph ?? 500, // new
                        penalty_strength: conf.penalty_strength ?? 1.0 // new
                    });
                    showConfigModal.value = true;
                };

                const saveConfig = async () => {
                    try {
                        const res = await fetch(`/api/v1/configs/${editingItemName.value}`, {
                            method: 'PUT',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(editingConfig)
                        });
                        if (res.ok) {
                            showConfigModal.value = false;
                            fetchConfigs(); // Refresh list
                            alert('配置更新成功! (实时生效)');
                        } else {
                            alert('Update failed');
                        }
                    } catch (e) {
                        console.error(e);
                        alert('Network error');
                    }
                };

                const deleteItem = async (itemName) => {
                    if (!confirm(`Are you sure you want to delete item "${itemName}"? This cannot be undone.`)) {
                        return;
                    }
                    try {
                        const res = await fetch(`/api/v1/configs/${itemName}`, {
                            method: 'DELETE'
                        });
                        if (res.ok) {
                            alert(`Item ${itemName} deleted successfully`);
                            fetchConfigs();
                        } else {
                            alert('Delete failed');
                        }
                    } catch (e) { console.error(e); alert('Network error'); }
                };


                // --- Dashboard Methods ---

                const fetchData = async () => {
                    // 构建 Query String
                    const params = new URLSearchParams();
                    if (filters.item_name) params.append('item_name', filters.item_name);
                    if (filters.station) params.append('station', filters.station);
                    if (filters.product) params.append('product', filters.product);
                    if (filters.line) params.append('line', filters.line);
                    if (filters.start_time) params.append('start_time', filters.start_time + 'T00:00:00');
                    if (filters.end_time) params.append('end_time', filters.end_time + 'T23:59:59');
                    params.append('limit', '20000');

                    try {
                        const res = await fetch(`/api/v1/history?${params.toString()}`);
                        const data = await res.json();
                        if (data.length === 0) {
                            if (mainChart) mainChart.clear();
                            if (baselineChart) baselineChart.clear();
                            alertRecords.value = [];
                            return;
                        }
                        renderCharts(data);
                        alertRecords.value = data.filter(r => r.is_alert).reverse().slice(0, 100);
                    } catch (e) { console.error(e); }
                };

                const renderCharts = (data) => {
                    // X轴统一使用简化时间
                    const timestamps = data.map(r => formatTime(r.timestamp));

                    const commonOption = () => ({
                        tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
                        grid: { left: '3%', right: '3%', bottom: '10%', containLabel: true },
                        dataZoom: [{ type: 'inside' }, { type: 'slider', bottom: 10 }],
                        xAxis: { type: 'category', data: timestamps, boundaryGap: false }
                    });

                    // --- Main Chart ---
                    if (mainChart) mainChart.dispose();
                    mainChart = echarts.init(document.getElementById('mainChart'));
                    mainChart.setOption({
                        ...commonOption(),
                        legend: { data: ['Value', 'Threshold (h)', 'CUSUM'] },
                        yAxis: [
                            { type: 'value', name: 'Value', position: 'left' },
                            { type: 'value', name: 'Score', position: 'right', splitLine: { show: false } }
                        ],
                        series: [
                            { name: 'Value', type: 'line', data: data.map(r => r.value), yAxisIndex: 0, smooth: true, itemStyle: { color: '#3b82f6' }, areaStyle: { opacity: 0.1 } },
                            { name: 'Threshold (h)', type: 'line', data: data.map(r => r.h_value), yAxisIndex: 1, lineStyle: { type: 'dashed', color: '#ef4444' }, showSymbol: false },
                            { name: 'CUSUM', type: 'line', data: data.map(r => r.s_plus), yAxisIndex: 1, lineStyle: { color: '#f59e0b', width: 2 } }
                        ]
                    });

                    // --- Baseline Chart ---
                    if (baselineChart) baselineChart.dispose();
                    baselineChart = echarts.init(document.getElementById('baselineChart'));
                    baselineChart.setOption({
                        ...commonOption(),
                        legend: { data: ['Baseline (μ)', 'Std (σ)'] },
                        yAxis: [{ type: 'value', name: 'μ' }, { type: 'value', name: 'σ', position: 'right' }],
                        series: [
                            { name: 'Baseline (μ)', type: 'line', data: data.map(r => r.baseline), yAxisIndex: 0, color: '#10b981' },
                            { name: 'Std (σ)', type: 'line', data: data.map(r => r.std), yAxisIndex: 1, color: '#8b5cf6', showSymbol: false }
                        ]
                    });

                    echarts.connect([mainChart, baselineChart]);
                };

                const openDetail = async (record) => {
                    selectedRecord.value = record;
                    showModal.value = true;

                    // 计算前后 48 小时 (确保足够覆盖 30+ 周期)
                    const centerTime = new Date(record.timestamp);
                    const startTime = new Date(centerTime.getTime() - 48 * 60 * 60 * 1000).toISOString();
                    const endTime = new Date(centerTime.getTime() + 48 * 60 * 60 * 1000).toISOString();

                    const params = new URLSearchParams();
                    params.append('item_name', record.item_name);
                    params.append('start_time', startTime);
                    params.append('end_time', endTime);

                    // Fetch context data
                    const res = await fetch(`/api/v1/history?${params.toString()}`);
                    const data = await res.json();

                    await nextTick(); // Wait for DOM
                    renderDetailChart(data);
                };

                const renderDetailChart = (data) => {
                    if (detailChart) detailChart.dispose();
                    detailChart = echarts.init(document.getElementById('detailChart'));

                    const timestamps = data.map(r => formatTime(r.timestamp));
                    detailChart.setOption({
                        title: { text: '30周期全息快照', left: 'center' },
                        tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
                        legend: { data: ['Value', 'CUSUM', 'Threshold'], top: 30 },
                        grid: { bottom: 50, right: 50, left: 50 },
                        xAxis: { type: 'category', data: timestamps },
                        yAxis: [{ type: 'value', name: 'Val' }, { type: 'value', name: 'Score' }],
                        dataZoom: [{ type: 'inside' }],
                        series: [
                            { name: 'Value', type: 'line', data: data.map(r => r.value), yAxisIndex: 0, color: '#3b82f6' },
                            { name: 'CUSUM', type: 'line', data: data.map(r => r.s_plus), yAxisIndex: 1, color: '#f59e0b', width: 3 },
                            { name: 'Threshold', type: 'line', data: data.map(r => r.h_value), yAxisIndex: 1, lineStyle: { type: 'dashed', color: '#ef4444' } }
                        ],
                        // MarkLine: 标出报警时刻
                        graphic: [{ type: 'line', shape: { x1: '50%', y1: 10, x2: '50%', y2: '90%' }, style: { stroke: 'rgba(255,0,0,0.3)', lineWidth: 1 } }]
                    });
                };


                const fetchOptions = async () => {
                    try {
                        // Build query from current filters (excluding time)
                        let query = '?';
                        if (filters.item_name) query += `item_name=${encodeURIComponent(filters.item_name)}&`;
                        if (filters.station) query += `station=${encodeURIComponent(filters.station)}&`;
                        if (filters.product) query += `product=${encodeURIComponent(filters.product)}&`;
                        if (filters.line) query += `line=${encodeURIComponent(filters.line)}&`;

                        const response = await fetch(`/api/v1/options${query}`);
                        const data = await response.json();

                        // We ONLY update options if the new list is non-empty, or we might clear valid selections?
                        // Actually, backend returns filtered options. We should just update.
                        options.value = data;
                    } catch (error) {
                        console.error('Failed to fetch options:', error);
                    }
                };

                // Expose to template
                const searchHistoryTrigger = searchHistory;

                onMounted(() => {
                    fetchConfigs();
                    fetchOptions(); // 加载下拉菜单
                    // Removed automatic fetchData() to enforce manual search
                    window.addEventListener('resize', () => {
                        mainChart && mainChart.resize();
                        baselineChart && baselineChart.resize();
                        detailChart && detailChart.resize();
                    });
                });

                const openImportModal = () => {
                    // Populate batchConfig with current defaults
                    Object.assign(batchConfig, {
                        target_shift_sigma: globalDefaults.value.target_shift_sigma,
                        target_arl0: globalDefaults.value.target_arl0,
                        cooldown_periods: globalDefaults.value.cooldown_periods,
                        monitoring_side: globalDefaults.value.monitoring_side || 'upper'
                    });
                    showImportModal.value = true;
                };

                // File Upload Logic
                const fileInput = ref(null);
                const triggerFileUpload = () => {
                    fileInput.value.click();
                };
                const handleFileUpload = (event) => {
                    const file = event.target.files[0];
                    if (!file) return;

                    const reader = new FileReader();

                    const isExcel = file.name.endsWith('.xlsx') || file.name.endsWith('.xls');

                    if (isExcel) {
                        reader.onload = (e) => {
                            const data = new Uint8Array(e.target.result);
                            const workbook = XLSX.read(data, { type: 'array' });

                            // 读取第一个 Sheet
                            const firstSheetName = workbook.SheetNames[0];
                            const worksheet = workbook.Sheets[firstSheetName];

                            // 转换为 JSON (header: 1 返回二维数组)
                            const jsonData = XLSX.utils.sheet_to_json(worksheet, { header: 1 });

                            // 提取有效的第一列数据 (排除空行)
                            const items = jsonData.map(row => row[0]).filter(item => item && String(item).trim() !== "");

                            importText.value = items.join('\n');
                        };
                        reader.readAsArrayBuffer(file);
                    } else {
                        // Text / CSV
                        reader.onload = (e) => {
                            const content = e.target.result;
                            importText.value = content;
                        };
                        reader.readAsText(file);
                    }

                    // Reset input so same file can be selected again
                    event.target.value = '';
                };

                return {
                    currentTab,
                    filters, options, fetchData, alertRecords, formatTime,
                    showModal, selectedRecord, openDetail,
                    // Config Exports
                    configList, globalDefaults, showConfigModal, editingItemName, editingConfig,
                    fetchConfigs, openConfigEdit, saveConfig, deleteItem,
                    // Import Exports
                    showImportModal, importText, batchImport, saveGlobalConfig,
                    openImportModal, showBatchSettings, batchConfig, batchContext, // Export batchContext
                    fileInput, triggerFileUpload, handleFileUpload,
                    configSearch, filteredConfigs, configFilters, // Export configFilters
                    // Helper
                    calculateH,
                    // Selection
                    selectedItems, isAllSelected, toggleSelectAll, batchDelete
                };
            }
        }).mount('#app');
