// Stock screener and ranking functionality
const screenerModule = {
    setup() {
        const allStocks = computed(() => {
            if (!stockData.value) return [];
            return Object.values(stockData.value.stocks);
        });

        const topRanked = computed(() => {
            return allStocks.value
                .filter(s => s.canslim.score >= 70)
                .sort((a, b) => b.canslim.score - a.canslim.score)
                .slice(0, 20);
        });

        const withInstitutionalBuying = computed(() => {
            return allStocks.value
                .filter(s => {
                    if (!s.institutional || s.institutional.length < 3) return false;
                    const recent3 = s.institutional.slice(0, 3);
                    const totalNet = recent3.reduce((sum, d) => 
                        sum + d.foreign_net + d.trust_net + d.dealer_net, 0);
                    return totalNet > 0;
                })
                .sort((a, b) => {
                    const aNet = a.institutional.slice(0, 3).reduce((s, d) => 
                        s + d.foreign_net + d.trust_net + d.dealer_net, 0);
                    const bNet = b.institutional.slice(0, 3).reduce((s, d) => 
                        s + d.foreign_net + d.trust_net + d.dealer_net, 0);
                    return bNet - aNet;
                })
                .slice(0, 20);
        });

        const highScoreBuying = computed(() => {
            return allStocks.value
                .filter(s => s.canslim.score >= 80)
                .filter(s => {
                    if (!s.institutional || s.institutional.length < 3) return false;
                    const recent3 = s.institutional.slice(0, 3);
                    const totalNet = recent3.reduce((sum, d) => 
                        sum + d.foreign_net + d.trust_net + d.dealer_net, 0);
                    return totalNet > 0;
                })
                .sort((a, b) => b.canslim.score - a.canslim.score);
        });

        return {
            topRanked,
            withInstitutionalBuying,
            highScoreBuying
        };
    }
};
