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
        const searchTimeout = ref(null);

        const metricsMap = {
            'C': { label: 'C - 當季盈餘' },
            'A': { label: 'A - 年度成長' },
            'N': { label: 'N - 新高/因子' },
            'S': { label: 'S - 供需' },
            'L': { label: 'L - 強勢股' },
            'I': { label: 'I - 機構認同' }
        };

        let chartInstance = null;

        const onSearchInput = () => {
            // Debounce search to avoid excessive filtering
            if (searchTimeout.value) {
                clearTimeout(searchTimeout.value);
            }
            searchTimeout.value = setTimeout(() => {
                updateSuggestions();
            }, 200);
        };

        const updateSuggestions = () => {
            if (!stockData.value || searchQuery.value.length < 2) {
                searchSuggestions.value = [];
                return;
            }

            const query = searchQuery.value.trim().toLowerCase();
            const allStocks = Object.values(stockData.value.stocks);
            
            searchSuggestions.value = allStocks
                .filter(s => 
                    s.symbol.includes(query) || 
                    s.name.toLowerCase().includes(query)
                )
                .slice(0, 10); // Limit to 10 suggestions
        };

        const clearSearch = () => {
            searchQuery.value = '';
            searchSuggestions.value = [];
        };

        const selectStock = (symbol) => {
            searchQuery.value = symbol;
            searchSuggestions.value = [];
        };

        const currentStock = computed(() => {
            if (!stockData.value || !searchQuery.value) return null;
            const query = searchQuery.value.trim().toLowerCase();
            
            if (stockData.value.stocks[query]) {
                return stockData.value.stocks[query];
            }

            return Object.values(stockData.value.stocks).find(s => 
                s.name.toLowerCase().includes(query) || s.symbol.includes(query)
            ) || null;
        });

        const fetchData = async () => {
            try {
                isLoading.value = true;
                errorState.value = null;
                loadingProgress.value = 30;
                
                console.log("Fetching data.json...");
                
                // Try compressed first, fallback to JSON
                let data;
                try {
                    const response = await fetch('data.json.gz');
                    if (response.ok) {
                        loadingProgress.value = 60;
                        const arrayBuffer = await response.arrayBuffer();
                        const decompressed = pako.inflate(new Uint8Array(arrayBuffer), { to: 'string' });
                        data = JSON.parse(decompressed);
                        console.log("✅ Loaded compressed data");
                    } else {
                        throw new Error('No compressed data');
                    }
                } catch {
                    loadingProgress.value = 50;
                    console.log("Loading uncompressed JSON...");
                    const response = await fetch('data.json?t=' + Date.now());
                    if (!response.ok) {
                        throw new Error(`HTTP ${response.status}: Data file not found`);
                    }
                    loadingProgress.value = 80;
                    data = await response.json();
                }
                
                loadingProgress.value = 100;
                stockData.value = data;
                lastUpdated.value = data.last_updated;
                console.log("✅ Data loaded:", Object.keys(data.stocks).length, "stocks");
            } catch (error) {
                console.error('Failed to load data:', error);
                errorState.value = `資料載入失敗: ${error.message}`;
                lastUpdated.value = '載入失敗';
            } finally {
                setTimeout(() => {
                    isLoading.value = false;
                }, 300);
            }
        };

        const sortedInstitutional = computed(() => {
            if (!currentStock.value || !currentStock.value.institutional) return [];
            return [...currentStock.value.institutional].sort((a, b) => b.date.localeCompare(a.date));
        });

        const renderChart = async () => {
            await nextTick();
            const canvas = document.getElementById('inst-chart');
            if (!canvas || !currentStock.value) return;

            const ctx = canvas.getContext('2d');
            if (chartInstance) {
                chartInstance.destroy();
                chartInstance = null;
            }

            const data = [...currentStock.value.institutional].sort((a, b) => a.date.localeCompare(b.date));

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
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { position: 'bottom' } }
                }
            });
        };

        watch(currentStock, async (newVal) => {
            if (chartInstance) {
                chartInstance.destroy();
                chartInstance = null;
            }
            if (newVal) await renderChart();
        });

        onMounted(() => {
            fetchData();
        });

        return {
            searchQuery,
            lastUpdated,
            currentStock,
            metricsMap,
            sortedInstitutional,
            isLoading,
            loadingProgress,
            errorState,
            searchSuggestions,
            onSearchInput,
            clearSearch,
            selectStock
        };
    }
}).mount('#app');
