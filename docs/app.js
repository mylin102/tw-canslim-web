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
        const screenerMinScore = ref(60);
        const screenerMinRs = ref(0);
        const screenerFundOnly = ref(false);
        const screenerIndustry = ref('all');

        const metricsMap = {
            'C': { label: 'C - 當季盈餘' },
            'A': { label: 'A - 年度成長' },
            'N': { label: 'N - 新高/因子' },
            'S': { label: 'S - 供需' },
            'L': { label: 'L - 強勢股' },
            'I': { label: 'I - 機構認同' }
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
                desc: '股價表現優於大盤 20% 以上。只買龍頭股，不買落後股。',
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

        const selectStock = (symbol) => { searchQuery.value = symbol; searchSuggestions.value = []; activeTab.value = 'search'; };

        const currentStock = computed(() => {
            if (!stockData.value || !searchQuery.value) return null;
            const query = searchQuery.value.trim().toLowerCase();
            return stockData.value.stocks[query] || Object.values(stockData.value.stocks).find(s =>
                s.name.toLowerCase().includes(query) || s.symbol.includes(query)
            ) || null;
        });

        const allStocksSorted = computed(() => {
            if (!stockData.value) return [];
            return Object.values(stockData.value.stocks)
                .sort((a, b) => b.canslim.score - a.canslim.score);
        });

        const filteredStocks = computed(() => {
            if (!stockData.value) return [];
            let result = Object.values(stockData.value.stocks)
                .filter(s => s.canslim.score >= screenerMinScore.value);
            
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

        return {
            stockData, searchQuery, lastUpdated, isLoading, errorState, searchSuggestions,
            activeTab, screenerMinScore, screenerMinRs, screenerFundOnly,
            currentStock, allStocksSorted, filteredStocks, metricsMap,
            updateSuggestions, selectStock, fetchData,
            showCanslimDefs, canslimDefinitions
        };
    }
});

app.mount('#app');
