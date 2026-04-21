/*
 * tw-canslim-web
 * Lightweight CANSLIM analyzer for Taiwan Stock Market
 */

const { createApp, ref, computed, onMounted } = Vue;

const app = createApp({
    setup() {
        const stockData = ref(null);
        const stockIndexData = ref(null);
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
            'C': {
                title: 'Current Quarterly Earnings — 當季獲利',
                desc: '最近一季 EPS 成長率 ≥ 25% (YoY)。這是大漲股的最基本特徵，顯示公司正處於爆發性成長期。',
                bgColor: 'bg-blue-50 border-blue-200',
                textColor: 'text-blue-800',
                badgeColor: 'bg-blue-600'
            },
            'A': {
                title: 'Annual Earnings Increases — 年度獲利',
                desc: '最近一年度 EPS 成長率 ≥ 25% (YoY)。確保公司並非曇花一現，而是具備長期成長實力的龍頭潛力。',
                bgColor: 'bg-green-50 border-green-200',
                textColor: 'text-green-800',
                badgeColor: 'bg-green-600'
            },
            'N': {
                title: 'New Products, Management, Highs — 新契機',
                desc: '股價處於 52 週新高的 90% 區間內。買入「創新高」的股票是大賺小賠的關鍵，代表市場對新契機的認同。',
                bgColor: 'bg-purple-50 border-purple-200',
                textColor: 'text-purple-800',
                badgeColor: 'bg-purple-600'
            },
            'S': {
                title: 'Supply and Demand — 供給與需求',
                desc: '成交量爆發（> 5 日均量 1.5 倍）。當股票在大漲且伴隨巨大成交量時，通常是主力法人建倉的訊號。',
                bgColor: 'bg-yellow-50 border-yellow-200',
                textColor: 'text-yellow-800',
                badgeColor: 'bg-yellow-600'
            },
            'L': {
                title: 'Leader or Laggard — 強勢股或落後股',
                desc: 'Mansfield RS 指標 > 0。買入產業中的「領導者」而非受困於底部的「落後股」，才能獲得超額報酬。',
                bgColor: 'bg-indigo-50 border-indigo-200',
                textColor: 'text-indigo-800',
                badgeColor: 'bg-indigo-600'
            },
            'I': {
                title: 'Institutional Sponsorship — 法人追蹤',
                desc: '三大法人近 3 日買超。跟隨「聰明錢」的腳步，尋找有法人機構背書與鎖碼的績優標的。',
                bgColor: 'bg-red-50 border-red-200',
                textColor: 'text-red-800',
                badgeColor: 'bg-red-600'
            },
            'M': {
                title: 'Market Direction — 市場趨勢',
                desc: '追蹤大盤多空。當大盤處於空頭市場時，即便選出再好的股票，成功率也會大幅下降。',
                bgColor: 'bg-slate-50 border-slate-200',
                textColor: 'text-slate-800',
                badgeColor: 'bg-slate-600'
            }
        };

        const getScoreCategory = (score) => {
            if (score >= 85) return { label: '🔥 超強勢股', class: 'bg-red-100 text-red-800 border-red-200' };
            if (score >= 70) return { label: '🚀 潛力股', class: 'bg-orange-100 text-orange-800 border-orange-200' };
            if (score >= 50) return { label: '📈 轉強中', class: 'bg-blue-100 text-blue-800 border-blue-200' };
            return { label: '💤 盤整中', class: 'bg-slate-100 text-slate-600 border-slate-200' };
        };

        const fetchData = async () => {
            isLoading.value = true;
            loadingProgress.value = 10;
            try {
                const [response, indexResponse, featuresResponse] = await Promise.all([
                    fetch('data.json?t=' + new Date().getTime()),
                    fetch('stock_index.json?t=' + new Date().getTime()),
                    fetch('api/stock_features.json?t=' + new Date().getTime()).catch(() => ({ json: () => ({}) })),
                ]);
                loadingProgress.value = 50;
                
                const featuresData = typeof featuresResponse.json === 'function' ? await featuresResponse.json() : {};
                
                // Merge features into stock data (featuresData is now a dictionary symbol -> data)
                if (data.stocks && featuresData) {
                    Object.keys(data.stocks).forEach(symbol => {
                        if (featuresData[symbol]) {
                            data.stocks[symbol].revenue_features = featuresData[symbol];
                        }
                    });
                }

                stockData.value = data;
                stockIndexData.value = indexData;
                lastUpdated.value = data.last_updated;
                loadingProgress.value = 100;
                
                // If query param exists, auto-select
                const urlParams = new URLSearchParams(window.location.search);
                const s = urlParams.get('s');
                if (s && ((data.stocks && data.stocks[s]) || (indexData.stocks && indexData.stocks[s]))) {
                    searchQuery.value = s;
                }
            } catch (err) {
                console.error('Fetch error:', err);
                errorState.value = "無法載入戰情室數據，請檢查網路連線或稍後再試。";
            } finally {
                setTimeout(() => {
                    isLoading.value = false;
                }, 500);
            }
        };

        const createIndexFallbackStock = (entry) => {
            if (!entry) return null;
            return {
                symbol: entry.symbol,
                name: entry.name,
                industry: entry.industry || '',
                is_etf: (entry.industry || '').toUpperCase() === 'ETF',
                freshness: entry.freshness || null,
                last_succeeded_at: entry.last_succeeded_at || '',
                has_full_detail: false,
                institutional: [],
                financials: {},
                revenue_features: null,
                canslim: {
                    C: false,
                    A: false,
                    N: false,
                    S: false,
                    L: false,
                    I: false,
                    M: true,
                    score: 0,
                    score_delta: 0,
                    i_score_abs: 0,
                    inst_details: {},
                    mansfield_rs: 0,
                    grid_strategy: { volatility_annual: 0, levels: [] },
                },
            };
        };

        const searchUniverse = computed(() => {
            const merged = new Map();

            if (stockData.value && stockData.value.stocks) {
                Object.values(stockData.value.stocks).forEach(stock => {
                    merged.set(stock.symbol, {
                        ...stock,
                        has_full_detail: true,
                    });
                });
            }

            if (stockIndexData.value && stockIndexData.value.stocks) {
                Object.values(stockIndexData.value.stocks).forEach(entry => {
                    if (!merged.has(entry.symbol)) {
                        merged.set(entry.symbol, createIndexFallbackStock(entry));
                    }
                });
            }

            return Array.from(merged.values());
        });

        const updateSuggestions = () => {
            if (!searchQuery.value || searchQuery.value.length < 1) {
                searchSuggestions.value = [];
                return;
            }
            const query = searchQuery.value.toLowerCase();
            const matches = searchUniverse.value
                .filter(s => s.symbol.includes(query) || (s.name || '').toLowerCase().includes(query))
                .slice(0, 8);
            searchSuggestions.value = matches;
        };

        const onSearchInput = () => {
            updateSuggestions();
        };

        const selectStock = (symbol) => {
            searchQuery.value = symbol;
            searchSuggestions.value = [];
            // Update URL without reload
            const newurl = window.location.protocol + "//" + window.location.host + window.location.pathname + '?s=' + symbol;
            window.history.pushState({path:newurl},'',newurl);
        };

        const clearSearch = () => {
            searchQuery.value = '';
            searchSuggestions.value = [];
            window.history.pushState({path:window.location.pathname},'',window.location.pathname);
        };

        const currentStock = computed(() => {
            if (!searchQuery.value) return null;
            const query = searchQuery.value.trim().toLowerCase();
            
            // Exact match
            const exactMatch = searchUniverse.value.find(s => s.symbol.toLowerCase() === query);
            if (exactMatch) return exactMatch;
            
            // Name match
            return searchUniverse.value.find(s => 
                (s.name || '').toLowerCase().includes(query) || s.symbol.toLowerCase() === query
            ) || null;
        });

        const allStocksSorted = computed(() => {
            if (!stockData.value) return [];
            return Object.values(stockData.value.stocks)
                .sort((a, b) => {
                    // Primary: Score
                    if (b.canslim.score !== a.canslim.score) return b.canslim.score - a.canslim.score;
                    // Secondary: Revenue Score (Alpha)
                    const aRev = a.revenue_features?.revenue_score || 0;
                    const bRev = b.revenue_features?.revenue_score || 0;
                    if (bRev !== aRev) return bRev - aRev;
                    // Tertiary: Institutional score (abs)
                    const aI = a.canslim.i_score_abs || 0;
                    const bI = b.canslim.i_score_abs || 0;
                    if (bI !== aI) return bI - aI;
                    // Fourth: Mansfield RS
                    return (b.canslim.mansfield_rs || 0) - (a.canslim.mansfield_rs || 0);
                });
        });

        const filteredStocks = computed(() => {
            if (!stockData.value) return [];
            const effectiveMinScore = screenerIndustry.value === 'ETF' ? 0 : screenerMinScore.value;
            let result = Object.values(stockData.value.stocks)
                .filter(s => s.canslim.score >= effectiveMinScore);
            
            if (screenerMinRs.value !== 0) {
                result = result.filter(s => (s.canslim.mansfield_rs || 0) >= screenerMinRs.value);
            }

            if (screenerIndustry.value !== 'All') {
                result = result.filter(s => s.industry === screenerIndustry.value);
            }

            if (screenerFundOnly.value) {
                result = result.filter(s => (s.canslim.fund_holdings?.current_month || 0) > 0);
            }

            return result.sort((a, b) => b.canslim.score - a.canslim.score);
        });

        const availableIndustries = computed(() => {
            if (!stockData.value) return ['All'];
            const industries = new Set(Object.values(stockData.value.stocks).map(s => s.industry).filter(Boolean));
            return ['All', ...Array.from(industries).sort()];
        });

        const metricsMap = computed(() => {
            return {
                'C': { label: '當季獲利' },
                'A': { label: '年度獲利' },
                'N': { label: '新高/契機' },
                'S': { label: '籌碼供需' },
                'L': { label: '市場龍頭' },
                'I': { label: '法人認同' }
            };
        });

        const getFreshnessBadge = (freshness) => {
            if (freshness && typeof freshness === 'object') {
                const level = freshness.level || 'unknown';
                const label = freshness.label || '未知';
                if (level === 'today') return { label, classes: 'bg-green-100 text-green-700 border-green-200' };
                if (level === 'warning') return { label, classes: 'bg-amber-100 text-amber-700 border-amber-200' };
                if (level === 'stale') return { label, classes: 'bg-rose-100 text-rose-700 border-rose-200' };
                return { label, classes: 'bg-slate-100 text-slate-500 border-slate-200' };
            }
            if (!freshness) return { label: '未知', classes: 'bg-slate-100 text-slate-500 border-slate-200' };
            if (freshness === 'realtime') return { label: '即時', classes: 'bg-green-100 text-green-700 border-green-200' };
            if (freshness === 'daily') return { label: '今日', classes: 'bg-blue-100 text-blue-700 border-blue-200' };
            if (freshness === 'stale') return { label: '延遲', classes: 'bg-amber-100 text-amber-700 border-amber-200' };
            return { label: freshness, classes: 'bg-slate-100 text-slate-500 border-slate-200' };
        };

        const getStockFreshness = (stock) => {
            return stock.freshness || 'daily';
        };

        const recentInstitutionalDays = (stock, count = 5) => {
            if (!stock || !Array.isArray(stock.institutional)) return [];
            // Data in JSON is already in 'Lots' (張) via backend // 1000
            return stock.institutional.slice(0, count);
        };

        const institutionalScale = (stock, count = 5) => {
            const days = recentInstitutionalDays(stock, count);
            if (days.length === 0) return 1;
            const values = days.flatMap(day => [
                Math.abs(safeNumber(day.foreign_net)),
                Math.abs(safeNumber(day.trust_net)),
                Math.abs(safeNumber(day.dealer_net)),
            ]);
            const maxVal = Math.max(...values);
            return maxVal > 0 ? maxVal : 1;
        };

        const institutionalBarStyle = (value, stock, count = 5) => {
            const normalized = safeNumber(value);
            const scale = institutionalScale(stock, count);
            // Height represents percentage of the max value in the 5-day window
            // Max height is 44% (half of container minus padding)
            const height = normalized === 0
                ? 1 
                : Math.max(Math.round((Math.abs(normalized) / scale) * 44), 4);

            if (normalized > 0) {
                return {
                    height: `${height}%`,
                    bottom: '50%',
                    marginBottom: '1px'
                };
            }

            if (normalized < 0) {
                return {
                    height: `${height}%`,
                    top: '50%',
                    marginTop: '1px'
                };
            }

            return {
                height: '2px',
                bottom: 'calc(50% - 1px)',
            };
        };

        const institutionalBarClass = (value, positiveClass, negativeClass) => {
            if (value > 0) return positiveClass;
            if (value < 0) return negativeClass;
            return 'bg-slate-300';
        };

        const institutionalValueClass = (value, positiveClass, negativeClass) => {
            if (value > 0) return positiveClass;
            if (value < 0) return negativeClass;
            return 'text-slate-300';
        };

        const safeNumber = (value) => {
            const normalized = Number(value);
            return Number.isFinite(normalized) ? normalized : 0;
        };

        const formatNumber = (value) => {
            return safeNumber(value).toLocaleString();
        };

        const totalInstitutionalNet = (day) => {
            if (!day || typeof day !== 'object') return 0;
            return safeNumber(day.foreign_net) + safeNumber(day.trust_net) + safeNumber(day.dealer_net);
        };

        onMounted(() => {
            fetchData();
        });

        return {
            stockData, searchQuery, lastUpdated, isLoading, loadingProgress, errorState, searchSuggestions,
            activeTab, screenerMinScore, screenerMinRs, screenerFundOnly, screenerIndustry,
            currentStock, allStocksSorted, filteredStocks, metricsMap, financialLabels, searchUniverse,
            updateSuggestions, onSearchInput, clearSearch, selectStock, fetchData,
            canslimDefinitions, getScoreCategory, getFreshnessBadge, getStockFreshness,
            availableIndustries, recentInstitutionalDays, institutionalBarStyle, institutionalBarClass,
            institutionalValueClass, formatNumber, totalInstitutionalNet
        };
    }
});

app.mount('#app');
