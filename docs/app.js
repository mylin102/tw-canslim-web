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
        const activeTab = ref('search'); // 'search', 'ranking', 'screener'

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
                const [response, indexResponse] = await Promise.all([
                    fetch('data.json?t=' + new Date().getTime()),
                    fetch('stock_index.json?t=' + new Date().getTime())
                ]);
                
                if (!response.ok) throw new Error('data.json 載入失敗');
                if (!indexResponse.ok) throw new Error('stock_index.json 載入失敗');
                
                const data = await response.json();
                const indexData = await indexResponse.json();
                
                // Fetch features (non-blocking)
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
                                if (featMap[s]) data.stocks[s].revenue_features = featMap[s];
                            });
                        }
                    }
                } catch (e) { console.warn('Features missing'); }

                stockData.value = data;
                stockIndexData.value = indexData;
                lastUpdated.value = data.last_updated || 'Unknown';

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

        const getFreshnessBadge = (f) => ({ label: f?.label || '未知', classes: 'bg-blue-100 text-blue-700' });
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

        onMounted(() => fetchData());

        return {
            stockData, stockIndexData, currentStock, searchQuery, lastUpdated, isLoading, loadingProgress, errorState, searchSuggestions,
            activeTab, screenerMinScore, screenerMinRs, screenerFundOnly, screenerIndustry,
            allStocksSorted, filteredStocks, searchUniverse, availableIndustries,
            selectStock, closeDetail, onSearchInput, clearSearch, updateSuggestions,
            getScoreCategory, getFreshnessBadge, getStockFreshness, formatNumber,
            recentInstitutionalDays, institutionalBarStyle, institutionalBarClass, institutionalValueClass, totalInstitutionalNet,
            financialLabels, canslimDefinitions
        };
    }
});

app.mount('#app');
