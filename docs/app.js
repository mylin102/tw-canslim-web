// Alpha War Room - Dashboard v2.0
const { createApp, ref, computed, onMounted, watch, nextTick } = Vue;

const app = createApp({
    setup() {
        const stockData = ref(null);
        const searchQuery = ref('');
        const lastUpdated = ref('載入中...');
        const isLoading = ref(true);
        const loadingProgress = ref(0);
        const errorState = ref(null);
        const searchSuggestions = ref([]);

        // Tab state
        const activeTab = ref('search');
        const screenerMinScore = ref(0);
        const screenerMinRs = ref(0);
        const screenerFundOnly = ref(false);
        const screenerIndustry = ref('all');
        const screenerInstBuy = ref('any');

        const availableIndustries = computed(() => {
            if (!stockData.value) return [];
            const industries = new Set();
            Object.values(stockData.value.stocks).forEach(s => {
                if (s.industry && s.industry !== '未知') industries.add(s.industry);
            });
            return ['all', ...Array.from(industries).sort()];
        });

        const inst3dNet = (stock) => {
            if (!stock || !stock.institutional || !Array.isArray(stock.institutional) || stock.institutional.length < 1) return 0;
            const n = Math.min(3, stock.institutional.length);
            return stock.institutional.slice(0, n).reduce((sum, d) =>
                sum + (d.foreign_net || 0) + (d.trust_net || 0) + (d.dealer_net || 0), 0);
        };

        const sortedInstitutional = computed(() => {
            if (!currentStock.value || !currentStock.value.institutional) return [];
            return [...currentStock.value.institutional].sort((a, b) =>
                String(b.date).localeCompare(String(a.date)));
        });

        const metricsMap = computed(() => {
            const base = {
                'C': { label: 'C - 當季盈餘' },
                'A': { label: 'A - 年度成長' },
                'N': { label: 'N - 新高/因子' },
                'S': { label: 'S - 供需' },
                'L': { label: 'L - 強勢股' },
                'I': { label: 'I - 機構認同' }
            };
            
            if (currentStock.value && currentStock.value.is_etf) {
                base['C'].label = 'C - (ETF不適用)';
                base['A'].label = 'A - (ETF不適用)';
            }
            return base;
        });

        const instStrengthLabels = {
            '5d': '5日吸籌力道',
            '20d': '20日吸籌力道'
        };

        const financialLabels = {
            'eps': '每股盈餘 (EPS)',
            'revenue': '營業收入 (百萬)',
            'net_income': '稅後淨利 (百萬)',
            'gross_margin': '毛利率 (%)',
            'operating_margin': '營業利益率 (%)',
            'net_margin': '純益率 (%)'
        };

        // CANSLIM definitions (from William J. O'Neil's "How to Make Money in Stocks")
        const showCanslimDefs = ref(true);
        const canslimDefinitions = {
            'C': {
                title: 'Current Quarterly Earnings — 當季每股盈餘',
                desc: '當季 EPS 較去年同期成長 ≥ 25%。盈利加速是股價大漲的核心驅動力。',
                bgColor: 'bg-blue-50 border-blue-200',
                textColor: 'text-blue-700',
                badgeColor: 'bg-blue-100'
            },
            'A': {
                title: 'Annual Earnings Growth — 年度盈利成長',
                desc: '過去 3-5 年 EPS 年複合成長率 ≥ 25%。持續成長的公司才有長期漲幅。',
                bgColor: 'bg-green-50 border-green-200',
                textColor: 'text-green-700',
                badgeColor: 'bg-green-100'
            },
            'N': {
                title: 'New Products, Management, Highs — 新高/新動能',
                desc: '股價接近 52 週新高（≥ 90%），或有新產品、新管理層等利多催化劑。',
                bgColor: 'bg-purple-50 border-purple-200',
                textColor: 'text-purple-700',
                badgeColor: 'bg-purple-100'
            },
            'S': {
                title: 'Supply and Demand — 供需關係',
                desc: '成交量放大至平均 150% 以上，代表需求旺盛、籌碼集中。',
                bgColor: 'bg-orange-50 border-orange-200',
                textColor: 'text-orange-700',
                badgeColor: 'bg-orange-100'
            },
            'L': {
                title: 'Leader or Laggard — 強勢股 vs 弱勢股',
                desc: 'Mansfield RS 指標 > 0，代表股價表現優於大盤平均水平。只買龍頭股，不買落後股。',
                bgColor: 'bg-red-50 border-red-200',
                textColor: 'text-red-700',
                badgeColor: 'bg-red-100'
            },
            'I': {
                title: 'Institutional Sponsorship — 機構認同',
                desc: '外資、投信等法人連續 3 日以上淨買進，代表專業投資人認同此股。',
                bgColor: 'bg-teal-50 border-teal-200',
                textColor: 'text-teal-700',
                badgeColor: 'bg-teal-100'
            },
            'M': {
                title: 'Market Direction — 市場趨勢',
                desc: '大盤處於多頭格局（如加權指數在 200 日均線之上）。順勢操作，逆勢虧損大。',
                bgColor: 'bg-indigo-50 border-indigo-200',
                textColor: 'text-indigo-700',
                badgeColor: 'bg-indigo-100'
            }
        };

        let chartInstance = null;

        const updateSuggestions = () => {
            if (!stockData.value || searchQuery.value.length < 2) {
                searchSuggestions.value = [];
                return;
            }
            const query = searchQuery.value.trim().toLowerCase();
            searchSuggestions.value = Object.values(stockData.value.stocks)
                .filter(s => s.symbol.includes(query) || s.name.toLowerCase().includes(query))
                .slice(0, 10);
        };

        const onSearchInput = () => {
            updateSuggestions();
        };

        const clearSearch = () => {
            searchQuery.value = '';
            searchSuggestions.value = [];
        };

        const selectStock = (symbol) => {
            searchQuery.value = symbol;
            searchSuggestions.value = [];
            activeTab.value = 'search';
        };

        const currentStock = computed(() => {
            if (!stockData.value || !searchQuery.value) return null;
            const query = searchQuery.value.trim().toLowerCase();
            return stockData.value.stocks[query] || Object.values(stockData.value.stocks).find(s =>
                s.name.toLowerCase().includes(query) || s.symbol.includes(query)
            ) || null;
        });

        const allStocksSorted = computed(() => {
            if (!stockData.value || !stockData.value.stocks) return [];
            try {
                return Object.values(stockData.value.stocks)
                    .filter(s => s && s.canslim)
                    .sort((a, b) => {
                        const scoreA = (a.canslim && typeof a.canslim.score === 'number') ? a.canslim.score : 0;
                        const scoreB = (b.canslim && typeof b.canslim.score === 'number') ? b.canslim.score : 0;
                        return scoreB - scoreA;
                    });
            } catch (e) {
                console.error("Critical: Global sorting failed", e);
                return [];
            }
        });

        const filteredStocks = computed(() => {
            if (!stockData.value) return [];
            let result = Object.values(stockData.value.stocks)
                .filter(s => s.canslim.score >= screenerMinScore.value);

            if (screenerIndustry.value !== 'all') {
                result = result.filter(s => (s.industry || '未知') === screenerIndustry.value);
            }

            if (screenerInstBuy.value === '3d') {
                result = result.filter(s => inst3dNet(s) > 0);
            }

            if (screenerMinRs.value > 0) {
                result = result.filter(s => (s.canslim.rs_rating || 0) >= screenerMinRs.value);
            }
            if (screenerFundOnly.value) {
                result = result.filter(s => (s.canslim.fund_change || 0) > 0);
            }

            return result.sort((a, b) => b.canslim.score - a.canslim.score);
        });

        const fetchData = async () => {
            try {
                isLoading.value = true;
                const response = await fetch('data.json?t=' + Date.now());
                if (!response.ok) throw new Error('HTTP ' + response.status);
                const data = await response.json();
                stockData.value = data;
                lastUpdated.value = data.last_updated;
            } catch (error) {
                errorState.value = '載入失敗: ' + error.message;
            } finally {
                isLoading.value = false;
            }
        };

        onMounted(fetchData);

        // Watch for tab changes to render chart when needed
        watch(activeTab, async (newTab) => {
            if (newTab === 'search' && currentStock.value) {
                await nextTick();
                renderChart();
            }
        });

        watch(currentStock, async () => {
            if (activeTab.value === 'search' && currentStock.value) {
                await nextTick();
                renderChart();
            }
        });

        const renderChart = () => {
            const canvas = document.getElementById('inst-chart');
            if (!canvas || !currentStock.value) return;
            if (chartInstance) { chartInstance.destroy(); chartInstance = null; }

            const data = currentStock.value.institutional || [];
            if (data.length === 0) return;

            const labels = data.map(d => String(d.date));
            const foreignData = data.map(d => d.foreign_net || 0);
            const trustData = data.map(d => d.trust_net || 0);
            const dealerData = data.map(d => d.dealer_net || 0);

            chartInstance = new Chart(canvas, {
                type: 'bar',
                data: {
                    labels,
                    datasets: [
                        { label: '外資', data: foreignData, backgroundColor: 'rgba(59, 130, 246, 0.7)' },
                        { label: '投信', data: trustData, backgroundColor: 'rgba(16, 185, 129, 0.7)' },
                        { label: '自營商', data: dealerData, backgroundColor: 'rgba(245, 158, 11, 0.7)' }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { position: 'top' } },
                    scales: {
                        y: {
                            stacked: true,
                            ticks: { callback: v => v.toLocaleString() + ' 張' }
                        },
                        x: { stacked: true }
                    }
                }
            });
        };

        return {
            stockData, searchQuery, lastUpdated, isLoading, loadingProgress, errorState, searchSuggestions,
            activeTab, screenerMinScore, screenerMinRs, screenerFundOnly, screenerIndustry,
            currentStock, allStocksSorted, filteredStocks, metricsMap, financialLabels,
            updateSuggestions, onSearchInput, clearSearch, selectStock, fetchData,
            showCanslimDefs, canslimDefinitions,
            availableIndustries, screenerInstBuy, inst3dNet, sortedInstitutional
        };
    }
});

app.config.errorHandler = (err, vm, info) => {
    console.error("Vue Global Error:", err, info);
    // Silent catch to prevent white screen
};

app.mount('#app');
