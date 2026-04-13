// Simplified CANSLIM app - v2
// Global error handler
window.onerror = function(msg, url, line, col, error) {
    console.error("GLOBAL ERROR:", msg, "at line", line);
    return false;
};

console.log("App loading...");

if (typeof Vue === 'undefined') {
    alert("Vue CDN failed to load! Check network connection.");
} else {
    console.log("Vue loaded, version:", Vue.version);
}

const { createApp, ref, computed, onMounted, watch, nextTick } = Vue;

const app = createApp({
    setup() {
        console.log("setup() called");

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
        const screenerInstBuy = ref('any');

        console.log("activeTab created:", activeTab.value);

        const metricsMap = {
            'C': { label: 'C - 當季盈餘' },
            'A': { label: 'A - 年度成長' },
            'N': { label: 'N - 新高/因子' },
            'S': { label: 'S - 供需' },
            'L': { label: 'L - 強勢股' },
            'I': { label: 'I - 機構認同' }
        };

        let chartInstance = null;

        // Search helpers
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

        const clearSearch = () => { searchQuery.value = ''; searchSuggestions.value = []; };
        const selectStock = (symbol) => { searchQuery.value = symbol; searchSuggestions.value = []; };

        // Main computed: current stock
        const currentStock = computed(() => {
            if (!stockData.value || !searchQuery.value) return null;
            const query = searchQuery.value.trim().toLowerCase();
            if (stockData.value.stocks[query]) return stockData.value.stocks[query];
            return Object.values(stockData.value.stocks).find(s =>
                s.name.toLowerCase().includes(query) || s.symbol.includes(query)
            ) || null;
        });

        // RANKING TAB DATA
        const allStocksSorted = computed(() => {
            if (!stockData.value) return [];
            return Object.values(stockData.value.stocks)
                .sort((a, b) => b.canslim.score - a.canslim.score);
        });

        // SCREENER TAB DATA
        const filteredStocks = computed(() => {
            if (!stockData.value) return [];
            let result = Object.values(stockData.value.stocks)
                .filter(s => s.canslim.score >= screenerMinScore.value);
            return result.sort((a, b) => b.canslim.score - a.canslim.score);
        });

        // Helpers
        const inst3dNet = (stock) => {
            if (!stock.institutional || stock.institutional.length < 3) return 0;
            return stock.institutional.slice(0, 3).reduce((s, d) =>
                s + d.foreign_net + d.trust_net + d.dealer_net, 0);
        };

        // Load data
        const fetchData = async () => {
            try {
                isLoading.value = true;
                errorState.value = null;
                loadingProgress.value = 30;
                console.log("Fetching data.json...");

                const response = await fetch('data.json?v=99999&t=' + Date.now());
                if (!response.ok) throw new Error('HTTP ' + response.status);
                loadingProgress.value = 80;

                const data = await response.json();
                loadingProgress.value = 100;
                stockData.value = data;
                lastUpdated.value = data.last_updated;
                console.log("Data loaded:", Object.keys(data.stocks).length, "stocks");
            } catch (error) {
                console.error('Failed:', error);
                errorState.value = '資料載入失敗: ' + error.message;
                lastUpdated.value = '載入失敗';
            } finally {
                isLoading.value = false;
            }
        };

        // Chart
        const renderChart = async (stock) => {
            await nextTick();
            const canvas = document.getElementById('inst-chart');
            if (!canvas || !stock || typeof Chart === 'undefined') return;
            const ctx = canvas.getContext('2d');
            if (chartInstance) chartInstance.destroy();
            const data = [...stock.institutional].sort((a, b) => a.date.localeCompare(b.date));
            chartInstance = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: data.map(d => d.date.substring(4)),
                    datasets: [
                        { label: '外資', data: data.map(d => d.foreign_net), backgroundColor: 'rgba(59, 130, 246, 0.6)' },
                        { label: '投信', data: data.map(d => d.trust_net), backgroundColor: 'rgba(16, 185, 129, 0.6)' },
                        { label: '自營商', data: data.map(d => d.dealer_net), backgroundColor: 'rgba(245, 158, 11, 0.6)' }
                    ]
                },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } }
            });
        };

        watch(currentStock, async (val) => {
            if (chartInstance) { chartInstance.destroy(); chartInstance = null; }
            if (val) await renderChart(val);
        });

        onMounted(() => {
            console.log("App mounted, loading data...");
            fetchData();
        });

        return {
            stockData, searchQuery, lastUpdated, isLoading, loadingProgress, errorState,
            searchSuggestions, activeTab, screenerMinScore, screenerInstBuy,
            metricsMap, currentStock, allStocksSorted, filteredStocks,
            onSearchInput: updateSuggestions, clearSearch, selectStock, inst3dNet
        };
    }
});

console.log("App created, mounting...");
app.mount('#app');
console.log("App mounted successfully!");
