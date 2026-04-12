const { createApp, ref, computed, onMounted, watch, nextTick } = Vue;

const app = createApp({
    setup() {
        const stockData = ref(null);
        const searchQuery = ref('');
        const lastUpdated = ref('載入中...');
        const metricsMap = {
            'C': { label: 'C - 當季盈餘' },
            'A': { label: 'A - 年度成長' },
            'N': { label: 'N - 新高/因子' },
            'S': { label: 'S - 供需' },
            'L': { label: 'L - 強勢股' },
            'I': { label: 'I - 機構認同' }
        };

        let chartInstance = null;

        const currentStock = computed(() => {
            if (!stockData.value || !searchQuery.value) return null;
            const query = searchQuery.value.trim().toLowerCase();
            
            // 1. Ticker exact match
            if (stockData.value.stocks[query]) {
                lastUpdated.value = stockData.value.last_updated;
                return stockData.value.stocks[query];
            }

            // 2. Name fuzzy match
            const foundByTitle = Object.values(stockData.value.stocks).find(s => 
                s.name.toLowerCase().includes(query) || s.symbol.includes(query)
            );

            if (!foundByTitle && query.length >= 2) {
                lastUpdated.value = `查無資料 (${query})`;
            } else if (foundByTitle) {
                lastUpdated.value = stockData.value.last_updated;
            }
            return foundByTitle || null;
        });

        const fetchData = async () => {
            try {
                const response = await fetch('data.json');
                if (!response.ok) throw new Error('Data file not found');
                const data = await response.json();
                stockData.value = data;
                lastUpdated.value = data.last_updated;
                console.log("Data loaded successfully");
            } catch (error) {
                console.error('Failed to load data:', error);
                lastUpdated.value = '載入失敗 (請確認已生成 data.json)';
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
            }

            const data = [...currentStock.value.institutional].sort((a, b) => a.date.localeCompare(b.date));
            
            chartInstance = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: data.map(d => d.date.substring(4)), // MM/DD
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

        watch(currentStock, (newVal) => {
            if (newVal) {
                renderChart();
            }
        });

        onMounted(fetchData);

        return {
            searchQuery,
            lastUpdated,
            currentStock,
            metricsMap,
            sortedInstitutional
        };
    }
});

// 安全掛載
app.mount('#app');
