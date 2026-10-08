/*
 * tw-canslim-web
 * High-performance CANSLIM analyzer for Taiwan Stock Market
 */

const { createApp, ref, shallowRef, computed, onMounted } = Vue;

const app = createApp({
    setup() {
        const stockData = shallowRef(null);
        const stockIndexData = shallowRef(null);
        const currentStock = ref(null);
        const searchQuery = ref('');
        const lastUpdated = ref('');
        const isLoading = ref(true);
        const loadingProgress = ref(0);
        const errorState = ref(null);
        const searchSuggestions = ref([]);
        const activeTab = ref('search'); // 'search', 'ranking', 'screener', 'institutional'

        // Institutional Traders Data
        const institutionalData = ref({
            records: [
                { date: '10/07', foreign: -1164, trust: 66, proprietary: 447 },
                { date: '10/06', foreign: -1673, trust: 154, proprietary: 395 },
                { date: '10/05', foreign: 9770, trust: 589, proprietary: 491 },
                { date: '10/02', foreign: -5914, trust: 253, proprietary: 316 },
                { date: '10/01', foreign: 3090, trust: 596, proprietary: 602 }
            ],
            totalForeign: computed(() => institutionalData.value.records.reduce((sum, r) => sum + r.foreign, 0)),
            totalTrust: computed(() => institutionalData.value.records.reduce((sum, r) => sum + r.trust, 0)),
            totalProprietary: computed(() => institutionalData.value.records.reduce((sum, r) => sum + r.proprietary, 0))
        });

        // Screener Filters
        const screenerMinScore = ref(70);
        const screenerMinRs = ref(0);
        const screenerFundOnly = ref(false);
        const screenerIndustry = ref('All');

        const financialLabels = {
            'eps': '每股盈餘 (EPS)',
            'revenue': '營業收入 (百萬)',
            'net_income': '稅後淨利 (百萬)',
            'gross_margin': '毛利率',
            'operating_margin': '營業利益率',
            'net_margin': '稅後淨利率',
            'roe': '股東權益報酬率 (ROE)'
        };

        const canslimDefinitions = {
            'C': { title: 'Current Quarterly Earnings', desc: '最近一季 EPS 成長率 ≥ 25% (YoY)。' },
            'A': { title: 'Annual Earnings Increases', desc: '最近一年度 EPS 成長率 ≥ 25% (YoY)。' },
            'N': { title: 'New Products, Management, Highs', desc: '股價處於 52 週新高的 90% 區間內。' },
            'S': { title: 'Supply and Demand', desc: '成交量爆發（> 5 日均量 1.5 倍）。' },
            'L': { title: 'Leader or Laggard', desc: 'Mansfield RS 指標 > 0。' },
            'I': { title: 'Institutional Sponsorship', desc: '三大法人近 3 日買超。' },
            'M': { title: 'Market Direction', desc: '追蹤大盤多空。' }
        };

        // ============ Core Symbols (與 core_selection_config.json 同步) ============
        const CORE_SYMBOLS = new Set([
            '1101', '1301', '1303', '2303', '2330', '2357', '2395',
            '2881', '2882', '3565', '6770', '6805', '8069',
            '0050', '0056', '006208', '00878', '00919'
        ]);

        // Leader thresholds
        const SIGNAL_SCORE_THRESHOLD = 75;
        const RS_LEADER_THRESHOLD = 80;

        // 輪動分組計算
        const getRotationGroup = (symbol) => {
            if (CORE_SYMBOLS.has(symbol)) return 'core';
            const code = parseInt(symbol) || 0;
            const group = code % 3;
            return `group${group + 1}`;
        };

        // RS (相對強度): prefer the IBD-style 1-99 percentile rating from the
        // 股票健診 Excel health-check file (canslim.excel_ratings.rs_rating) --
        // reliable, locally-sourced, not subject to the TEJ/FinMind/yfinance
        // chain's rate limits/outages. Falls back to an approximate percentile
        // derived from the raw Mansfield RS ratio using the same formula
        // export_canslim.py's _export_leaders_json() already uses for
        // data/leaders.json, so "RS" means the same thing everywhere in this
        // app regardless of which source actually supplied it. Every "RS"
        // label in this UI (leader cards, tables, screener, RS_LEADER_THRESHOLD
        // comparisons) means *this* value -- it was already being compared
        // against a percentile-scale threshold (80) even when fed the raw
        // ratio, which a Mansfield RS value realistically never reaches.
        const getEffectiveRs = (stock) => {
            const excelRs = stock?.canslim?.excel_ratings?.rs_rating;
            if (excelRs !== undefined && excelRs !== null) return excelRs;
            const mansfield = stock?.canslim?.mansfield_rs;
            if (!mansfield) return null;
            return Math.min(99, Math.max(1, 50 + Math.round(mansfield * 5)));
        };

        // 股票分級
        const getStockTier = (symbol, stock) => {
            // 防禦性檢查：如果 stock 為 undefined/null，返回默認值
            if (!stock) {
                return {
                    tier: 'unknown', label: '', icon: '',
                    subtext: '', color: '', bg: '', border: '',
                    nextUpdate: '未知'
                };
            }
            if (CORE_SYMBOLS.has(symbol)) {
                const freshness = stock.freshness || {};
                const isFresh = freshness.days_old <= 1;
                return {
                    tier: 'core', label: 'Core', icon: '✅',
                    subtext: isFresh ? '最近更新' : '更新延遲',
                    color: isFresh ? 'text-emerald-600' : 'text-amber-600',
                    bg: isFresh ? 'bg-emerald-50' : 'bg-amber-50',
                    border: isFresh ? 'border-emerald-200' : 'border-amber-200',
                    nextUpdate: '每個交易日'
                };
            }
            const score = stock.canslim?.score || 0;
            const rs = getEffectiveRs(stock) || 0;
            if (score >= SIGNAL_SCORE_THRESHOLD || rs >= RS_LEADER_THRESHOLD) {
                let leaderType = 'Signal';
                if (rs >= RS_LEADER_THRESHOLD) leaderType = 'RS';
                else if (score >= SIGNAL_SCORE_THRESHOLD) leaderType = 'Score';
                return {
                    tier: 'leader', label: `Leader (${leaderType})`, icon: '🏆',
                    subtext: `Score: ${score} | RS: ${rs}`,
                    color: 'text-amber-600', bg: 'bg-amber-50', border: 'border-amber-200',
                    nextUpdate: '每個交易日'
                };
            }
            const group = getRotationGroup(symbol);
            const freshness = stock.freshness || {};
            const isStale = freshness.days_old > 2;
            const groupNames = {
                'group1': { name: 'G1', day: '一/四' },
                'group2': { name: 'G2', day: '二/五' },
                'group3': { name: 'G3', day: '三' }
            };
            const info = groupNames[group] || { name: 'G?', day: '?' };
            return {
                tier: 'rotation', label: info.name, icon: isStale ? '⏳' : '📅',
                subtext: `更新：週${info.day}`,
                color: isStale ? 'text-slate-500' : 'text-blue-600',
                bg: isStale ? 'bg-slate-50' : 'bg-blue-50',
                border: isStale ? 'border-slate-200' : 'border-blue-200',
                nextUpdate: `週${info.day}`
            } || {};
        };

        const getNextUpdateDay = (symbol) => {
            const tier = getStockTier(symbol, {});
            return tier?.nextUpdate || '未知';
        };

        const formatRelativeTime = (timestamp) => {
            if (!timestamp) return '';
            const date = new Date(timestamp);
            const now = new Date();
            const diffMs = now - date;
            const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
            const diffDays = Math.floor(diffHours / 24);
            if (diffHours < 1) return '剛剛';
            if (diffHours < 24) return `${diffHours}小時前`;
            if (diffDays === 1) return '昨天';
            if (diffDays < 7) return `${diffDays}天前`;
            return date.toLocaleDateString('zh-TW', { month: 'short', day: 'numeric' });
        };

        const safeNumber = (value) => {
            const normalized = Number(value);
            return Number.isFinite(normalized) ? normalized : 0;
        };

        const formatNumber = (value) => {
            return safeNumber(value).toLocaleString();
        };

        const fetchData = async () => {
            isLoading.value = true;
            loadingProgress.value = 10;
            try {
                // Use data_light.json for much faster initial load and search
                const [response, indexResponse] = await Promise.all([
                    fetch('data.json?t=' + new Date().getTime()),
                    fetch('stock_index.json?t=' + new Date().getTime())
                ]);
                
                if (!response.ok) throw new Error('資料載入失敗');
                if (!indexResponse.ok) throw new Error('索引載入失敗');
                
                const data = await response.json();
                const indexData = await indexResponse.json();
                
                loadingProgress.value = 60;
                try {
                    const featResp = await fetch('api/stock_features.json?t=' + new Date().getTime());
                    if (featResp.ok) {
                        const feat = await featResp.json();
                        let featMap = {};
                        if (Array.isArray(feat)) {
                            feat.forEach(item => { if (item.symbol) featMap[item.symbol] = item; });
                        } else {
                            featMap = feat || {};
                        }
                        
                        if (data.stocks) {
                            Object.keys(data.stocks).forEach(s => {
                                const stock = data.stocks[s];
                                const inline = stock.canslim || {};
                                if (featMap[s]) {
                                    stock.revenue_features = featMap[s];
                                } else if (Object.prototype.hasOwnProperty.call(inline, 'revenue_score')) {
                                    // The primary publish bundle already contains the score flags.
                                    // Keep the revenue UI useful when the optional TEJ feature export
                                    // is temporarily unavailable.
                                    stock.revenue_features = {
                                        revenue_score: inline.revenue_score || 0,
                                        rev_accelerating: !!inline.rev_accelerating,
                                        rev_strong: !!inline.rev_strong,
                                        rev_yoy: 0,
                                        rev_mom: 0,
                                        rev_acc_1: 0,
                                    };
                                }
                            });
                        }
                    }
                } catch (e) { console.warn('Features missing'); }

                stockData.value = data;
                stockIndexData.value = indexData;
                
                // Robust date parsing for the UI
                const rawDate = data.last_updated || 'Unknown';
                lastUpdated.value = rawDate.replace(/T\(.*?\)/g, ' ').replace('T', ' ').replace('Z', '');

                const urlParams = new URLSearchParams(window.location.search);
                const s = urlParams.get('s');
                if (s) selectStock(s);
            } catch (err) {
                errorState.value = `連線失敗: ${err.message}`;
            } finally {
                loadingProgress.value = 100;
                setTimeout(() => { isLoading.value = false; }, 500);
            }
        };

        const searchUniverse = computed(() => {
            const dataStocks = (stockData.value && stockData.value.stocks) || {};
            const indexStocks = (stockIndexData.value && stockIndexData.value.stocks) || {};
            const allSymbols = new Set([...Object.keys(dataStocks), ...Object.keys(indexStocks)]);
            return Array.from(allSymbols).map(symbol => {
                const detailed = dataStocks[symbol];
                const indexed = indexStocks[symbol];
                if (detailed) return { ...detailed, has_full_detail: true };
                return {
                    symbol, name: indexed?.name || symbol, industry: indexed?.industry || '其他',
                    is_etf: !!indexed?.is_etf, has_full_detail: false,
                    canslim: { score: 0, mansfield_rs: 0, grid_strategy: { levels: [] } },
                    institutional: [], freshness: indexed?.freshness || null
                };
            });
        });

        const availableIndustries = computed(() => {
            const industries = new Set();
            (stockIndexData.value?.stocks ? Object.values(stockIndexData.value.stocks) : []).forEach(s => {
                if (s.industry && s.industry !== 'ETF') industries.add(s.industry);
            });
            return ['All', 'ETF', ...Array.from(industries).sort()];
        });

        const filteredStocks = computed(() => {
            let res = searchUniverse.value;
            const minScore = (screenerIndustry.value === 'ETF') ? 0 : screenerMinScore.value;
            res = res.filter(s => (s.canslim?.score || 0) >= minScore);
            if (screenerMinRs.value !== 0) res = res.filter(s => (s.canslim?.mansfield_rs || 0) >= screenerMinRs.value);
            if (screenerIndustry.value !== 'All') res = res.filter(s => s.industry === screenerIndustry.value);
            return res.sort((a, b) => (b.canslim?.score || 0) - (a.canslim?.score || 0));
        });

        const allStocksSorted = computed(() => {
            return (stockData.value ? Object.values(stockData.value.stocks) : [])
                .sort((a, b) => (b.canslim?.score || 0) - (a.canslim?.score || 0));
        });

        // Freshness tier for leader ranking: a stock whose score hasn't been
        // recomputed in weeks/months (stuck in the rotation queue) must not
        // outrank a genuinely fresh score just because the frozen number is
        // numerically higher -- "今日強勢領頭羊" should mean today's, not
        // "whatever score happened to stick months ago".
        const freshnessTier = (s) => {
            const level = s && s.freshness && s.freshness.level;
            return (level === 'today' || level === 'warning') ? 0 : 1;
        };

        const byFreshnessThenScore = (a, b) => {
            const tierDiff = freshnessTier(a) - freshnessTier(b);
            if (tierDiff !== 0) return tierDiff;
            return ((b && b.canslim && b.canslim.score) || 0) - ((a && a.canslim && a.canslim.score) || 0);
        };

        // Separate stock leaders and ETF leaders at the data layer
        const stockLeaders = computed(() => {
            const stocks = stockData.value ? Object.values(stockData.value.stocks) : [];
            return stocks
                .filter(s => s && !s.is_etf)
                .sort(byFreshnessThenScore);
        });

        const etfLeaders = computed(() => {
            const stocks = stockData.value ? Object.values(stockData.value.stocks) : [];
            return stocks
                .filter(s => s && s.is_etf)
                .sort(byFreshnessThenScore);
        });

        const selectStock = (symbol) => {
            const stock = searchUniverse.value.find(s => s.symbol === symbol);
            if (stock) {
                currentStock.value = stock;
                activeTab.value = 'detail';
                window.history.pushState(null, '', `?s=${symbol}`);
            }
        };

        const closeDetail = () => { currentStock.value = null; activeTab.value = 'search'; window.history.pushState(null, '', window.location.pathname); };
        const onSearchInput = () => updateSuggestions();
        const clearSearch = () => { searchQuery.value = ''; searchSuggestions.value = []; };
        const updateSuggestions = () => {
            if (!searchQuery.value) { searchSuggestions.value = []; return; }
            const q = searchQuery.value.toLowerCase();
            searchSuggestions.value = searchUniverse.value.filter(s => s.symbol.includes(q) || s.name.toLowerCase().includes(q)).slice(0, 10);
        };

        const getScoreCategory = (score) => {
            if (score >= 85) return { label: '🔥 超強勢股', class: 'bg-red-100 text-red-800 border-red-200' };
            if (score >= 70) return { label: '🚀 潛力股', class: 'bg-orange-100 text-orange-800 border-orange-200' };
            return { label: '💤 盤整中', class: 'bg-slate-100 text-slate-600 border-slate-200' };
        };

        const getFreshnessBadge = (stock) => {
            if (stock && stock.freshness && stock.freshness.label) {
                return { label: stock.freshness.label, classes: 'bg-blue-100 text-blue-700' };
            }
            
            // Fallback to institutional date
            const latestInst = stock?.institutional && stock.institutional[0];
            if (latestInst && latestInst.date) {
                const dateStr = String(latestInst.date);
                const year = parseInt(dateStr.substring(0, 4));
                const month = parseInt(dateStr.substring(4, 6)) - 1;
                const day = parseInt(dateStr.substring(6, 8));
                const instDate = new Date(year, month, day);
                const today = new Date();
                today.setHours(0, 0, 0, 0);
                
                const diffTime = today - instDate;
                const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));
                
                if (diffDays <= 0) return { label: '🟢 今日', classes: 'bg-blue-100 text-blue-700' };
                if (diffDays <= 2) return { label: `🟡 ${diffDays}天前`, classes: 'bg-blue-100 text-blue-700' };
                return { label: '🔴 逾3天', classes: 'bg-blue-100 text-blue-700' };
            }
            
            return { label: '⚪ 未更新', classes: 'bg-slate-100 text-slate-500' };
        };
        const getStockFreshness = (s) => s.freshness || 'daily';

        const recentInstitutionalDays = (s, count = 5) => (s?.institutional || []).slice(0, count);
        const institutionalScale = (s, count = 5) => {
            const days = recentInstitutionalDays(s, count);
            if (days.length === 0) return 1;
            const vals = days.flatMap(d => [Math.abs(safeNumber(d.foreign_net)), Math.abs(safeNumber(d.trust_net)), Math.abs(safeNumber(d.dealer_net))]);
            return Math.max(...vals) || 1;
        };

        const institutionalBarStyle = (val, s, count = 5) => {
            const scale = institutionalScale(s, count);
            const height = Math.max(Math.round((Math.abs(safeNumber(val)) / scale) * 44), 1);
            return val >= 0 ? { height: `${height}%`, bottom: '50%', marginBottom: '1px' } : { height: `${height}%`, top: '50%', marginTop: '1px' };
        };

        const institutionalBarClass = (v, p, n) => v > 0 ? p : (v < 0 ? n : 'bg-slate-300');
        const institutionalValueClass = (v, p, n) => v > 0 ? p : (v < 0 ? n : 'text-slate-300');
        const totalInstitutionalNet = (day) => safeNumber(day?.foreign_net) + safeNumber(day?.trust_net) + safeNumber(day?.dealer_net);

        const formatNumber = (num) => {
            const sign = num > 0 ? '+' : '';
            return sign + num.toLocaleString();
        };

        const initInstitutionalChart = () => {
            this.$nextTick(() => {
                const canvas = document.getElementById('institutionalChart');
                if (!canvas || !window.Chart) return;

                const data = institutionalData.value.records;
                const dates = data.map(d => d.date);
                const foreign = data.map(d => d.foreign);
                const trust = data.map(d => d.trust);
                const proprietary = data.map(d => d.proprietary);

                new window.Chart(canvas, {
                    type: 'line',
                    data: {
                        labels: dates,
                        datasets: [
                            {
                                label: '外資', data: foreign, borderColor: '#1a73e8', backgroundColor: 'rgba(26, 115, 232, 0.1)',
                                borderWidth: 2.5, fill: true, tension: 0.4, pointRadius: 5, pointBackgroundColor: '#1a73e8', pointBorderColor: 'white', pointBorderWidth: 2
                            },
                            {
                                label: '投信', data: trust, borderColor: '#f59e0b', backgroundColor: 'rgba(245, 158, 11, 0.1)',
                                borderWidth: 2.5, fill: false, tension: 0.4, pointRadius: 5, pointBackgroundColor: '#f59e0b', pointBorderColor: 'white', pointBorderWidth: 2
                            },
                            {
                                label: '自營商', data: proprietary, borderColor: '#10b981', backgroundColor: 'rgba(16, 185, 129, 0.1)',
                                borderWidth: 2.5, fill: false, tension: 0.4, pointRadius: 5, pointBackgroundColor: '#10b981', pointBorderColor: 'white', pointBorderWidth: 2
                            }
                        ]
                    },
                    options: {
                        responsive: true, maintainAspectRatio: false,
                        plugins: { legend: { display: false } },
                        scales: {
                            y: { grid: { color: 'rgba(0, 0, 0, 0.05)' } },
                            x: { grid: { display: false } }
                        }
                    }
                });
            });
        };

        onMounted(() => {
            fetchData();
            if (activeTab.value === 'institutional') initInstitutionalChart();
        });

        return {
            stockData, stockIndexData, currentStock, searchQuery, lastUpdated, isLoading, loadingProgress, errorState, searchSuggestions,
            activeTab, screenerMinScore, screenerMinRs, screenerFundOnly, screenerIndustry, institutionalData,
            stockLeaders, etfLeaders, filteredStocks, searchUniverse, availableIndustries,
            selectStock, closeDetail, onSearchInput, clearSearch, updateSuggestions,
            getScoreCategory, getFreshnessBadge, getStockFreshness, formatNumber, initInstitutionalChart,
            recentInstitutionalDays, institutionalBarStyle, institutionalBarClass, institutionalValueClass, totalInstitutionalNet,
            financialLabels, canslimDefinitions,
            formatRelativeTime, getStockTier, getNextUpdateDay, getEffectiveRs,
        };
    }
});

app.mount('#app');
