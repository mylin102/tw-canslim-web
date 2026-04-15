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

        // Single stock update state
        const showUpdateModal = ref(false);
        const updateTicker = ref('');
        const isUpdateLoading = ref(false);
        const updateStatus = ref('');

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
            if (!currentStock.value || !currentStock.value.institutional || !Array.isArray(currentStock.value.institutional)) return [];
            return currentStock.value.institutional
                .filter(row => row && !row.no_data)
                .sort((a, b) => String(b.date || '').localeCompare(String(a.date || '')));
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
                base['C'].label = 'C - 成份股動能';
                base['A'].label = 'A - 指數獲利力';
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
                desc: '個股：EPS 成長 ≥ 25%。 ETF：追蹤成份股之獲利動能與產業強度。',
                bgColor: 'bg-blue-50 border-blue-200',
                textColor: 'text-blue-700',
                badgeColor: 'bg-blue-100'
            },
            'A': {
                title: 'Annual Earnings Growth — 年度盈利成長',
                desc: '個股：年度 EPS 穩定增長且 ROE ≥ 17%。 ETF：追蹤指數之獲利一致性與長期趨勢。',
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
                desc: 'Mansfield RS > 0 代表表現優於大盤平均水平。正值越高，代表其相對強度越強，顯示個股正處於「強勢區」。',
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

        // 緩存排序結果以提高性能
        const sortedStocksCache = ref(null);
        const sortedStocksCacheKey = ref('');
        
        const allStocksSorted = computed(() => {
            if (!stockData.value || !stockData.value.stocks) return [];
            
            // 檢查緩存
            const cacheKey = `${Object.keys(stockData.value.stocks).length}`;
            if (sortedStocksCache.value && sortedStocksCacheKey.value === cacheKey) {
                return sortedStocksCache.value;
            }
            
            try {
                console.time('股票排序');
                const sorted = Object.values(stockData.value.stocks)
                    .filter(s => s && s.canslim)
                    .sort((a, b) => {
                        const scoreA = (a.canslim && typeof a.canslim.score === 'number') ? a.canslim.score : 0;
                        const scoreB = (b.canslim && typeof b.canslim.score === 'number') ? b.canslim.score : 0;
                        return scoreB - scoreA;
                    });
                console.timeEnd('股票排序');
                console.log(`📊 排序完成: ${sorted.length} 檔股票`);
                
                // 更新緩存
                sortedStocksCache.value = sorted;
                sortedStocksCacheKey.value = cacheKey;
                
                return sorted;
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
                loadingProgress.value = 10;
                
                console.time('數據加載');
                const response = await fetch('data.json?t=' + Date.now());
                if (!response.ok) throw new Error('HTTP ' + response.status);
                
                loadingProgress.value = 30;
                const data = await response.json();
                
                loadingProgress.value = 60;
                console.log(`📊 數據加載中: ${Object.keys(data.stocks).length} 檔股票`);
                
                // 分批設置數據以避免阻塞
                await new Promise(resolve => setTimeout(resolve, 0));
                stockData.value = data;
                
                loadingProgress.value = 90;
                lastUpdated.value = data.last_updated;
                
                console.timeEnd('數據加載');
                console.log(`✅ 數據加載完成: ${Object.keys(data.stocks).length} 檔股票`);
                
            } catch (error) {
                console.error('數據加載錯誤:', error);
                errorState.value = '載入失敗: ' + error.message;
                
                // 嘗試加載精簡版作為備用
                console.log('嘗試加載精簡版數據...');
                try {
                    const fallbackResponse = await fetch('data_light.json?t=' + Date.now());
                    const fallbackData = await fallbackResponse.json();
                    stockData.value = fallbackData;
                    lastUpdated.value = fallbackData.last_updated + ' (精簡版)';
                    console.log(`✅ 精簡版數據加載成功: ${Object.keys(fallbackData.stocks).length} 檔股票`);
                } catch (fallbackError) {
                    console.error('精簡版數據也加載失敗:', fallbackError);
                }
            } finally {
                loadingProgress.value = 100;
                isLoading.value = false;
            }
        };

        const checkUrlParams = () => {
            const fullUrl = window.location.href;
            const search = window.location.search;
            
            let ticker = '';

            // 1. 優先嘗試標準解析 ?update=2330
            const urlParams = new URLSearchParams(search);
            ticker = urlParams.get('update');

            // 2. 如果沒抓到，嘗試解析 ?update:2330 格式 (包含 URL 編碼處理)
            if (!ticker) {
                const decodedUrl = decodeURIComponent(fullUrl);
                if (decodedUrl.includes('update:')) {
                    ticker = decodedUrl.split('update:')[1].split('&')[0].split('#')[0];
                }
            }

            // 3. 如果抓到代號，延遲 500ms 顯示，確保 Safari 中 Vue 已完全掛載
            if (ticker && /^\d{4,6}$/.test(ticker)) {
                setTimeout(() => {
                    updateTicker.value = ticker;
                    showUpdateModal.value = true;
                }, 500);
            }
        };

        const triggerUpdate = () => {
            if (!updateTicker.value || updateTicker.value.length < 4) {
                updateStatus.value = '請輸入正確的股票代號';
                return;
            }
            
            isUpdateLoading.value = true;
            updateStatus.value = '準備跳轉至 GitHub...';
            
            // Redirect to GitHub Issue with pre-filled title
            const repoUrl = 'https://github.com/mylin102/tw-canslim-web';
            const issueTitle = `update:${updateTicker.value}`;
            const issueBody = `On-demand update request for stock: ${updateTicker.value}. This will be processed automatically.`;
            const githubUrl = `${repoUrl}/issues/new?title=${encodeURIComponent(issueTitle)}&body=${encodeURIComponent(issueBody)}`;
            
            window.location.href = githubUrl;
        };

        onMounted(() => {
            fetchData();
            checkUrlParams();
        });

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
            availableIndustries, screenerInstBuy, inst3dNet, sortedInstitutional,
            showUpdateModal, updateTicker, isUpdateLoading, updateStatus, triggerUpdate
        };
    }
});

app.config.errorHandler = (err, vm, info) => {
    console.error("Vue Global Error:", err, info);
    // Silent catch to prevent white screen
};

app.mount('#app');
